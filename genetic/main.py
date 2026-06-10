"""Driver: parse CLI, dispatch to per-subcommand handler.

Subcommand handlers:
- _run    : the M2 GA driver
- _save_best : extract champion from a run dir, write a patch
- _play   : load a patch and audition it
- _resume : extend an existing run with champion-seeded gens
"""

import contextlib
import json
import random
from pathlib import Path

from deap import base, creator, tools, algorithms

from synthesizer.midicontrol import MidiConnection, AnalogRytmMachineSelector
from synthesizer.parameters import AnalogRytmParameterCSVReader, Parameter, ParameterCollection
from user_interface.voter import LPD8VoteController, KeyboardVoteController

from genetic.genome import (
    apply_pad_config, build_bounds, make_individual, bounded_mutate,
)
from genetic.pad_config import get_pad_config
from genetic.evaluate import (
    make_evaluate, send_individual, build_params_for_individual,
)
from genetic.cli import parse_args
from genetic.logging import (
    make_run_dir, write_config, log_generation, log_vote, read_last_generation,
)
from genetic import patches


# ============================================================================
# Top-level dispatch
# ============================================================================

def run(argv=None):
    args = parse_args(argv)
    if args.subcommand == "run":
        _run(args)
    elif args.subcommand == "save-best":
        _save_best(args)
    elif args.subcommand == "play":
        _play(args)
    elif args.subcommand == "resume":
        _resume(args)
    else:
        raise AssertionError(f"unknown subcommand: {args.subcommand}")


# ============================================================================
# Shared setup
# ============================================================================

def _setup_voter():
    voter = LPD8VoteController()
    voter.connect()
    if voter.check_is_connected():
        return voter, "lpd8"
    print("Falling back to keyboard voter.")
    return KeyboardVoteController(), "keyboard"


def _pad_config_snapshot(pad_config):
    snap = {}
    if 'machine_filter' in pad_config:
        snap['machine_filter'] = sorted(pad_config['machine_filter'])
    if 'fixed_ccs' in pad_config:
        snap['fixed_ccs'] = {str(cc): v for cc, v in pad_config['fixed_ccs'].items()}
    if 'cc_value_caps' in pad_config:
        snap['cc_value_caps'] = {str(cc): list(rng)
                                 for cc, rng in pad_config['cc_value_caps'].items()}
    return snap


def _setup_pad(pad):
    """Load canonical params + pad config; return (canonical, evolved, fixed, machines, pad_config)."""
    canonical_params = AnalogRytmParameterCSVReader().get_parameter_collection()
    full_machine_palette = AnalogRytmMachineSelector.avail_machines_by_channel[pad]
    pad_config = get_pad_config(pad)
    evolved_params, fixed_values, machines = apply_pad_config(
        canonical_params, full_machine_palette, pad_config,
    )
    return canonical_params, evolved_params, fixed_values, machines, pad_config


def _ensure_deap_classes():
    if not hasattr(creator, "FitnessMax"):
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMax)


def _print_champion(pad, midi_channel, hof, evolved_params, machines):
    if not hof:
        print("No champion produced.")
        return
    best = hof[0]
    champion_machine = machines[best[0]]
    print("\n=== CHAMPION ===")
    print(f"Pad: {pad}  (sent on MIDI channel {midi_channel})")
    print(f"Machine number: {champion_machine}")
    print(f"Fitness: {best.fitness.values[0]}")
    print(f"Evolved CC values:")
    for p, v in zip(evolved_params, list(best)[1:]):
        print(f"  CC {p.cc:3d} = {v:3d}  ({p.name})")


# ============================================================================
# Subcommand: run
# ============================================================================

