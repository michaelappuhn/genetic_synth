"""CLI surface for `python -m genetic.main`.

Subcommands: run (default), save-best, play, resume. Bare flags or no args
default to `run` for M2 backward compatibility.
"""

import argparse
import sys
import time


KNOWN_SUBCOMMANDS = {"run", "save-best", "play", "resume"}


def parse_args(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Inject 'run' if the first token isn't an explicit subcommand. Empty argv
    # or a flag (-x/--x) implies the user wants the default `run` behavior.
    # Exception: bare -h/--help should show the parent (subcommand list) help.
    _bare_help = argv == ["-h"] or argv == ["--help"]
    if not _bare_help and (not argv or argv[0] not in KNOWN_SUBCOMMANDS):
        argv.insert(0, "run")

    p = argparse.ArgumentParser(
        prog="genetic.main",
        description="Run the GA, save / replay champions, resume runs.",
    )
    subparsers = p.add_subparsers(dest="subcommand", required=True)

    _add_run_parser(subparsers)
    _add_save_best_parser(subparsers)
    _add_play_parser(subparsers)
    _add_resume_parser(subparsers)

    args = p.parse_args(argv)

    if args.subcommand == "run":
        if args.midi_channel is None:
            args.midi_channel = args.pad
        if args.seed is None:
            args.seed = int(time.time())

    return args


def _add_run_parser(subparsers):
    r = subparsers.add_parser("run", help="Run a GA session (default).")
    r.add_argument("--pad", type=int, default=0,
                   help="Which Rytm pad/voice to evolve.")
    r.add_argument("--midi-channel", type=int, default=None,
                   help="MIDI channel for sends. Defaults to --pad.")
    r.add_argument("--pop-size", type=int, default=4)
    r.add_argument("--generations", type=int, default=5)
    r.add_argument("--mutation-rate", type=float, default=0.3)
    r.add_argument("--crossover-rate", type=float, default=0.5)
    r.add_argument("--mutation-indpb", type=float, default=0.15)
    r.add_argument("--tournament-size", type=int, default=2)
    r.add_argument("--seed", type=int, default=None,
                   help="RNG seed. Default: int(time()).")
    r.add_argument("--no-log", action="store_true",
                   help="Skip run-directory creation.")
    r.add_argument("--seed-from-patch", type=str, default=None,
                   help="Patch name to use as one initial population member.")


def _add_save_best_parser(subparsers):
    s = subparsers.add_parser("save-best",
                              help="Save the champion of a run as a patch.")
    s.add_argument("run_dir", type=str, help="Path to runs/<dir>")
    s.add_argument("--name", type=str, default=None,
                   help="Patch name. Auto-named from run dir if omitted.")


def _add_play_parser(subparsers):
    pl = subparsers.add_parser("play", help="Audition a saved patch on the Rytm.")
    pl.add_argument("patch_name", type=str, help="Patch name (without .json).")


def _add_resume_parser(subparsers):
    rs = subparsers.add_parser("resume", help="Resume a stopped run.")
    rs.add_argument("run_dir", type=str, help="Path to runs/<dir>")
    rs.add_argument("--generations", type=int, default=None,
                    help="Generations to run. Defaults to original from config.json.")
    rs.add_argument("--override", action="store_true",
                    help="Permit CLI flags to override config.json.")
