# M2 — Quality of Life Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the M1 GA loop usable for real sound-design sessions: CLI configuration, on-disk logging, replay-best from the LPD8, elitism, and graceful Ctrl-C.

**Architecture:** Add two device-free modules (`genetic/cli.py`, `genetic/logging.py`). Rewrite `genetic/main.py` to run an inline `mu+lambda` loop (replacing `eaSimple`) so we own the generation boundary and can stamp `gen`/`eval_idx` into each vote log line. Add a non-blocking poll + `on_replay` callback to `LPD8VoteController.get_vote()`. Extract a `send_individual()` helper from `evaluate.py` so the replay callback re-uses the same send path. Move the RNG seed out of module-import into `main.run()`.

**Tech Stack:** Python 3, stdlib (`argparse`, `pathlib`, `json`, `datetime`, `random`), DEAP, mido. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-10-m2-quality-of-life-design.md`

---

### Task 0: Gitignore + baseline check

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add `runs/` to .gitignore**

Edit `.gitignore` to append:

```
runs/
```

Final file content:

```
*.swp
.ipynb_checkpoints
runs/
```

- [ ] **Step 2: Verify M1 device-free tests still pass**

Run:

```bash
source ./activate_virtualenv.sh
python -m unittest tests.test_parameters -v
```

Expected: all `test_parameters` tests pass. (M1 baseline — nothing should be different yet.)

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "M2: ignore runs/ directory"
```

---

### Task 1: Logging module + device-free tests

The logging module is pure file I/O — no GA awareness. TDD: write the tests first, then the module.

**Files:**
- Create: `genetic/logging.py`
- Create: `tests/test_logging.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_logging.py`:

```python
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from genetic.logging import (
    make_run_dir,
    write_config,
    log_generation,
    log_vote,
)


class TestMakeRunDir(unittest.TestCase):
    def test_creates_named_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            run_dir = make_run_dir(base, pad=0, now=ts)
            self.assertTrue(run_dir.is_dir())
            self.assertEqual(run_dir.name, "2026-06-10-1422-pad0")
            self.assertEqual(run_dir.parent, base)

    def test_pad_suffix_distinguishes_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            d0 = make_run_dir(base, pad=0, now=ts)
            d3 = make_run_dir(base, pad=3, now=ts)
            self.assertNotEqual(d0, d3)
            self.assertTrue(d0.is_dir())
            self.assertTrue(d3.is_dir())


class TestWriteConfig(unittest.TestCase):
    def test_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            config = {"pad": 0, "seed": 42, "pop_size": 4}
            write_config(run_dir, config)
            text = (run_dir / "config.json").read_text()
            self.assertEqual(json.loads(text), config)


class TestLogGeneration(unittest.TestCase):
    def test_writes_one_jsonl_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=5.0, avg_fitness=3.2,
                               min_fitness=1.0, best_individual=[3, 64, 70],
                               n_evaluated=4)
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["gen"], 0)
            self.assertEqual(row["best_fitness"], 5.0)
            self.assertEqual(row["best_individual"], [3, 64, 70])
            self.assertEqual(row["n_evaluated"], 4)

    def test_two_lines_appended(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=5.0, avg_fitness=3.2,
                               min_fitness=1.0, best_individual=[1], n_evaluated=4)
                log_generation(fh, gen=1, best_fitness=7.0, avg_fitness=4.0,
                               min_fitness=2.0, best_individual=[2], n_evaluated=3)
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["gen"], 1)


class TestLogVote(unittest.TestCase):
    def test_writes_one_jsonl_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "votes.jsonl"
            with path.open("w") as fh:
                log_vote(fh, gen=0, eval_idx=2, machine=13,
                         evolved_ccs={"17": 64, "109": 60},
                         fixed_ccs={"70": 0},
                         vote=5, timestamp_iso="2026-06-10T14:22:31")
            row = json.loads(path.read_text().strip())
            self.assertEqual(row["gen"], 0)
            self.assertEqual(row["eval_idx"], 2)
            self.assertEqual(row["machine"], 13)
            self.assertEqual(row["evolved_ccs"], {"17": 64, "109": 60})
            self.assertEqual(row["vote"], 5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests, verify they fail**

Run:

```bash
python -m unittest tests.test_logging -v
```

Expected: `ModuleNotFoundError: No module named 'genetic.logging'`.

- [ ] **Step 3: Implement `genetic/logging.py`**

Create `genetic/logging.py`:

```python
"""Run-directory and JSONL helpers. Pure file I/O — no GA knowledge."""

