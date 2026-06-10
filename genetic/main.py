"""Driver: parse CLI, seed RNG, set up GA, run inline mu+lambda loop with logging."""

import contextlib
import random
from pathlib import Path

from deap import base, creator, tools, algorithms

from synthesizer.midicontrol import MidiConnection, AnalogRytmMachineSelector
from synthesizer.parameters import AnalogRytmParameterCSVReader
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
    make_run_dir, write_config, log_generation, log_vote,
)


def _setup_voter():
    voter = LPD8VoteController()
    voter.connect()
    if voter.check_is_connected():
        return voter, "lpd8"
    print("Falling back to keyboard voter.")
    return KeyboardVoteController(), "keyboard"


def _pad_config_snapshot(pad_config):
    """Make a JSON-serializable copy of pad_config for config.json."""
    snap = {}
    if 'machine_filter' in pad_config:
        snap['machine_filter'] = sorted(pad_config['machine_filter'])
    if 'fixed_ccs' in pad_config:
        snap['fixed_ccs'] = {str(cc): v for cc, v in pad_config['fixed_ccs'].items()}
    if 'cc_value_caps' in pad_config:
        snap['cc_value_caps'] = {str(cc): list(rng)
                                 for cc, rng in pad_config['cc_value_caps'].items()}
    return snap


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


def run(argv=None):
    args = parse_args(argv)
    random.seed(args.seed)

    midi_connect = MidiConnection('Elektron Analog Rytm MKII')
    assert midi_connect.check_is_connected(), "Rytm not connected — aborting."

    voter, voter_kind = _setup_voter()

    canonical_params = AnalogRytmParameterCSVReader().get_parameter_collection()
    full_machine_palette = AnalogRytmMachineSelector.avail_machines_by_channel[args.pad]
    pad_config = get_pad_config(args.pad)
    evolved_params, fixed_values, machines = apply_pad_config(
        canonical_params, full_machine_palette, pad_config,
    )
    bounds = build_bounds(machines, evolved_params)

    print(
        f"Pad {args.pad} (MIDI ch {args.midi_channel}): "
        f"{len(machines)}/{len(full_machine_palette)} machines, "
        f"{len(evolved_params)} evolved + {len(fixed_values)} fixed CCs "
        f"(genome length {len(bounds)}), seed={args.seed}"
    )

    # --- Run directory ---
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

    # --- DEAP setup ---
    if not hasattr(creator, "FitnessMax"):
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMax)

    toolbox = base.Toolbox()
    toolbox.register("individual", make_individual, bounds, creator.Individual)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", bounded_mutate, bounds=bounds, indpb=args.mutation_indpb)
    toolbox.register("select", tools.selTournament, tournsize=args.tournament_size)

    # --- Replay callback (closes over hof + per-evaluation context) ---
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

    # --- Evaluator with logging hooks ---
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

    # --- Inline mu+lambda loop ---
    with gen_fh, vote_fh:
        try:
            pop = toolbox.population(n=args.pop_size)

            # Gen 0: evaluate initial population
            invalid = [ind for ind in pop if not ind.fitness.valid]
            for ind in invalid:
                ind.fitness.values = toolbox.evaluate(ind)
            hof.update(pop)
            _log_gen_to_fh(gen_fh, args.no_log, 0, pop, n_evaluated=len(invalid))

            # Gens 1..N
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


if __name__ == "__main__":
    run()