def _run(args):
    random.seed(args.seed)

    midi_connect = MidiConnection('Elektron Analog Rytm MKII')
    assert midi_connect.check_is_connected(), "Rytm not connected — aborting."

    voter, voter_kind = _setup_voter()

    canonical_params, evolved_params, fixed_values, machines, pad_config = \
        _setup_pad(args.pad)
    bounds = build_bounds(machines, evolved_params)

    print(
        f"Pad {args.pad} (MIDI ch {args.midi_channel}): "
        f"{len(machines)}/{len(AnalogRytmMachineSelector.avail_machines_by_channel[args.pad])} machines, "
        f"{len(evolved_params)} evolved + {len(fixed_values)} fixed CCs "
        f"(genome length {len(bounds)}), seed={args.seed}"
    )

    if args.no_log:
        run_dir = None
        gen_fh = contextlib.nullcontext()
        vote_fh = contextlib.nullcontext()
    else:
        run_dir = make_run_dir(Path("runs"), pad=args.pad)
        write_config(run_dir, {
            "pad": args.pad,
            "midi_channel": args.midi_channel,
            "pop_size": args.pop_size,
            "generations": args.generations,
            "mutation_rate": args.mutation_rate,
            "crossover_rate": args.crossover_rate,
            "mutation_indpb": args.mutation_indpb,
            "tournament_size": args.tournament_size,
            "seed": args.seed,
            "rytm_port": str(midi_connect),
            "voter": voter_kind,
            "pad_config": _pad_config_snapshot(pad_config),
        })
        gen_fh = (run_dir / "generations.jsonl").open("w")
        vote_fh = (run_dir / "votes.jsonl").open("w")
        print(f"Logging to {run_dir}")

    _ensure_deap_classes()

    toolbox = base.Toolbox()
    toolbox.register("individual", make_individual, bounds, creator.Individual)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", bounded_mutate, bounds=bounds, indpb=args.mutation_indpb)
    toolbox.register("select", tools.selTournament, tournsize=args.tournament_size)

    hof = tools.HallOfFame(1)
    evolved_ccs = [p.cc for p in evolved_params]

    def _replay():
        if not hof:
            print("[replay] no champion yet — vote on at least one candidate first.")
            return
        champion = hof[0]
        machine_num, params = build_params_for_individual(
            champion, machines, canonical_params, evolved_ccs, fixed_values,
        )
        print(f"[replay] champion: machine {machine_num}, fitness "
              f"{champion.fitness.values[0]}")
        send_individual(midi_connect, args.midi_channel, machine_num, params)

    state = {'gen': 0, 'eval_idx': 0}

    def _vote_logger(**row):
        if not args.no_log:
            log_vote(vote_fh, **row)

    toolbox.register(
        "evaluate",
        make_evaluate(
            midi_connect, args.midi_channel, voter, machines,
            canonical_params, evolved_params, fixed_values,
            state=state, vote_logger=_vote_logger, on_replay=_replay,
        ),
    )

    with gen_fh, vote_fh:
        try:
            pop = _make_initial_population(
                toolbox, args.pop_size, args.seed_from_patch,
                machines, evolved_ccs, fixed_values, args.pad,
            )

            invalid = [ind for ind in pop if not ind.fitness.valid]
            for ind in invalid:
                ind.fitness.values = toolbox.evaluate(ind)
            hof.update(pop)
            _log_gen_to_fh(gen_fh, args.no_log, 0, pop, n_evaluated=len(invalid))

            for gen in range(1, args.generations + 1):
                state['gen'] = gen
                state['eval_idx'] = 0

                offspring = algorithms.varOr(
                    pop, toolbox,
                    lambda_=args.pop_size,
                    cxpb=args.crossover_rate,
                    mutpb=args.mutation_rate,
                )
                invalid = [ind for ind in offspring if not ind.fitness.valid]
                for ind in invalid:
                    ind.fitness.values = toolbox.evaluate(ind)
                hof.update(offspring)
                pop[:] = toolbox.select(pop + offspring, k=args.pop_size)
                _log_gen_to_fh(gen_fh, args.no_log, gen, pop, n_evaluated=len(invalid))

        except KeyboardInterrupt:
            print(f"\nInterrupted at gen {state['gen']}.")

        _print_champion(args.pad, args.midi_channel, hof, evolved_params, machines)
        if run_dir is not None:
            print(f"Run dir: {run_dir}")