import json
from datetime import datetime
from pathlib import Path


def make_run_dir(base: Path, pad: int, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    name = f"{now.strftime('%Y-%m-%d-%H%M')}-pad{pad}"
    run_dir = base / name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


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
```

- [ ] **Step 4: Run tests, verify they pass**

Run:

```bash
python -m unittest tests.test_logging -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add genetic/logging.py tests/test_logging.py
git commit -m "M2: add genetic/logging.py for run-directory + JSONL"
```

---

### Task 2: CLI module + device-free tests

**Files:**
- Create: `genetic/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
import unittest

from genetic.cli import parse_args


class TestParseArgs(unittest.TestCase):
    def test_defaults(self):
        args = parse_args([])
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 0)  # defaults to pad
        self.assertEqual(args.pop_size, 4)
        self.assertEqual(args.generations, 5)
        self.assertEqual(args.crossover_rate, 0.5)
        self.assertEqual(args.mutation_rate, 0.3)
        self.assertEqual(args.mutation_indpb, 0.15)
        self.assertEqual(args.tournament_size, 2)
        self.assertIsInstance(args.seed, int)
        self.assertFalse(args.no_log)

    def test_pad_override_propagates_to_midi_channel(self):
        args = parse_args(["--pad", "3"])
        self.assertEqual(args.pad, 3)
        self.assertEqual(args.midi_channel, 3)

    def test_midi_channel_override(self):
        args = parse_args(["--pad", "0", "--midi-channel", "10"])
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 10)

    def test_seed_override(self):
        args = parse_args(["--seed", "42"])
        self.assertEqual(args.seed, 42)

    def test_no_log_flag(self):
        args = parse_args(["--no-log"])
        self.assertTrue(args.no_log)

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests, verify they fail**

Run:

```bash
python -m unittest tests.test_cli -v
```

Expected: `ModuleNotFoundError: No module named 'genetic.cli'`.

- [ ] **Step 3: Implement `genetic/cli.py`**

Create `genetic/cli.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify they pass**

Run:

```bash
python -m unittest tests.test_cli -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add genetic/cli.py tests/test_cli.py
git commit -m "M2: add genetic/cli.py with --pad/--midi-channel/--seed"
```

---

### Task 3: Remove module-level seed(time()) — make seeding driver-controlled

CLAUDE.md flags `seed(time())` at module-import in `parameters.py` and `midicontrol.py` as a footgun and tasks M2 with deterministic seeding. Move the seed into `main.run()` after CLI parse.

**Files:**
- Modify: `synthesizer/parameters.py:1-8`
- Modify: `synthesizer/midicontrol.py:1-8`

- [ ] **Step 1: Remove seed from `synthesizer/parameters.py`**

Current top of file:

```python
from random import seed, randint
from time import time
from typing import List
from collections import UserList, UserDict
import pandas as pd

seed(time())
#seed(100)
```

Edit to:

```python
from random import randint
from typing import List
from collections import UserList, UserDict
import pandas as pd
```

(Removes the `seed`/`time` imports, the module-level `seed(time())` call, and the dead commented `#seed(100)` line.)

- [ ] **Step 2: Remove seed from `synthesizer/midicontrol.py`**

Current top of file:

```python
import mido
from random import randint, seed
from time import time

from synthesizer.parameters import ParameterCollection, Parameter, AnalogRytmParameterCSVReader

seed(time())
```

