# M3 — Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GA output durable. Save champions as named JSON patches, replay them without a GA run, resume a stopped run, seed a new run from a saved patch. Plus the M2-final-review cleanup carryovers (voter.py dead code, make_run_dir collisions).

**Architecture:** Add `genetic/patches.py` for patch I/O + DEAP individual conversion. Restructure `genetic/cli.py` around `argparse` subparsers (`run` default, plus `save-best` / `play` / `resume`). Route from `main.py` to four per-subcommand handlers; M2's driver becomes `_run`. Extend `genetic/logging.py` with `read_last_generation()` and a collision-suffix `make_run_dir`. Delete pre-M0 dead code from `user_interface/voter.py`.

**Tech Stack:** Python 3.9, stdlib (`argparse`, `json`, `pathlib`, `datetime`, `random`), DEAP, mido. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-10-m3-persistence-design.md`

---

### Task 0: Baseline check + gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Confirm M2 device-free tests pass on current HEAD**

```bash
cd /Users/michaelappuhn/Dev/genetic_algorithm
source ./activate_virtualenv.sh
python -m unittest tests.test_parameters tests.test_logging tests.test_cli tests.test_voter
```

Expected: 34 tests pass, `OK`. If anything fails, STOP and report — M3 must not start on a broken baseline.

- [ ] **Step 2: Add `patches/` to .gitignore**

Current `.gitignore`:

```
*.swp
.ipynb_checkpoints
runs/
```

Use Edit to make the final content:

```
*.swp
.ipynb_checkpoints
runs/
patches/
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "M3: ignore patches/ directory"
```

---

### Task 1: voter.py cleanup — delete pre-M0 dead code

The file has ~210 lines but only `LPD8VoteController` (M2 path) and `KeyboardVoteController` (fallback) are live. Delete the pre-M0 module-level code plus unused stubs. Keep the two module helpers (`keyboard_vote()` / `keyboard_vote_instructions()`) that `KeyboardVoteController.get_vote()` calls via recursion.

**Files:**
- Modify: `user_interface/voter.py`
- Test: `tests/test_voter.py` (existing tests must still pass after cleanup)

- [ ] **Step 1: Replace `user_interface/voter.py` contents**

Read the file first to satisfy the Write tool prerequisite, then replace with EXACTLY this content:

```python
import sys
import time

import mido


class VoteController():
    def get_vote(self):
        pass


class LPD8VoteController(VoteController):
    is_connected = False

    def connect(self):
        ins = mido.get_input_names()
        if ('LPD8' in ins):
            print("LPD8 connected")
            port = mido.open_input('LPD8')
            self.is_connected = True
            self.port = port
        else:
            self.message_failure()

    def message_failure(self):
        print("LPD8 port not connected.")
        print("Using keyboard instead of external controller.")

    def check_is_connected(self):
        if (self.is_connected != False):
            return True
        else:
            return False

    def get_vote(self, on_replay=None, replay_cc=1):
        while True:
            for msg in self.port.iter_pending():
                if msg.type == 'note_on' and 36 <= msg.note <= 43:
                    return msg.note - 35   # 36→1, 43→8
                if msg.type == 'note_on':
                    print("Your LPD8 should be on Prog1!")
                    continue
                if msg.type == 'control_change' and msg.control == replay_cc:
                    if on_replay is not None:
                        on_replay()
            time.sleep(0.01)


class KeyboardVoteController(VoteController):

    def get_vote(self, on_replay=None, replay_cc=1):
        # Keyboard fallback has no replay support — accept the params for
        # signature parity with LPD8VoteController and ignore them.
        _ = on_replay, replay_cc
        got_info = False
        try:
            vote = int(input("Please rate the pad between 1-8: "))
            if (vote > 0 and vote <= 8):
                got_info = True
            else:
                keyboard_vote_instructions()

        except KeyboardInterrupt:
            sys.exit(0)
        except:
            keyboard_vote_instructions()
            got_info = False

        if (got_info == True):
            return vote
        else:
            return keyboard_vote()


def keyboard_vote_instructions():
    print("Needs to be an integer between 1-8.")


def keyboard_vote():
    got_info = False
    try:
        vote = int(input("Please rate the pad between 1-8: "))
        if (vote > 0 and vote <= 8):
            got_info = True
        else:
            keyboard_vote_instructions()

    except KeyboardInterrupt:
        sys.exit(0)
    except:
        keyboard_vote_instructions()
        got_info = False

    if (got_info == True):
        return vote
    else:
        return keyboard_vote()