def _make_initial_population(toolbox, pop_size, seed_from_patch,
                              machines, evolved_ccs, fixed_values, pad):
    """Build the gen-0 population. If seed_from_patch is set, one slot is the
    decoded patch and the rest are random."""
    if not seed_from_patch:
        return toolbox.population(n=pop_size)
    patch_path = Path("patches") / f"{seed_from_patch}.json"
    patch = patches.load(patch_path)
    if patch["pad"] != pad:
        print(f"[seed-from-patch] WARNING: patch pad {patch['pad']} != current pad {pad}")
    seeded, dropped = patches.to_individual(patch, machines, evolved_ccs, creator.Individual)
    # Filter dropped against the caller's fixed CCs — those are expected drops.
    surprising = {cc: v for cc, v in dropped.items() if cc not in fixed_values}
    if surprising:
        print(f"[seed-from-patch] dropped CCs not in current evolved or fixed: "
              f"{sorted(surprising)}")
    rest = [toolbox.individual() for _ in range(pop_size - 1)]
    return [seeded] + rest


def _log_gen_to_fh(fh, no_log, gen, pop, n_evaluated):
    fits = [ind.fitness.values[0] for ind in pop if ind.fitness.valid]
    if not fits:
        return
    best_idx = max(range(len(pop)), key=lambda i: pop[i].fitness.values[0])
    if no_log:
        print(f"  gen {gen}: best={max(fits)} avg={sum(fits)/len(fits):.2f} "
              f"min={min(fits)} n_evaluated={n_evaluated}")
        return
    log_generation(
        fh,
        gen=gen,
        best_fitness=max(fits),
        avg_fitness=sum(fits) / len(fits),
        min_fitness=min(fits),
        best_individual=list(pop[best_idx]),
        n_evaluated=n_evaluated,
    )


# ============================================================================
# Subcommand: save-best
# ============================================================================

def _save_best(args):
    run_dir = Path(args.run_dir)
    assert run_dir.is_dir(), f"not a directory: {run_dir}"

    config = json.loads((run_dir / "config.json").read_text())
    pad = config["pad"]
    midi_channel = config["midi_channel"]

    canonical_params, evolved_params, fixed_values, machines, _ = _setup_pad(pad)
    evolved_ccs = [p.cc for p in evolved_params]

    champion_row = read_last_generation(run_dir)
    individual = champion_row["best_individual"]
    machine_num, params = build_params_for_individual(
        individual, machines, canonical_params, evolved_ccs, fixed_values,
    )
    machine_name = patches.machine_name_for(pad, machine_num)

    name = args.name or _auto_patch_name(run_dir, champion_row["best_fitness"])
    patch = patches.from_individual(
        pad=pad, midi_channel=midi_channel,
        machine_num=machine_num, machine_name=machine_name,
        params=params, fitness=champion_row["best_fitness"],
        source={
            "run_dir": str(run_dir),
            "generation": champion_row["gen"],
        },
    )
    patch["name"] = name

    out_dir = Path("patches")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.json"
    patches.save(out_path, patch)
    print(f"Saved {out_path}  (machine {machine_num} '{machine_name}', "
          f"fitness {champion_row['best_fitness']})")


def _auto_patch_name(run_dir, fitness):
    return f"{run_dir.name}-fit{int(fitness)}"


# ============================================================================
# Subcommand: play
# ============================================================================

def _play(args):
    patch_path = Path("patches") / f"{args.patch_name}.json"
    patch = patches.load(patch_path)

    midi_connect = MidiConnection('Elektron Analog Rytm MKII')
    assert midi_connect.check_is_connected(), "Rytm not connected — aborting."

    params = ParameterCollection()
    for p in patch["parameters"]:
        params.add_parameter(Parameter(
            cc=p["cc"], value=int(p["value"]),
            value_min=0, value_max=127,
            name=p.get("name", "n/a"),
        ))

    print(f"Playing patch '{patch['name']}'  machine {patch['machine_number']} "
          f"('{patch.get('machine_name', '?')}') on MIDI ch {patch['midi_channel']}")
    send_individual(midi_connect, patch["midi_channel"],
                    patch["machine_number"], params)