Edit to:

```python
import mido
from random import randint

from synthesizer.parameters import ParameterCollection, Parameter, AnalogRytmParameterCSVReader
```

- [ ] **Step 3: Run the device-free tests**

Run:

```bash
python -m unittest tests.test_parameters tests.test_logging tests.test_cli -v
```

Expected: all pass. (Removing module-level seed shouldn't affect any existing test — random calls in `test_parameters` either use explicit values or don't depend on a specific seed.)

- [ ] **Step 4: Verify imports still work**

Run:

```bash
python -c "from synthesizer.parameters import AnalogRytmParameterCSVReader; print('ok')"
python -c "from synthesizer.midicontrol import AnalogRytmMachineSelector; print('ok')"
```

Expected: both print `ok` with no errors.

- [ ] **Step 5: Commit**

```bash
git add synthesizer/parameters.py synthesizer/midicontrol.py
git commit -m "M2: remove module-level seed(time()); driver now owns seeding"
```

---

### Task 4: LPD8VoteController — non-blocking poll + replay callback

The current `get_vote()` uses `for msg in self.port:` which blocks in mido C code. Switch to `iter_pending()` + `time.sleep(0.01)` so we can also see CC messages (for replay) and so Ctrl-C lands promptly.

**Files:**
- Modify: `user_interface/voter.py:60-90`

- [ ] **Step 1: Write the failing test**

Create `tests/test_voter.py`:

```python
import unittest
from unittest.mock import MagicMock

import mido

from user_interface.voter import LPD8VoteController


class FakePort:
    """Minimal mido-port stand-in for tests."""
    def __init__(self, messages):
        self._queue = list(messages)

    def iter_pending(self):
        while self._queue:
            yield self._queue.pop(0)


def _make_controller(messages):
    c = LPD8VoteController()
    c.port = FakePort(messages)
    c.is_connected = True
    return c


class TestLPD8GetVote(unittest.TestCase):
    def test_pad_1_returns_vote_1(self):
        c = _make_controller([mido.Message("note_on", note=36, velocity=100)])
        self.assertEqual(c.get_vote(), 1)

    def test_pad_8_returns_vote_8(self):
        c = _make_controller([mido.Message("note_on", note=43, velocity=100)])
        self.assertEqual(c.get_vote(), 8)

    def test_replay_cc_calls_callback_then_waits_for_vote(self):
        msgs = [
            mido.Message("control_change", control=1, value=100),
            mido.Message("note_on", note=38, velocity=100),  # pad 3 → vote 3
        ]
        c = _make_controller(msgs)
        replay = MagicMock()
        vote = c.get_vote(on_replay=replay)
        self.assertEqual(vote, 3)
        replay.assert_called_once()

    def test_replay_cc_ignored_when_no_callback(self):
        msgs = [
            mido.Message("control_change", control=1, value=100),
            mido.Message("note_on", note=40, velocity=100),  # pad 5 → vote 5
        ]
        c = _make_controller(msgs)
        self.assertEqual(c.get_vote(), 5)  # no on_replay → CC silently ignored

    def test_non_replay_cc_ignored(self):
        msgs = [
            mido.Message("control_change", control=2, value=100),  # not replay CC
            mido.Message("note_on", note=36, velocity=100),
        ]
        c = _make_controller(msgs)
        replay = MagicMock()
        self.assertEqual(c.get_vote(on_replay=replay), 1)
        replay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test, verify it fails**

Run:

```bash
python -m unittest tests.test_voter -v
```

Expected: tests fail because the current `get_vote()` blocks on `for msg in self.port:` (FakePort has no `__iter__`) AND doesn't accept `on_replay`.

- [ ] **Step 3: Rewrite `LPD8VoteController.get_vote()` (and align `KeyboardVoteController`'s signature)**

In `user_interface/voter.py`, add `import time` near the top (after `import sys`):

```python
import sys
import time