```

Deleted: `VotingSystem`, `VoteProcessor`, `give_instructions()` stubs on all three classes, `get_lpd8_port()`, `lpd8_vote()`, `vote()`, the module-level `main()` and its `if __name__ == "__main__"` block.

- [ ] **Step 2: Run existing voter tests + the rest of the device-free suite**

```bash
python -m unittest tests.test_voter tests.test_parameters tests.test_logging tests.test_cli -v
```

Expected: 34 tests pass, `OK`. The five `tests.test_voter` tests in particular must all pass — they exercise the LPD8 path.

- [ ] **Step 3: Verify imports from main.py still work**

```bash
python -c "from user_interface.voter import LPD8VoteController, KeyboardVoteController; print('ok')"
python -c "from genetic.main import run; print('ok')"
```

Both should print `ok`.

- [ ] **Step 4: Commit**

```bash
git add user_interface/voter.py
git commit -m "M3: delete pre-M0 dead code from voter.py"
```

---

### Task 2: logging.py extensions — collision suffix + read_last_generation

Two changes to `genetic/logging.py`:
1. `make_run_dir` retries with `-1`, `-2`, ..., `-9` suffix on `FileExistsError`. Raises after 10 collisions.
2. New `read_last_generation(run_dir)` returns the JSONL row with the highest `best_fitness` (tiebreak: latest gen).

**Files:**
- Modify: `genetic/logging.py`
- Test: `tests/test_logging.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_logging.py` (before the `if __name__ == "__main__":` line):

```python
class TestMakeRunDirCollision(unittest.TestCase):
    def test_collision_uses_dash_one_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            first = make_run_dir(base, pad=0, now=ts)
            second = make_run_dir(base, pad=0, now=ts)
            self.assertEqual(first.name, "2026-06-10-1422-pad0")
            self.assertEqual(second.name, "2026-06-10-1422-pad0-1")
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())

    def test_collision_increments_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            d0 = make_run_dir(base, pad=0, now=ts)
            d1 = make_run_dir(base, pad=0, now=ts)
            d2 = make_run_dir(base, pad=0, now=ts)
            self.assertEqual(d2.name, "2026-06-10-1422-pad0-2")

    def test_collision_raises_after_ten_tries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            for _ in range(10):
                make_run_dir(base, pad=0, now=ts)
            with self.assertRaises(RuntimeError):
                make_run_dir(base, pad=0, now=ts)


class TestReadLastGeneration(unittest.TestCase):
    def test_returns_row_with_highest_best_fitness(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            path = run_dir / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=3.0, avg_fitness=2.0,
                               min_fitness=1.0, best_individual=[0], n_evaluated=4)
                log_generation(fh, gen=1, best_fitness=7.0, avg_fitness=4.0,
                               min_fitness=2.0, best_individual=[1, 64], n_evaluated=4)
                log_generation(fh, gen=2, best_fitness=5.0, avg_fitness=3.5,
                               min_fitness=1.0, best_individual=[2], n_evaluated=4)
            row = read_last_generation(run_dir)
            self.assertEqual(row["gen"], 1)
            self.assertEqual(row["best_fitness"], 7.0)
            self.assertEqual(row["best_individual"], [1, 64])

    def test_tiebreak_picks_latest_gen(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            path = run_dir / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=5.0, avg_fitness=3.0,
                               min_fitness=1.0, best_individual=[1], n_evaluated=4)
                log_generation(fh, gen=1, best_fitness=5.0, avg_fitness=4.0,
                               min_fitness=2.0, best_individual=[2], n_evaluated=4)
            row = read_last_generation(run_dir)
            self.assertEqual(row["gen"], 1)   # tiebreak: latest gen wins