# ============================================================================
# Subcommand: resume
# ============================================================================

def _resume(args):
    run_dir = Path(args.run_dir)
    assert run_dir.is_dir(), f"not a directory: {run_dir}"

    config = json.loads((run_dir / "config.json").read_text())
    pad = config["pad"]
    midi_channel = config["midi_channel"]
    pop_size = config["pop_size"]
    n_more_generations = args.generations if args.generations is not None \
        else config["generations"]
    crossover_rate = config["crossover_rate"]
    mutation_rate = config["mutation_rate"]
    mutation_indpb = config["mutation_indpb"]
    tournament_size = config["tournament_size"]
    seed = config["seed"]

    random.seed(seed)

    midi_connect = MidiConnection('Elektron Analog Rytm MKII')
    assert midi_connect.check_is_connected(), "Rytm not connected — aborting."

    voter, _ = _setup_voter()

    canonical_params, evolved_params, fixed_values, machines, _ = _setup_pad(pad)
    bounds = build_bounds(machines, evolved_params)
    evolved_ccs = [p.cc for p in evolved_params]

    champion_row = read_last_generation(run_dir)
    last_gen = champion_row["gen"]

    print(f"Resuming {run_dir} from gen {last_gen} "
          f"(champion fitness {champion_row['best_fitness']}). "
          f"Adding {n_more_generations} more generations.")

    _ensure_deap_classes()

    toolbox = base.Toolbox()
    toolbox.register("individual", make_individual, bounds, creator.Individual)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", bounded_mutate, bounds=bounds, indpb=mutation_indpb)
    toolbox.register("select", tools.selTournament, tournsize=tournament_size)

    hof = tools.HallOfFame(1)

    def _replay():
        if not hof:
            return
        champion = hof[0]
        machine_num, params = build_params_for_individual(
            champion, machines, canonical_params, evolved_ccs, fixed_values,
        )
        send_individual(midi_connect, midi_channel, machine_num, params)

    state = {'gen': last_gen + 1, 'eval_idx': 0}
    vote_fh = (run_dir / "votes.jsonl").open("a")
    gen_fh = (run_dir / "generations.jsonl").open("a")

    def _vote_logger(**row):
        log_vote(vote_fh, **row)

    toolbox.register(
        "evaluate",
        make_evaluate(
            midi_connect, midi_channel, voter, machines,
            canonical_params, evolved_params, fixed_values,
            state=state, vote_logger=_vote_logger, on_replay=_replay,
        ),
    )

    # Seed gen-0 with champion + random rest.
    champion_individual = creator.Individual(champion_row["best_individual"])
    champion_individual.fitness.values = (champion_row["best_fitness"],)
    pop = [champion_individual] + [toolbox.individual()
                                   for _ in range(pop_size - 1)]

    with gen_fh, vote_fh:
        try:
            invalid = [ind for ind in pop if not ind.fitness.valid]
            for ind in invalid:
                ind.fitness.values = toolbox.evaluate(ind)
            hof.update(pop)
            _log_gen_to_fh(gen_fh, False, last_gen + 1, pop, n_evaluated=len(invalid))

            for gen_offset in range(1, n_more_generations + 1):
                state['gen'] = last_gen + 1 + gen_offset
                state['eval_idx'] = 0

                offspring = algorithms.varOr(
                    pop, toolbox,
                    lambda_=pop_size, cxpb=crossover_rate, mutpb=mutation_rate,
                )
                invalid = [ind for ind in offspring if not ind.fitness.valid]
                for ind in invalid:
                    ind.fitness.values = toolbox.evaluate(ind)
                hof.update(offspring)
                pop[:] = toolbox.select(pop + offspring, k=pop_size)
                _log_gen_to_fh(gen_fh, False, state['gen'], pop,
                               n_evaluated=len(invalid))

        except KeyboardInterrupt:
            print(f"\nInterrupted at gen {state['gen']}.")

        _print_champion(pad, midi_channel, hof, evolved_params, machines)
        print(f"Run dir: {run_dir}")


if __name__ == "__main__":
    run()