import mido
```

Replace the existing `LPD8VoteController.get_vote` method (lines ~60-89) with:

```python
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
```

Then update `KeyboardVoteController.get_vote` (lines ~94-114) so callers can pass `on_replay=` to either voter type without branching. Replace its signature:

```python
    def get_vote(self):
```

with:

```python
    def get_vote(self, on_replay=None, replay_cc=1):
        # Keyboard fallback has no replay support — accept the params for
        # signature parity with LPD8VoteController and ignore them.
        _ = on_replay, replay_cc
```

Leave the rest of the method body unchanged.

- [ ] **Step 4: Run tests, verify they pass**

Run:

```bash
python -m unittest tests.test_voter tests.test_parameters tests.test_logging tests.test_cli -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add user_interface/voter.py tests/test_voter.py
git commit -m "M2: LPD8 get_vote non-blocking poll + on_replay callback"
```

---

### Task 5: Refactor `genetic/evaluate.py` — extract send + accept logging hooks

The replay callback needs the same MIDI send path the evaluator uses. Extract a `send_individual()` helper, and let `make_evaluate()` accept an optional `state` dict + `vote_logger` callable + `on_replay` callback. No device-free test here — the function depends on hardware; manual verification covers it in Task 8.

**Files:**
- Modify: `genetic/evaluate.py` (rewrite)

- [ ] **Step 1: Rewrite `genetic/evaluate.py`**

Replace the entire contents of `genetic/evaluate.py` with:

```python
import copy
import time
from datetime import datetime

import mido

from synthesizer.parameters import Parameter
from synthesizer.midicontrol import (
    MidiMessage,
    MidiCCMessage,
    MidiMessageCollectionSender,
)


MACHINE_CC = 15
TRIGGER_NOTE = 36
TRIGGER_VELOCITY = 100
TRIGGER_HOLD_SECONDS = 0.1


def build_params_for_individual(individual, machines, canonical_params,
                                evolved_ccs, fixed_values):
    """Decode a genome into (machine_num, params): a list of Parameter objects
    with evolved + fixed values applied, ready to send."""
    machine_num = machines[individual[0]]
    cc_values = individual[1:]

    params = copy.deepcopy(canonical_params)
    cc_to_param = {p.cc: p for p in params}

    for cc, value in zip(evolved_ccs, cc_values):
        cc_to_param[cc].set_value(value)
    for cc, value in fixed_values.items():
        cc_to_param[cc].set_value(value)

    return machine_num, params


def send_individual(midi_connect, midi_channel, machine_num, params):
    """Send machine CC + all param CCs + a trig note. Used by evaluate() and
    by the replay-best callback so both paths produce identical sound."""
    machine_param = Parameter(cc=MACHINE_CC, value=machine_num,
                              value_min=0, value_max=127)
    MidiCCMessage(midi_connect, midi_channel, machine_param).send()

    sender = MidiMessageCollectionSender(midi_connect, midi_channel)
    sender.convert_parameters_to_messages(params)
    sender.send_collection_messages()

    note_on = mido.Message('note_on', note=TRIGGER_NOTE, velocity=TRIGGER_VELOCITY)
    MidiMessage(midi_connect, midi_channel, note_on).send()
    time.sleep(TRIGGER_HOLD_SECONDS)
    note_off = mido.Message('note_off', note=TRIGGER_NOTE, velocity=0)
    MidiMessage(midi_connect, midi_channel, note_off).send()


