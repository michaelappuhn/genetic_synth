# M3 — Persistence: implementation design

## Context

M2 ended with the GA producing a usable champion at the end of each run, logged to `runs/.../generations.jsonl`. But the champion is still just a row in a file — you can't reload it next session, you can't re-hear it without re-running, and a stopped run is dead. This milestone makes GA output durable: champions become named, reloadable JSON patches; a stopped run can be picked up where it left off; and a saved patch can seed a new run for "this is close, evolve around it" workflows.

This design implements `docs/specs/M3-persistence.md` with the architectural decisions made during brainstorming on 2026-06-10. The outcome is four CLI verbs (`run`, `save-best`, `play`, `resume`), a new `genetic/patches.py` module, and the cleanup carryover from M2's final review.

## Design

### CLI restructure: argparse subcommands with `run` default

M2's CLI is one command with flags. M3 introduces four verbs. To keep `python -m genetic.main --pad 0` working unchanged (M2 muscle memory), `parse_args` inspects `argv` before delegating to argparse:

```python
KNOWN_SUBCOMMANDS = {"run", "save-best", "play", "resume"}

def parse_args(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Inject 'run' if the first token isn't an explicit subcommand.
    # Empty argv, a flag (-x/--x), or any non-subcommand token → run.
    if not argv or argv[0] not in KNOWN_SUBCOMMANDS:
        argv.insert(0, "run")
    # ... build parser with subparsers, parse argv
```

Each subparser owns its own flag set. `run` carries everything M2's `parse_args` has today, plus `--seed-from-patch`. `save-best`/`play`/`resume` take a positional path or patch name plus a few specific flags.

Module structure:

- `genetic/cli.py` — restructured around `add_subparsers()`. Exposes `parse_args(argv=None) -> Namespace` with `args.subcommand` set to the verb chosen.
- `genetic/main.py` — `run(argv=None)` dispatches on `args.subcommand` to `_run(args)` / `_save_best(args)` / `_play(args)` / `_resume(args)`. M2's driver becomes `_run()`.

### File layout

**New:**
- `genetic/patches.py` — patch I/O + DEAP individual conversion. Pure data; no MIDI, no DEAP setup.
- `tests/test_patches.py` — device-free round-trip tests.

**Modified:**
- `genetic/cli.py` — subparser restructure
- `genetic/main.py` — verb dispatch + four handlers (`_run` is the existing M2 driver renamed)
- `genetic/logging.py` — add `read_last_generation(run_dir)`; harden `make_run_dir` against collisions
- `tests/test_logging.py` — extend for collision + read-last
- `tests/test_cli.py` — extend for subcommand parsing
- `user_interface/voter.py` — delete pre-M0 dead code
- `.gitignore` — add `patches/`
- `README.md`, `CLAUDE.md` — document the new verbs

### Patch format

`patches/<name>.json`:

```json
{
  "version": 1,
  "name": "kraken-bd-acoustic",
  "pad": 0,
  "midi_channel": 0,
  "machine_number": 30,
  "machine_name": "bd acoustic",
  "parameters": [
    {"cc": 16, "value": 127, "name": "Source Level"},
    {"cc": 17, "value": 64, "name": "Tune"}
  ],
  "fitness": 8.0,
  "source": {
    "run_dir": "runs/2026-06-10-1422-pad0",
    "generation": 4,
    "eval_idx": 2
  }
}
```

