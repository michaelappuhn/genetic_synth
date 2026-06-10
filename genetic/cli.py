"""CLI surface for `python -m genetic.main`."""

import argparse
import time


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="genetic.main",
        description="Run the genetic-algorithm sound-design loop against the Rytm.",
    )
    p.add_argument("--pad", type=int, default=0,
                   help="Which Rytm pad/voice to evolve. Drives pad_config + machine palette.")
    p.add_argument("--midi-channel", type=int, default=None,
                   help="MIDI channel for sends. Defaults to --pad. Override when "
                        "Rytm routing reassigns pads (e.g. ch10 triggering pad 11).")
    p.add_argument("--pop-size", type=int, default=4)
    p.add_argument("--generations", type=int, default=5)
    p.add_argument("--mutation-rate", type=float, default=0.3,
                   help="Probability an offspring gets mutated (DEAP mutpb).")
    p.add_argument("--crossover-rate", type=float, default=0.5,
                   help="Probability of crossover (DEAP cxpb).")
    p.add_argument("--mutation-indpb", type=float, default=0.15,
                   help="Per-gene resample probability inside bounded_mutate.")
    p.add_argument("--tournament-size", type=int, default=2)
    p.add_argument("--seed", type=int, default=None,
                   help="RNG seed. Default: int(time()). Logged in config.json.")
    p.add_argument("--no-log", action="store_true",
                   help="Skip run-directory creation. For smoke tests.")
    args = p.parse_args(argv)
    if args.midi_channel is None:
        args.midi_channel = args.pad
    if args.seed is None:
        args.seed = int(time.time())
    return args