def make_evaluate(midi_connect, midi_channel, voter, machines, canonical_params,
                  evolved_params, fixed_values,
                  state=None, vote_logger=None, on_replay=None):
    """Build the GA fitness closure.

    state: optional {'gen': int, 'eval_idx': int} dict the driver mutates between
           generations. Used to stamp gen/eval_idx into vote log lines.
    vote_logger: optional callable(gen, eval_idx, machine, evolved_ccs, fixed_ccs,
                                   vote, timestamp_iso) -> None.
    on_replay: optional callable passed through to voter.get_vote() so the user
               can re-hear best-so-far without spending a vote.
    """
    evolved_ccs = [p.cc for p in evolved_params]

    def evaluate(individual):
        machine_num, params = build_params_for_individual(
            individual, machines, canonical_params, evolved_ccs, fixed_values,
        )
        send_individual(midi_connect, midi_channel, machine_num, params)

        vote = voter.get_vote(on_replay=on_replay)
        if not vote:
            vote = 1

        if vote_logger is not None and state is not None:
            evolved_ccs_log = {str(cc): int(v)
                               for cc, v in zip(evolved_ccs, individual[1:])}
            fixed_ccs_log = {str(cc): (int(v) if isinstance(v, int) else v)
                             for cc, v in fixed_values.items()}
            vote_logger(
                gen=state['gen'],
                eval_idx=state['eval_idx'],
                machine=machine_num,
                evolved_ccs=evolved_ccs_log,
                fixed_ccs=fixed_ccs_log,
                vote=vote,
                timestamp_iso=datetime.now().isoformat(timespec='seconds'),
            )
            state['eval_idx'] += 1

        return (float(vote),)

    return evaluate
```

- [ ] **Step 2: Verify imports still work**

Run:

```bash
python -c "from genetic.evaluate import make_evaluate, send_individual, build_params_for_individual; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Run device-free tests to confirm nothing else broke**

Run:

```bash
python -m unittest tests.test_parameters tests.test_logging tests.test_cli tests.test_voter -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add genetic/evaluate.py
git commit -m "M2: extract send_individual; evaluate accepts state + vote_logger + on_replay"
```

---

### Task 6: Rewrite `genetic/main.py` — argparse → seed → run dir → inline mu+lambda → HoF → Ctrl-C

This is the biggest task. The new driver:
1. Parses CLI args
2. Seeds RNG
3. Creates run directory + opens log file handles (unless `--no-log`)
4. Sets up DEAP toolbox (unchanged from M1 except for `eaMuPlusLambda` replacement)
5. Builds the replay callback bound to a `tools.HallOfFame(1)`
6. Runs an inline `mu+lambda` loop that bumps `state['gen']` between generations and writes `generations.jsonl`
7. Wraps the loop in try/except KeyboardInterrupt
8. Prints champion summary on exit

**Files:**
- Modify: `genetic/main.py` (full rewrite)

- [ ] **Step 1: Rewrite `genetic/main.py`**

Replace the entire contents of `genetic/main.py` with:

```python
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
```

- [ ] **Step 2: Verify the module imports without error**

Run:

```bash
python -c "from genetic.main import run; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Verify `--help` works**

Run:

```bash
python -m genetic.main --help
```

Expected: prints argparse help text listing every flag with its default.

- [ ] **Step 4: Run all device-free tests**

Run:

```bash
python -m unittest tests.test_parameters tests.test_logging tests.test_cli tests.test_voter -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add genetic/main.py
git commit -m "M2: rewrite main.py with CLI, seeding, run dir, mu+lambda, HoF, Ctrl-C"
```

---

### Task 7: Update README + CLAUDE.md

**Files:**
- Modify: `README.md` (Running section)
- Modify: `CLAUDE.md` (Common commands; mark RNG-seeding gotcha resolved)

- [ ] **Step 1: Update README — Running section**

In `README.md`, replace the `## Running` section (currently lines ~12-27) with:

