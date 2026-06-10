from deap import base, creator, tools, algorithms

from synthesizer.midicontrol import MidiConnection, AnalogRytmMachineSelector
from synthesizer.parameters import AnalogRytmParameterCSVReader
from user_interface.voter import LPD8VoteController, KeyboardVoteController

from genetic.genome import apply_pad_config, build_bounds, make_individual, bounded_mutate
from genetic.pad_config import get_pad_config
from genetic.evaluate import make_evaluate


# Which Rytm voice/pad we're evolving. Indexes AnalogRytmMachineSelector.avail_machines_by_channel
# (0=BD, 1=SD, 2=RS/CP/BD, 3=BT, ..., 10=CY, 11=XT — see kits_10.md).
PAD = 0

# MIDI channel that pad's voice actually listens on. Defaults to PAD (1:1 mapping).
# Override when Rytm MIDI routing reassigns pads — e.g., set MIDI_CHANNEL = 10 if
# you've wired channel 0 to trigger pad 11 for external-device routing.
#MIDI_CHANNEL = PAD
MIDI_CHANNEL = 10

POPULATION = 4
GENERATIONS = 5
CXPB = 0.5
MUTPB = 0.3
INDPB = 0.15
TOURNSIZE = 2


def _setup_voter():
    voter = LPD8VoteController()
    voter.connect()
    if voter.check_is_connected():
        return voter
    print("Falling back to keyboard voter.")
    return KeyboardVoteController()


def run():
    midi_connect = MidiConnection('Elektron Analog Rytm MKII')
    assert midi_connect.check_is_connected(), "Rytm not connected — aborting."

    voter = _setup_voter()

    canonical_params = AnalogRytmParameterCSVReader().get_parameter_collection()
    full_machine_palette = AnalogRytmMachineSelector.avail_machines_by_channel[PAD]
    pad_config = get_pad_config(PAD)
    evolved_params, fixed_values, machines = apply_pad_config(
        canonical_params, full_machine_palette, pad_config,
    )
    bounds = build_bounds(machines, evolved_params)

    print(
        f"Pad {PAD}: {len(machines)}/{len(full_machine_palette)} machines, "
        f"{len(evolved_params)} evolved + {len(fixed_values)} fixed CCs "
        f"(genome length {len(bounds)})"
    )

    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMax)

    toolbox = base.Toolbox()
    toolbox.register("individual", make_individual, bounds, creator.Individual)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", bounded_mutate, bounds=bounds, indpb=INDPB)
    toolbox.register("select", tools.selTournament, tournsize=TOURNSIZE)
    toolbox.register(
        "evaluate",
        make_evaluate(
            midi_connect, MIDI_CHANNEL, voter, machines,
            canonical_params, evolved_params, fixed_values,
        ),
    )

    pop = toolbox.population(n=POPULATION)
    algorithms.eaSimple(pop, toolbox, cxpb=CXPB, mutpb=MUTPB, ngen=GENERATIONS, verbose=True)

    best = tools.selBest(pop, k=1)[0]
    champion_machine = machines[best[0]]
    champion_ccs = list(best[1:])
    print("\n=== CHAMPION ===")
    print(f"Pad: {PAD}  (sent on MIDI channel {MIDI_CHANNEL})")
    print(f"Machine number: {champion_machine}")
    print(f"Fitness: {best.fitness.values[0]}")
    print(f"Evolved CC values:")
    for p, v in zip(evolved_params, champion_ccs):
        print(f"  CC {p.cc:3d} = {v:3d}  ({p.name})")


if __name__ == "__main__":
    run()