```

Add the import at the top of the test file:

```python
from genetic.logging import (
    make_run_dir,
    write_config,
    log_generation,
    log_vote,
    read_last_generation,
)
```

(Replace the existing `from genetic.logging import (...)` block.)

- [ ] **Step 2: Run tests, verify they fail**

```bash
python -m unittest tests.test_logging -v
```

Expected: `TestMakeRunDirCollision` raises `FileExistsError` (not the suffix); `TestReadLastGeneration` errors with `ImportError: cannot import name 'read_last_generation'`.

- [ ] **Step 3: Update `genetic/logging.py`**

Read the file first. Then replace the entire contents with:

```python
"""Run-directory and JSONL helpers. Pure file I/O — no GA knowledge."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def make_run_dir(base: Path, pad: int, now: Optional[datetime] = None) -> Path:
    now = now or datetime.now()
    stem = f"{now.strftime('%Y-%m-%d-%H%M')}-pad{pad}"
    for suffix in [""] + [f"-{i}" for i in range(1, 10)]:
        candidate = base / (stem + suffix)
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(
        f"10 runs in the same minute on pad {pad} — wait one minute or pass --no-log"
    )


def write_config(run_dir: Path, config: dict) -> None:
    (run_dir / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True))


def log_generation(fh, gen, best_fitness, avg_fitness, min_fitness,
                   best_individual, n_evaluated):
    fh.write(json.dumps({
        "gen": gen,
        "best_fitness": best_fitness,
        "avg_fitness": avg_fitness,
        "min_fitness": min_fitness,
        "best_individual": list(best_individual),
        "n_evaluated": n_evaluated,
    }) + "\n")
    fh.flush()


def log_vote(fh, gen, eval_idx, machine, evolved_ccs, fixed_ccs, vote, timestamp_iso):
    fh.write(json.dumps({
        "gen": gen,
        "eval_idx": eval_idx,
        "machine": machine,
        "evolved_ccs": evolved_ccs,
        "fixed_ccs": fixed_ccs,
        "vote": vote,
        "timestamp_iso": timestamp_iso,
    }) + "\n")
    fh.flush()


def read_last_generation(run_dir: Path) -> dict:
    """Return the generations.jsonl row with the highest best_fitness.
    Tiebreak: the latest gen. Used by save-best and resume."""
    rows = []
    with (run_dir / "generations.jsonl").open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"no rows in {run_dir / 'generations.jsonl'}")
    return max(rows, key=lambda r: (r["best_fitness"], r["gen"]))
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
python -m unittest tests.test_logging -v
```

Expected: all logging tests pass (originals plus the new collision + read_last_generation tests, ~10 tests total in this module).

- [ ] **Step 5: Run the full device-free suite to confirm no regressions**

```bash
python -m unittest tests.test_parameters tests.test_logging tests.test_cli tests.test_voter -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add genetic/logging.py tests/test_logging.py
git commit -m "M3: make_run_dir collision suffix + read_last_generation helper"
```

---

### Task 3: genetic/patches.py + tests

The biggest standalone piece. Patch I/O and DEAP individual conversion.

**Files:**
- Create: `genetic/patches.py`
- Create: `tests/test_patches.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_patches.py` with EXACTLY this content:

```python
import json
import tempfile
import unittest
from pathlib import Path

from genetic.patches import (
    save,
    load,
    from_individual,
    to_individual,
    machine_name_for,
)


class TestMachineNameFor(unittest.TestCase):
    def test_bd_classic_for_drum_pad(self):
        self.assertEqual(machine_name_for(pad=0, machine_num=0), "bd classic")

    def test_bd_acoustic_for_drum_pad(self):
        self.assertEqual(machine_name_for(pad=0, machine_num=30), "bd acoustic")

    def test_drum_machines_same_across_drum_pads(self):
        for pad in (0, 1, 2, 3):
            self.assertEqual(machine_name_for(pad=pad, machine_num=13), "bd fm")

    def test_unknown_falls_back_to_machine_number(self):
        # Pad 4 is BT track — drum machine table doesn't apply
        self.assertEqual(machine_name_for(pad=4, machine_num=30), "machine_30")

    def test_unknown_machine_on_drum_pad(self):
        # Machine 99 isn't in the table
        self.assertEqual(machine_name_for(pad=0, machine_num=99), "machine_99")


class TestSaveLoad(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            patch = {
                "version": 1,
                "name": "test",
                "pad": 0,
                "midi_channel": 0,
                "machine_number": 30,
                "machine_name": "bd acoustic",
                "parameters": [{"cc": 16, "value": 127, "name": "Source Level"}],
                "fitness": 8.0,
                "source": {
                    "run_dir": "runs/2026-06-10-1422-pad0",
                    "generation": 4,
                    "eval_idx": 2,
                },
            }
            path = Path(tmp) / "test.json"
            save(path, patch)
            loaded = load(path)
            self.assertEqual(loaded, patch)


class _FakeParam:
    """Stand-in for synthesizer.parameters.Parameter — just cc, value, name."""
    def __init__(self, cc, value, name="n/a"):
        self.cc = cc
        self.value = value
        self.name = name


class TestFromIndividual(unittest.TestCase):
    def test_builds_full_enumeration_patch(self):
        # Three params, one is machine-select, rest are evolved + fixed
        params = [
            _FakeParam(16, 127, "Source Level"),
            _FakeParam(17, 64, "Tune"),
            _FakeParam(70, 0, "Filter Attack"),
        ]
        patch = from_individual(
            pad=0, midi_channel=0,
            machine_num=30, machine_name="bd acoustic",
            params=params, fitness=8.0,
            source={"run_dir": "runs/x", "generation": 1, "eval_idx": 0},
        )
        self.assertEqual(patch["version"], 1)
        self.assertEqual(patch["pad"], 0)
        self.assertEqual(patch["midi_channel"], 0)
        self.assertEqual(patch["machine_number"], 30)
        self.assertEqual(patch["machine_name"], "bd acoustic")
        self.assertEqual(patch["fitness"], 8.0)
        self.assertEqual(len(patch["parameters"]), 3)
        self.assertEqual(patch["parameters"][0],
                         {"cc": 16, "value": 127, "name": "Source Level"})


class TestToIndividual(unittest.TestCase):
    def test_decodes_patch_to_individual(self):
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 30, "machine_name": "bd acoustic",
            "parameters": [
                {"cc": 16, "value": 127, "name": "Source Level"},
                {"cc": 17, "value": 64, "name": "Tune"},
                {"cc": 70, "value": 0, "name": "Filter Attack"},
            ],
            "fitness": 8.0, "source": {},
        }
        machines = [0, 13, 21, 22, 26, 30]    # 30 is at index 5
        evolved_ccs = [16, 17]                # CC 70 is fixed, not in genome
        ind, dropped = to_individual(patch, machines, evolved_ccs, list)
        self.assertEqual(ind, [5, 127, 64])
        self.assertEqual(dropped, {})

    def test_drops_ccs_not_in_evolved(self):
        # Patch carries CC 109 (LFO Depth) but current pad doesn't evolve it
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 30, "machine_name": "bd acoustic",
            "parameters": [
                {"cc": 16, "value": 127, "name": "Source Level"},
                {"cc": 109, "value": 60, "name": "LFO Depth"},
            ],
            "fitness": 8.0, "source": {},
        }
        machines = [0, 30]
        evolved_ccs = [16]   # 109 is not evolved here
        ind, dropped = to_individual(patch, machines, evolved_ccs, list)
        self.assertEqual(ind, [1, 127])
        self.assertEqual(dropped, {109: 60})

    def test_machine_not_in_filter_raises(self):
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 30, "machine_name": "bd acoustic",
            "parameters": [{"cc": 16, "value": 127, "name": "Source Level"}],
            "fitness": 8.0, "source": {},
        }
        machines = [0, 13, 21]   # 30 isn't here
        evolved_ccs = [16]
        with self.assertRaises(ValueError) as cm:
            to_individual(patch, machines, evolved_ccs, list)
        self.assertIn("30", str(cm.exception))

    def test_evolved_cc_missing_from_patch_raises(self):
        # evolved_ccs expects CC 17 but patch doesn't have it
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 0, "machine_name": "bd classic",
            "parameters": [{"cc": 16, "value": 127, "name": "Source Level"}],
            "fitness": 5.0, "source": {},
        }
        machines = [0]
        evolved_ccs = [16, 17]
        with self.assertRaises(ValueError) as cm:
            to_individual(patch, machines, evolved_ccs, list)
        self.assertIn("17", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
python -m unittest tests.test_patches -v
```

Expected: `ModuleNotFoundError: No module named 'genetic.patches'`.

- [ ] **Step 3: Implement `genetic/patches.py`**

Create `genetic/patches.py` with EXACTLY this content:

```python
"""Patch I/O and DEAP individual conversion. Pure data; no MIDI, no DEAP setup."""

import json
from pathlib import Path
from typing import Tuple


PATCH_VERSION = 1


# Machine names for the BD/SD/RS/CP drum-track family (pads 0-3). Derived from
# kits_10.md (1-based human labels, -1 to 0-based MIDI). Other pad families
# (BT/XT/HH/CY) use different machines at the same MIDI numbers — patches saved
# from those pads use "machine_<N>" as machine_name. This is informational only;
# machine_number is the source of truth.
_DRUM_TRACK_MACHINES = {
    0: "bd classic",
    1: "sd hard",
    2: "sd classic",
    3: "rs hard",
    4: "rs classic",
    5: "cp classic",
    13: "bd fm",
    14: "sd fm",
    15: "ut noise",
    16: "ut impulse",
    21: "bd plastic",
    22: "bd silky",
    23: "sd natural",
    26: "bd sharp",
    27: "disable",
    28: "sy dual vco",
    29: "sy chip",
    30: "bd acoustic",
    31: "sd acoustic",
    32: "sy raw",
}


def machine_name_for(pad: int, machine_num: int) -> str:
    if pad in (0, 1, 2, 3) and machine_num in _DRUM_TRACK_MACHINES:
        return _DRUM_TRACK_MACHINES[machine_num]
    return f"machine_{machine_num}"


def save(path: Path, patch: dict) -> None:
    """Write patch JSON to path. Caller ensures parent dir exists."""
    path.write_text(json.dumps(patch, indent=2, sort_keys=False))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def from_individual(pad, midi_channel, machine_num, machine_name,
                    params, fitness, source):
    """Build a patch dict from a decoded individual's send-ready state.
    `params` is an iterable of objects with .cc, .value, .name."""
    return {
        "version": PATCH_VERSION,
        "name": None,   # caller sets this from the filename
        "pad": pad,
        "midi_channel": midi_channel,
        "machine_number": machine_num,
        "machine_name": machine_name,
        "parameters": [
            {"cc": p.cc, "value": int(p.value), "name": p.name}
            for p in params
        ],
        "fitness": float(fitness),
        "source": source,
    }


def to_individual(patch, machines, evolved_ccs, individual_cls) -> Tuple[list, dict]:
    """Decode a patch into a DEAP-style individual list.

    Returns (individual, dropped_ccs) where:
    - individual = [machine_idx, evolved_cc_val_0, evolved_cc_val_1, ...]
    - dropped_ccs = {cc: value, ...} for patch CCs not in evolved_ccs

    Raises ValueError if patch's machine_number isn't in machines, or if any
    evolved_cc is missing from the patch's parameter list.
    """
    machine_num = patch["machine_number"]
    try:
        machine_idx = machines.index(machine_num)
    except ValueError:
        raise ValueError(
            f"patch machine {machine_num} ({patch.get('machine_name', '?')}) "
            f"not available in current pad's filter"
        )

    cc_to_value = {p["cc"]: p["value"] for p in patch["parameters"]}

    missing = [cc for cc in evolved_ccs if cc not in cc_to_value]
    if missing:
        raise ValueError(
            f"patch missing evolved CCs {missing}"
        )

    cc_values = [cc_to_value[cc] for cc in evolved_ccs]
    dropped = {cc: v for cc, v in cc_to_value.items() if cc not in set(evolved_ccs)}

    return individual_cls([machine_idx] + cc_values), dropped
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
python -m unittest tests.test_patches -v
```

Expected: all 11 tests pass, `OK`.

- [ ] **Step 5: Run the full device-free suite**

```bash
python -m unittest tests.test_parameters tests.test_logging tests.test_cli tests.test_voter tests.test_patches -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add genetic/patches.py tests/test_patches.py
git commit -m "M3: add genetic/patches.py for patch I/O + DEAP individual conversion"
```

---

### Task 4: CLI subcommand restructure + main.py verb dispatch

Largest task in M3. Restructure `genetic/cli.py` around `argparse` subparsers with `run` as default. Restructure `genetic/main.py` to dispatch on `args.subcommand`. M2's entire `run()` body becomes `_run(args)`.

**Files:**
- Modify: `genetic/cli.py`
- Modify: `genetic/main.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Update tests in `tests/test_cli.py`**

Replace the entire contents of `tests/test_cli.py` with EXACTLY this content:

```python
import unittest

from genetic.cli import parse_args


class TestRunSubcommandDefaults(unittest.TestCase):
    def test_bare_invocation_defaults_to_run(self):
        args = parse_args([])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 0)
        self.assertEqual(args.pop_size, 4)
        self.assertEqual(args.generations, 5)
        self.assertEqual(args.crossover_rate, 0.5)
        self.assertEqual(args.mutation_rate, 0.3)
        self.assertEqual(args.mutation_indpb, 0.15)
        self.assertEqual(args.tournament_size, 2)
        self.assertIsInstance(args.seed, int)
        self.assertFalse(args.no_log)
        self.assertIsNone(args.seed_from_patch)

    def test_bare_flags_default_to_run(self):
        args = parse_args(["--pad", "3"])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 3)
        self.assertEqual(args.midi_channel, 3)

    def test_explicit_run_subcommand(self):
        args = parse_args(["run", "--pad", "2"])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 2)

    def test_midi_channel_override(self):
        args = parse_args(["--pad", "0", "--midi-channel", "10"])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 10)

    def test_seed_override(self):
        args = parse_args(["--seed", "42"])
        self.assertEqual(args.seed, 42)

    def test_no_log_flag(self):
        args = parse_args(["--no-log"])
        self.assertTrue(args.no_log)

    def test_seed_from_patch(self):
        args = parse_args(["--seed-from-patch", "kraken"])
        self.assertEqual(args.seed_from_patch, "kraken")

    def test_all_numeric_overrides(self):
        args = parse_args([
            "--pop-size", "8",
            "--generations", "10",
            "--mutation-rate", "0.4",
            "--crossover-rate", "0.7",
            "--mutation-indpb", "0.2",
            "--tournament-size", "3",
        ])
        self.assertEqual(args.pop_size, 8)
        self.assertEqual(args.generations, 10)
        self.assertEqual(args.mutation_rate, 0.4)
        self.assertEqual(args.crossover_rate, 0.7)
        self.assertEqual(args.mutation_indpb, 0.2)
        self.assertEqual(args.tournament_size, 3)


class TestSaveBestSubcommand(unittest.TestCase):
    def test_with_name(self):
        args = parse_args(["save-best", "runs/2026-x-pad0", "--name", "kraken"])
        self.assertEqual(args.subcommand, "save-best")
        self.assertEqual(args.run_dir, "runs/2026-x-pad0")
        self.assertEqual(args.name, "kraken")

    def test_name_optional(self):
        args = parse_args(["save-best", "runs/2026-x-pad0"])
        self.assertEqual(args.subcommand, "save-best")
        self.assertIsNone(args.name)


class TestPlaySubcommand(unittest.TestCase):
    def test_positional_name(self):
        args = parse_args(["play", "kraken"])
        self.assertEqual(args.subcommand, "play")
        self.assertEqual(args.patch_name, "kraken")


class TestResumeSubcommand(unittest.TestCase):
    def test_positional_dir(self):
        args = parse_args(["resume", "runs/2026-x-pad0"])
        self.assertEqual(args.subcommand, "resume")
        self.assertEqual(args.run_dir, "runs/2026-x-pad0")

    def test_generations_override(self):
        args = parse_args(["resume", "runs/2026-x-pad0", "--generations", "3"])
        self.assertEqual(args.generations, 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
python -m unittest tests.test_cli -v
```

Expected: every test fails because `parse_args` doesn't have subcommand support yet.

- [ ] **Step 3: Replace `genetic/cli.py`**

Read the file first, then write EXACTLY this content:

```python
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
    if not argv or argv[0] not in KNOWN_SUBCOMMANDS:
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
```

- [ ] **Step 4: Run cli tests, verify they pass**

```bash
python -m unittest tests.test_cli -v
```

Expected: all 14 tests pass.

- [ ] **Step 5: Replace `genetic/main.py` with the dispatch shell + renamed _run**

Read the file first. Then replace with EXACTLY this content:

```python
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
    """Load canonical params + pad config; return (canonical, evolved, fixed, machines)."""
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
                machines, evolved_ccs, args.pad,
            )

            # Gen 0: evaluate any not-yet-valid individuals (seed-from-patch may
            # provide a pre-fit champion if we extend that later, but right now
            # all initial individuals are evaluated.)
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
                              machines, evolved_ccs, pad):
    """Build the gen-0 population. If seed_from_patch is set, one slot is the
    decoded patch and the rest are random."""
    if not seed_from_patch:
        return toolbox.population(n=pop_size)
    patch_path = Path("patches") / f"{seed_from_patch}.json"
    patch = patches.load(patch_path)
    if patch["pad"] != pad:
        print(f"[seed-from-patch] WARNING: patch pad {patch['pad']} != current pad {pad}")
    seeded, dropped = patches.to_individual(patch, machines, evolved_ccs, creator.Individual)
    if dropped:
        print(f"[seed-from-patch] dropped CCs not in current evolved_ccs: {sorted(dropped)}")
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


def _auto_patch_name(run_dir: Path, fitness: float) -> str:
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
```

- [ ] **Step 6: Verify the module imports without error**

```bash
python -c "from genetic.main import run; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 7: Verify each subcommand `--help` exits cleanly**

```bash
python -m genetic.main --help                  # shows the parent help w/ subcommands
python -m genetic.main run --help              # shows --pad, --midi-channel, etc.
python -m genetic.main save-best --help        # shows run_dir + --name
python -m genetic.main play --help             # shows patch_name
python -m genetic.main resume --help           # shows run_dir + --generations + --override
```

Expected: each exits with status 0, prints flag descriptions.

- [ ] **Step 8: Run the full device-free suite**

```bash
python -m unittest tests.test_parameters tests.test_logging tests.test_cli tests.test_voter tests.test_patches -v
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add genetic/cli.py genetic/main.py tests/test_cli.py
git commit -m "M3: argparse subcommands + per-verb dispatch; M2 driver becomes _run"
```

---

### Task 5: Update README + CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update README — Running section**

Read `README.md` first. Find the `## Running` section. Use Edit to replace the section's `Start a GA run:` code block and the paragraph describing it with the new four-verb structure.

Locate the existing block (starts with ` ```bash` and contains `python -m genetic.main`). Replace it with this expanded block:

```markdown
Start a GA run:

```bash
source ./activate_virtualenv.sh
python -m genetic.main                          # all defaults (run subcommand)
python -m genetic.main --help                   # subcommand list
python -m genetic.main run --help               # all run flags
python -m genetic.main --pad 0 --generations 10 --seed 42

# Save champion of a run as a patch
python -m genetic.main save-best runs/2026-06-10-1422-pad0 --name kraken
ls patches/kraken.json

# Audition a saved patch without re-running the GA
python -m genetic.main play kraken

# Resume a stopped run (champion + random fill, append to same dir)
python -m genetic.main resume runs/2026-06-10-1422-pad0 --generations 3

# Seed a new run from a saved patch
python -m genetic.main --pad 0 --seed-from-patch kraken --generations 5
```

Each run writes to `runs/YYYY-MM-DD-HHMM-pad<N>/` (with `-1`, `-2`, ... suffix
if you restart within the same minute). Patches go to `patches/<name>.json`.
Both directories are gitignored.

Common run flags (same as M2):
- `--pad` (default 0) — which Rytm voice to evolve.
- `--midi-channel` — defaults to `--pad`. Override if Rytm routing reassigns pads.
- `--pop-size`, `--generations`, `--mutation-rate`, `--crossover-rate`, `--tournament-size` — DEAP knobs.
- `--seed` — RNG seed, logged for reproducibility.
- `--no-log` — skip run-directory creation.
- `--seed-from-patch <name>` — seed initial population with a saved patch.

LPD8 controls during a run:
- Pads 1-8 → votes 1-8
- Knob 1 (CC 1 on Prog1) → re-hear the best-so-far without consuming a vote

Ctrl-C exits cleanly, printing the run directory and champion.
```

(The full replacement is from the `Start a GA run:` heading through the `Ctrl-C` line, plus the now-redundant inline flag list that the M2 README had.)

- [ ] **Step 2: Update CLAUDE.md — Common commands**

Read CLAUDE.md, find the `## Common commands` block. Replace the `# Run the GA` portion with:

```bash
# Run the GA / save / play / resume
python -m genetic.main --help                       # subcommand list
python -m genetic.main run --pad 0 --generations 10 --seed 42
python -m genetic.main save-best runs/2026-*-pad0 --name kraken
python -m genetic.main play kraken
python -m genetic.main resume runs/2026-*-pad0 --generations 3
```

- [ ] **Step 3: Update CLAUDE.md — Architecture section**

In CLAUDE.md, find the `genetic/` package description. Update the `main.py` bullet to mention the verb dispatch, and add a bullet for `patches.py`. Replace the `main.py` bullet text with:

```
  - `main.py` — top-level dispatcher. Parses CLI (via `cli.py`), routes to `_run` / `_save_best` / `_play` / `_resume`. `_run` is the M2 GA driver: argparse → seed → make `runs/` directory → DEAP toolbox → inline `mu+lambda` loop with HallOfFame elitism, replay-best callback, and per-vote/per-generation JSONL logging. `--midi-channel` defaults to `--pad`.
  - `patches.py` — patch I/O + DEAP individual conversion. `save()` / `load()`, `from_individual()` (build patch dict from decoded individual), `to_individual()` (decode patch back to individual + machine_idx lookup). Pure data; no MIDI or DEAP setup.
```

(Insert the `patches.py` bullet immediately after `main.py`.)

- [ ] **Step 4: Mark M0-M2 as shipped status updated to include M3**

In the intro paragraph (near the top of CLAUDE.md), find the "M0/M1/M2 are done" sentence. Update it to add M3:

```
M0 (foundation cleanup), M1 (end-to-end GA loop), M2 (quality of life — CLI, logging, replay-best, elitism, graceful Ctrl-C), and M3 (persistence — save/play/resume + seed-from-patch) are done. `genetic/` wires DEAP to the existing `synthesizer/` and `user_interface/` code; `python -m genetic.main --help` shows the CLI surface. Future milestones (M4 better fitness, M5 device abstraction, M6 Mopho, M7 multi-device) are specced in `docs/specs/`.
```

- [ ] **Step 5: Update docs/specs/README.md status table**

In `docs/specs/README.md`, find the row for M3 and change `| Next |` to `| Shipped |`. Find the row for M4 and change `| Not started |` to `| Next |`.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md docs/specs/README.md
git commit -m "M3: document the four-verb CLI + patches.py + ship status"
```

---

### Task 6: Manual hardware verification

These checks need the Rytm + LPD8 connected. The user will run these — your job (as implementer) ends after the doc updates in Task 5.

- [ ] **Step 1: Help surfaces**

```bash
python -m genetic.main --help
python -m genetic.main run --help
python -m genetic.main save-best --help
python -m genetic.main play --help
python -m genetic.main resume --help
```

Expected: each exits 0, prints flag descriptions.

- [ ] **Step 2: Full GA run → save → play round-trip**

```bash
python -m genetic.main --pad 0 --generations 2 --pop-size 2 --seed 42
# Vote on each candidate. Note which one wins.

python -m genetic.main save-best runs/2026-*-pad0 --name test
ls patches/test.json
cat patches/test.json | head -20

python -m genetic.main play test
# Expected: same sound as the winning candidate from the run.
```

- [ ] **Step 3: Resume**

```bash
python -m genetic.main resume runs/2026-*-pad0 --generations 1
# Expected: first candidate played is the previous run's champion.
# Run dir's generations.jsonl now has additional rows.
wc -l runs/2026-*-pad0/generations.jsonl   # > original
```

- [ ] **Step 4: Seed-from-patch**

```bash
python -m genetic.main --pad 0 --seed-from-patch test --generations 1 --pop-size 2
# Expected: first candidate sounds identical to `play test`.
```

- [ ] **Step 5: Collision suffix**

```bash
# Run twice in quick succession
python -m genetic.main --pad 0 --generations 0 --pop-size 1
python -m genetic.main --pad 0 --generations 0 --pop-size 1
ls runs/
# Expected: second run dir has `-1` suffix.
```

- [ ] **Step 6: voter.py cleanup check**

```bash
wc -l user_interface/voter.py
# Expected: ~120 lines (down from ~210).

# voting still works (any of the runs above already exercises it)
```

---

## Notes & gotchas during implementation

- **Patch filename = name.** The CLI's positional `patch_name` doesn't include `.json`. `_play` and `_save_best` join `Path("patches") / f"{name}.json"`. Keep this consistent everywhere.
- **`creator.Individual` is created lazily.** The `_ensure_deap_classes()` helper guards repeated `creator.create()` calls (M2 pattern). It must be called before any `creator.Individual(...)` constructor in `_save_best` / `_resume` / `_seed_from_patch` paths even though those handlers don't construct a toolbox — `_setup_pad` doesn't trigger it.
- **`_save_best` does NOT touch DEAP at all** beyond reading the saved best_individual (which is just a list). It doesn't need `_ensure_deap_classes()`. But `_resume` does (it constructs `creator.Individual(...)` directly), so the call is in `_resume`.
- **Resume open mode is `"a"` (append)** — the existing JSONL lines stay. If a user wants a fresh dir, they should re-run, not resume.
- **`make_run_dir` collision suffix is bounded to 9.** Beyond that, the RuntimeError is intentional (something is very wrong).
- **`_DRUM_TRACK_MACHINES` only covers pads 0-3.** Patches saved from BT/XT/HH/CY pads use `machine_<N>` as the name. M4+ might add per-track-type tables; M3 doesn't.
- **`patches.save()` doesn't create the parent dir.** `_save_best` calls `out_dir.mkdir(parents=True, exist_ok=True)` explicitly. Don't duplicate this in `patches.save()`.
- **`json.dumps(..., indent=2, sort_keys=False)`** in `patches.save()` — order preservation matters because we want the patch file to read naturally (version, name, pad, then parameters). `sort_keys=True` would scramble that.