Decisions:
- **`pad` + `midi_channel`** (not the spec's `channel`) — matches the M2 split. `play` sends on `midi_channel`; the patch records both for reference.
- **`parameters` is the full canonical CC enumeration** (evolved + fixed). `play` just iterates and sends every line. Order-independent, robust to CSV reordering, robust to pad_config drift.
- **`version: 1`** lets later milestones add fields without breaking old patches.
- **Filename is source of truth** — `name` field is for humans reading the JSON.

### `genetic/patches.py` API

```python
def save(path: Path, individual_data: dict) -> None
def load(path: Path) -> dict
def from_individual(individual, pad, midi_channel, machine_num, machine_name,
                    params, fitness, source) -> dict
def to_individual(patch: dict, machines: list, evolved_ccs: list,
                  individual_cls) -> tuple[Any, dict[int, int]]
```

`from_individual` takes the decoded send-ready state and produces the patch dict. `to_individual` does the inverse: given a loaded patch + the current pad's `machines` list + `evolved_ccs` order, produces a DEAP Individual `[machine_idx, cc_val_0, ...]` and a dict of CCs that the patch carried but aren't in evolved_ccs (so the caller can warn).

**Edge case — machine not in current pad's filter:** `to_individual` raises `ValueError("patch machine {N} ({name}) not available in pad {pad}'s filter")`. Caller surfaces a clear error.

**Edge case — patch CC set vs current evolved_ccs differs:** `to_individual` uses patch values for CCs that ARE in evolved_ccs and silently drops the rest (they'll be set by `fixed_values` at evaluate time). Returns a dict of dropped CCs so the caller can print a one-line warning.

### `save-best` handler

```bash
python -m genetic.main save-best <run-dir> [--name <patch-name>]
```

1. `read_last_generation(<run-dir>)` returns the line with highest `best_fitness` (tiebreak: latest gen).
2. Load `<run-dir>/config.json` → `pad`, `midi_channel`, `seed`, `pad_config` snapshot.
3. Reconstruct `machines`, `evolved_params`, `fixed_values` from canonical CSV + saved pad_config snapshot. (Same call chain `_run` uses; lift into a `_setup_pad(args.pad, pad_config_snapshot)` helper.)
4. `build_params_for_individual(best_individual, ...)` (M2 helper) → `(machine_num, params)`.
5. Look up `machine_name` from a `RYTM_MACHINE_NAMES` constant in `genetic/patches.py`. Machine names are NOT in `rytm-limited.csv`; the table is derived from `docs/rytm-machine-ranges.csv`'s `machine` column (~36 entries: `{0: "bd hard", 1: "bd classic", ..., 30: "bd acoustic", ...}`). One-time data entry; doesn't change unless Elektron ships new machines.
6. `patches.from_individual(...)` → patch dict.
7. Write `patches/<name>.json` via `patches.save()`. Auto-name from run dir basename + fitness if `--name` omitted (e.g. `2026-06-10-1422-pad0-fit8.json`).

### `play` handler

```bash
python -m genetic.main play <patch-name>
```

1. `patches.load(Path("patches") / f"{patch_name}.json")`.
2. Open Rytm connection.
3. Build a `ParameterCollection` from the patch's `parameters` array (one `Parameter` per CC).
4. Call `send_individual(midi_connect, patch["midi_channel"], patch["machine_number"], params)` (the M2 helper). Sends machine CC + every param CC + a trig.
5. Exit. No GA, no logging.

### `resume` handler

```bash
python -m genetic.main resume <run-dir> [--generations N] [--override]
```

Per the "champion + random fill" decision:

1. Read config.json from `<run-dir>`.
2. If any CLI flags conflict with config.json values and `--override` is NOT set, refuse with a list of conflicts.
3. `read_last_generation()` → champion (machine_idx + CC values from `best_individual`).
4. Build initial population: `[Individual(champion)] + [Individual(random)] * (pop_size - 1)`. Champion gets fitness from the log; the rest evaluate normally.
5. Reopen `<run-dir>/generations.jsonl` and `<run-dir>/votes.jsonl` in **append mode**. Continue gen-numbering from `last_gen + 1`.
6. Run the same inline mu+lambda loop M2 uses, but with `--generations` (or the original from config.json) more iterations.

The "champion + random fill" is the same shape as `--seed-from-patch`; `_resume` is implemented as a thin wrapper that builds a "virtual patch" from the run dir's champion and delegates.

### `--seed-from-patch` flag on `run`

```bash
python -m genetic.main run --pad 0 --seed-from-patch <patch-name> --generations 10
```

1. Normal `_run` setup (parse, seed RNG, make new run dir, DEAP toolbox).
2. After toolbox is built but before initial pop creation: load patch, `to_individual(patch, machines, evolved_ccs, creator.Individual)`.
3. Refuse if machine not in filter.
4. Build initial pop: `[seeded] + [toolbox.individual() for _ in range(pop_size - 1)]`.
5. Print warning if patch had CCs that aren't in current evolved_ccs.
6. Run normally.

### `make_run_dir` collision

`genetic/logging.py:make_run_dir()`:

```python
def make_run_dir(base, pad, now=None):
    now = now or datetime.now()
    stem = f"{now.strftime('%Y-%m-%d-%H%M')}-pad{pad}"
    for suffix in [""] + [f"-{i}" for i in range(1, 10)]:
        candidate = base / (stem + suffix)
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"10 runs in the same minute on pad {pad} — wait or pass --no-log")
```

Adds `-1`, `-2`, ..., `-9` suffix on collision. 10 hits is absurd; if you get there, raise loudly.

### `read_last_generation` helper

```python
def read_last_generation(run_dir: Path) -> dict
```

Reads `<run-dir>/generations.jsonl`, returns the line with highest `best_fitness` (parsed as JSON dict). Tiebreak: latest `gen`. Used by `save-best` and `resume`.

### `voter.py` cleanup

Delete:
- `def main()` (module-level)
- `class VotingSystem`
- `class VoteProcessor`
- `VoteController.give_instructions` (unused stub)
- `LPD8VoteController.give_instructions` (unused stub)
- `KeyboardVoteController.give_instructions` (unused stub)
- `def get_lpd8_port()` (module-level)
- `def lpd8_vote(port)` (module-level)
- `def vote(port)` (module-level)
- `if __name__ == "__main__": main()` block

Keep:
- `class VoteController` (abstract base)
- `class LPD8VoteController` (live; M2 path)
- `class KeyboardVoteController` (live; fallback path)
- `def keyboard_vote()` / `def keyboard_vote_instructions()` (called by `KeyboardVoteController.get_vote()` via recursion)

Net change: ~210 lines → ~120 lines.

### Testing

Device-free:

- **`tests/test_patches.py`** (new):
  - Round-trip: `from_individual` then `to_individual` produces the same individual.
  - `to_individual` raises when machine not in filter.
  - `to_individual` warns (via returned dropped-CCs dict) when patch carries CCs not in evolved_ccs.
  - File save/load round-trips a real patch dict.
- **`tests/test_logging.py`** (extend):
  - `make_run_dir` returns `-1` suffix when base name collides.
  - `make_run_dir` raises after 10 collisions.
  - `read_last_generation` returns the row with highest fitness across 3 mocked jsonl lines.
- **`tests/test_cli.py`** (extend):
  - Bare flags (no subcommand) parse as `run` subcommand.
  - `save-best <run-dir>` parses with `args.subcommand == "save-best"`.
  - Subcommand-specific flags don't leak across (e.g. `--name` is invalid for `play`).
- **`tests/test_voter.py`** (existing): should still pass after voter.py cleanup. No new tests.

Hardware:
- Run GA → save champion → `play` the patch → sounds identical to the original.
- Run GA, Ctrl-C → `resume` → continues from next gen with champion preserved.
- `run --seed-from-patch <name>` → first audition is the patch.

## Verification

```bash
source ./activate_virtualenv.sh

# Device-free tests pass
python -m unittest tests.test_parameters tests.test_logging tests.test_cli tests.test_voter tests.test_patches

# CLI surface — backward compat
python -m genetic.main --help                                # run subparser's help (sys.argv peek)
python -m genetic.main --pad 0 --generations 1 --no-log      # bare flags → run subcommand
python -m genetic.main run --help                            # explicit run --help
python -m genetic.main save-best --help
python -m genetic.main play --help
python -m genetic.main resume --help

# Save → play round-trip (manual hardware)
python -m genetic.main --pad 0 --generations 2
python -m genetic.main save-best runs/2026-*-pad0 --name test
ls patches/test.json
python -m genetic.main play test
# - Plays one trig, same sound as the champion at end of the GA run

# Resume (manual hardware)
python -m genetic.main resume runs/2026-*-pad0 --generations 2
# - Picks up from last gen, champion seeded, same run dir extended

# Seed-from-patch (manual hardware)
python -m genetic.main --pad 0 --seed-from-patch test --generations 2
# - First candidate played sounds identical to `play test`

# Collision behavior
mkdir -p runs/2026-06-10-1422-pad0   # simulate collision
python -m genetic.main --pad 0 --generations 0
ls runs/                              # second run uses -1 suffix
```

## Non-goals (deferred to later milestones or M3.5)

- SysEx kit dump to the Rytm — owned by M3.5 if it lands; M3 is JSON-only.
- Patch browser / GUI — out of scope forever (this is a CLI tool).
- Full-population resume — by design, "champion + random fill" is the resume mechanic. Use save-best + fresh run if you want explicit re-seeding from a different individual.
- Refactoring `KeyboardVoteController.get_vote()` to inline `keyboard_vote()` — deferred; the helper recursion works.
- Cross-version patch migration — M3 only reads `version: 1`. M3.5 (if added) introduces `version: 2` and a one-time migration script.