```markdown
## Running

Prerequisites:
- Elektron Analog Rytm MKII connected (MIDI port name: `Elektron Analog Rytm MKII`)
- Akai LPD8 on Prog1 (port name: `LPD8`) — optional, falls back to keyboard input if missing
- Python venv set up: `source ./activate_virtualenv.sh` (or `source venv/bin/activate`)
- Dependencies installed: `pip install -r requirements.txt`

Start a GA run:

```bash
source ./activate_virtualenv.sh
python -m genetic.main                          # all defaults
python -m genetic.main --help                   # see every flag
python -m genetic.main --pad 0 --generations 10 --seed 42
```

Common flags:
- `--pad` (default 0) — which Rytm voice to evolve (0=BD, 1=SD, ...). Drives `pad_config.py`.
- `--midi-channel` — MIDI channel for sends. Defaults to `--pad`. Override if your Rytm routing reassigns pads to channels (e.g. `--midi-channel 10` when channel 10 triggers pad 0).
- `--pop-size`, `--generations`, `--mutation-rate`, `--crossover-rate`, `--tournament-size` — DEAP knobs.
- `--seed` — RNG seed. Default: `int(time())`. Logged in the run's `config.json` for reproducibility.
- `--no-log` — skip run directory creation (smoke tests).

Each run writes to `runs/YYYY-MM-DD-HHMM-pad<N>/`:
- `config.json` — resolved args + Rytm port + pad_config snapshot
- `generations.jsonl` — best/avg/min fitness + best individual per generation
- `votes.jsonl` — one line per evaluation: gen, eval_idx, machine, CCs, vote, timestamp

LPD8 controls during a run:
- Pads 1-8 → votes 1-8
- Knob 1 (CC 1 on Prog1) → re-hear the best-so-far without consuming a vote

Ctrl-C exits cleanly, printing the run directory and champion.

Tests:

```bash
./unittests.sh                                # full suite (requires Rytm connected)
python -m unittest tests.test_parameters tests.test_cli tests.test_logging tests.test_voter
                                              # device-free unit tests
```
```

- [ ] **Step 2: Update CLAUDE.md — Common commands**

In `CLAUDE.md`, find the `## Common commands` section and replace its `# Tests` block area / Running paragraph with the new CLI surface. Specifically, change the block:

```bash
# Environment
source ./activate_virtualenv.sh         # or: source venv/bin/activate
pip install -r requirements.txt

# Tests (uses stdlib unittest, discovered from ./tests/)
./unittests.sh                          # all tests, verbose
python -m unittest tests.test_parameters                          # one module
python -m unittest tests.test_parameters.TestParameter            # one class
python -m unittest tests.test_parameters.TestParameter.test_default  # one test
```

To:

```bash
# Environment
source ./activate_virtualenv.sh         # or: source venv/bin/activate
pip install -r requirements.txt

# Run the GA
python -m genetic.main --help
python -m genetic.main --pad 0 --generations 10 --seed 42
python -m genetic.main --no-log         # smoke test, no run directory

# Tests (uses stdlib unittest, discovered from ./tests/)
./unittests.sh                          # all tests, verbose (requires Rytm)
python -m unittest tests.test_parameters tests.test_cli tests.test_logging tests.test_voter
                                        # device-free subset
python -m unittest tests.test_parameters.TestParameter            # one class
python -m unittest tests.test_parameters.TestParameter.test_default  # one test
```

- [ ] **Step 3: Mark RNG-seeding gotcha resolved in CLAUDE.md**

In `CLAUDE.md` under `## Gotchas`, find the bullet:

```
- **RNG seeded at module import** in `parameters.py` and `midicontrol.py` (`seed(time())`). Tests can't pin a deterministic seed without changing those modules. M2 will own deterministic seeding via a `--seed` flag.
```

Replace with:

```
- **RNG seeded by the driver, not at import.** `genetic.main.run()` calls `random.seed(args.seed)` after CLI parse; the seed is logged in `config.json` so any run is reproducible by passing `--seed <N>`.
```

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "M2: document the new CLI surface and run-directory layout"
```

---

### Task 8: Manual hardware verification

These checks need the Rytm and (for replay/votes) the LPD8 plugged in. Run from the M2 spec's verification block.

- [ ] **Step 1: `--help` and a clean smoke run**

```bash
python -m genetic.main --help
python -m genetic.main --pad 0 --generations 1 --pop-size 2 --no-log
```

Expected: help prints all flags; smoke run plays a few candidates, accepts votes, prints champion.

- [ ] **Step 2: Run dir layout**

```bash
python -m genetic.main --pad 0 --generations 3 --pop-size 4 --seed 42
ls runs/
cat runs/2026-*-pad0/config.json | head -40
wc -l runs/2026-*-pad0/generations.jsonl    # == 4  (gen 0 + 3 more)
wc -l runs/2026-*-pad0/votes.jsonl          # <= pop_size * (generations + 1) = 16
```

Expected: one new `runs/2026-MM-DD-HHMM-pad0/` directory with three files. `config.json` has all flags + seed=42 + pad_config snapshot. `generations.jsonl` has 4 lines. `votes.jsonl` has at most 16 (some offspring inherit fitness via direct-copy varOr path and skip re-evaluation).

- [ ] **Step 3: Replay-best**

Start a run, vote on a few candidates to populate the HoF, then twist LPD8 knob 1 (CC 1 on Prog1) mid-vote. Expected: console prints `[replay] champion: ...`, the Rytm re-plays the champion, the voter keeps waiting for a pad press. No `votes.jsonl` line is written for the replay.

- [ ] **Step 4: Elitism**

```bash
python -m genetic.main --pad 0 --generations 3 --pop-size 4 --seed 42
# In gen 0, vote 8 for one candidate, 1 for the rest.
# In gens 1-3, vote 1 for everything.
cat runs/2026-*-pad0/generations.jsonl
```

Expected: `best_fitness` never drops below 8 across the 4 generation lines — the champion is preserved by HallOfFame + mu+lambda selection.

- [ ] **Step 5: Graceful Ctrl-C**

Start a run, press Ctrl-C mid-vote. Expected:
- `Interrupted at gen N` prints.
- Champion summary prints (or `No champion produced.` if before any vote).
- Run dir path prints.
- Process exits 0.
- `runs/<dir>/generations.jsonl` and `votes.jsonl` are well-formed (last line is a complete JSON object, no partial write).

- [ ] **Step 6: Seed reproducibility**

```bash
python -m genetic.main --pad 0 --generations 0 --pop-size 4 --seed 42 --no-log
python -m genetic.main --pad 0 --generations 0 --pop-size 4 --seed 42 --no-log
```

Expected: both runs initialize the same population (same machine + same CC values for each candidate). With `--generations 0`, only gen-0 evaluation happens — the genome decisions are deterministic on `--seed`. (You'll have to vote your way through both, but the candidates played should match.)

- [ ] **Step 7: Commit any doc tweaks discovered during verification**

If verification surfaced any wording or assertion fixes needed in README/CLAUDE.md, commit them now:

```bash
git status
git add <files>
git commit -m "M2: doc tweaks from hardware verification"
```

(Skip if nothing changed.)

---

## Notes & gotchas during implementation

- **DEAP `creator.create()` is global.** If you re-run `main.py` in the same Python session (e.g. via `python -i`), `creator.create("FitnessMax", ...)` will warn about re-creation. The `if not hasattr(creator, "FitnessMax")` guard in Task 6 handles this.
- **`algorithms.varOr` returns offspring as a flat list** — the inline loop calls it as the M2 spec intends. `lambda_ = pop_size` keeps the budget the same as M1.
- **HoF on the entire population, not just offspring.** We call `hof.update(pop)` after gen 0 and `hof.update(offspring)` after each later gen. That's enough: if the champion is a parent that survives `select(pop + offspring, k=pop_size)`, HoF already has it from a prior generation; new candidates get checked when they're evaluated.
- **`midi_connect` ports are global to the process** — there's no need to close them in the try/finally. Ctrl-C just exits.
- **`config.json` snapshot is shallow.** It captures the *current* pad_config dict shape (machine_filter as a sorted list, fixed_ccs/cc_value_caps with string keys for JSON). It does NOT capture which canonical CSV row each evolved CC came from. M3 will need that mapping for replay; M2's snapshot is enough for human inspection + an eventual M3 lookup against the same `rytm-limited.csv`.
