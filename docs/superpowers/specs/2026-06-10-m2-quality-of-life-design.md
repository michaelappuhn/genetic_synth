# M2 — Quality of life: implementation design

## Context

M1 wired DEAP to the synthesizer/voter code and produced a working GA loop. Using it for an actual sound-design session is rough: every parameter is hardcoded in `genetic/main.py`, nothing is recorded so good runs can't be replayed or analyzed, you can't re-hear a champion mid-run, a bad generation can wipe a champion, and Ctrl-C kills the process without summary.

This design implements `docs/specs/M2-quality-of-life.md`. The outcome is a CLI-driven driver that logs each run to disk, lets the user replay the best-so-far candidate from the LPD8, preserves champions across generations, and exits cleanly on Ctrl-C. M3 (persistence) will read the run directories this milestone produces; M4 (better fitness) will add to `votes.jsonl`.

## Design

### File layout

Three new concerns, each in its own module so `genetic/main.py` stays scannable:

- **`genetic/cli.py`** — argparse setup. One function `parse_args() -> argparse.Namespace`.
- **`genetic/logging.py`** — run directory + JSONL helpers. Pure file I/O, no GA knowledge.
- **`genetic/main.py`** — orchestrator: parse args → seed RNG → make run dir → setup GA → run an inline `mu+lambda` loop → write champion summary. Wraps the loop in try/except for graceful Ctrl-C.

Existing files get surgical edits, not restructuring:

- **`genetic/evaluate.py`** — closure gains a shared `state` dict + an optional `vote_logger` callback so it can stamp `gen` and `eval_idx` on each vote without leaking GA loop concerns into the evaluator.
- **`user_interface/voter.py`** — `LPD8VoteController.get_vote()` gains an optional `on_replay` callback and a `replay_cc` parameter (default `1` — first knob on LPD8 Prog1).
- **`synthesizer/parameters.py`**, **`synthesizer/midicontrol.py`** — delete module-level `seed(time())` calls (footgun flagged in CLAUDE.md; M2 owns the fix per that gotcha). Seeding moves to `main.run()` after CLI parse.

### CLI

`argparse` directly on `python -m genetic.main` — no `run` subcommand (the M2 spec proposed one, but with a single command it's noise; M3 can introduce subcommands when `replay` / `resume` arrive). Defaults match the M1 hardcoded values so muscle memory is preserved.

| Flag | Default | Purpose |
|---|---|---|
| `--pad` | `0` | Drives `pad_config` lookup + `avail_machines_by_channel` palette |
| `--midi-channel` | `--pad` | Where MIDI sends actually go (override for Rytm routing) |
| `--pop-size` | `4` | Initial population size; also `mu` and `lambda` in eaMuPlusLambda |
| `--generations` | `5` | Number of generations after gen 0 |
| `--mutation-rate` | `0.3` | Probability an offspring gets mutated (DEAP's `mutpb`) |
| `--crossover-rate` | `0.5` | Probability of crossover (DEAP's `cxpb`) |
| `--mutation-indpb` | `0.15` | Per-gene resample probability inside `bounded_mutate` |
| `--tournament-size` | `2` | Tournament selection size |
| `--seed` | `int(time())` | RNG seed; logged in `config.json` so any run is reproducible |
| `--no-log` | off | Skip run directory creation (quick smoke tests) |

### Seeding

CLAUDE.md flags module-level `seed(time())` in `parameters.py` and `midicontrol.py` as a footgun and tasks M2 with deterministic seeding. Plan: delete both module-level calls, seed once in `main.run()` immediately after parsing args. Update the CLAUDE.md gotcha to mark it resolved.

### Run directory

Layout: `runs/YYYY-MM-DD-HHMM-pad<N>/` (e.g. `runs/2026-06-10-1422-pad0/`). The pad suffix keeps simultaneous-pad sessions distinguishable in `ls`. `runs/` is added to `.gitignore`.

Three files per run:

- **`config.json`** — resolved CLI args, Rytm port name, LPD8 status (connected/keyboard fallback), pad_config snapshot (machine_filter, fixed_ccs, cc_value_caps). The snapshot is what makes M3's replay reproducible without re-reading source.
- **`generations.jsonl`** — one line per generation:
  ```json
  {"gen": 0, "best_fitness": 5.0, "avg_fitness": 3.2, "min_fitness": 1.0,
   "best_individual": [3, 64, ...], "n_evaluated": 4}
  ```
- **`votes.jsonl`** — one line per evaluation:
  ```json
  {"gen": 0, "eval_idx": 0, "machine": 13, "evolved_ccs": {"17": 64, "109": 60, ...},
   "fixed_ccs": {"70": 0, ...}, "vote": 5, "timestamp_iso": "2026-06-10T14:22:31"}
  ```

`f.flush()` after every JSONL line so Ctrl-C never loses a row. Stdlib `json` + `pathlib` only.

### Gen / eval_idx plumbing

DEAP's `algorithms.eaMuPlusLambda` doesn't pass `gen` or `eval_idx` to the evaluate function. Two options were considered:

1. Use stock `eaMuPlusLambda` + a `tools.Logbook` and derive logs from it post-hoc.
2. Replicate the `eaMuPlusLambda` body inline (≈20 lines) so we own the loop and can stamp `gen` on each evaluation as it happens.

Going with option 2. The inline loop lets us also write `generations.jsonl` cleanly per-gen, place the Ctrl-C boundary at a natural gen edge, and update `best_so_far` (used by the replay callback) at the same point. Trade-off is owning a small bit of DEAP plumbing; benefit is that all per-run state lives in one place.

Mechanism: a small `state = {'gen': 0, 'eval_idx': 0}` dict in the driver closure, passed into `make_evaluate(...)`. The evaluator reads `state['gen']`, increments `state['eval_idx']`, and writes the `votes.jsonl` line via a `vote_logger` callback. The driver bumps `state['gen']` after each generation, resets `eval_idx` to 0.

### Replay-best

`LPD8VoteController.get_vote(on_replay=None, replay_cc=1)`:

```
loop on port.iter_pending():
    if msg.type == 'note_on' and 36 <= msg.note <= 43: return vote
    if msg.type == 'control_change' and msg.control == replay_cc and on_replay:
        on_replay()
        # keep waiting for a real vote
```

Driver wires `on_replay = lambda: _replay(best_so_far)`. `_replay` re-sends machine CC + param CCs + trig note through the same path `evaluate()` uses — so we extract that send logic into a small helper in `evaluate.py` (`send_individual(...)`) and both `evaluate()` and the replay callback call it.

`best_so_far` updates after each generation from `tools.HallOfFame(1)`. If user hits replay before any generation completes, callback is a no-op with a printed "no champion yet".

### Elitism

`tools.HallOfFame(1)` plus inline `mu+lambda` selection with `mu = pop_size`, `lambda_ = pop_size`. The HoF doubles as the source of `best_so_far` for replay, so there's no separate champion tracking.

### Graceful shutdown

`try / except KeyboardInterrupt` around the generation loop body. On Ctrl-C:

1. JSONL flushing on each write means files are already consistent.
2. Print: run directory path, current generation, best-so-far fitness + machine + evolved CCs.
3. Exit 0.

The M2 spec mentions a `mido` signal-handling caveat (`for msg in port` blocks in C). The voter already uses `port.iter_pending()` inside a `while True` loop, which is poll-friendly — so a Ctrl-C during vote-wait should land. Will verify during implementation; if it doesn't, add a `time.sleep(0.01)` between polls to keep the GIL handing back to Python.

### Testing

Device-free tests in `tests/`:

- **`tests/test_logging.py`** (new):
  - `make_run_dir()` creates a unique directory under a tmpdir
  - `log_generation()` and `log_vote()` write parseable JSON lines
  - Re-opening and reading the JSONL back round-trips
- **`tests/test_cli.py`** (new):
  - Defaults parse with no args
  - All flag overrides parse to the right types
  - `--midi-channel` omitted → defaults to `--pad`
- **`tests/test_parameters.py`** — verify no longer depends on module-import seeding being magical (existing tests should still pass; if any silently relied on `seed(time())` they'll need an explicit `random.seed(...)` in setUp).

Manual hardware verification per the M2 spec's verification block (CLI runs end-to-end, run dir populated, replay knob works, Ctrl-C exits cleanly, elitism preserves champion).

## Verification

```bash
source ./activate_virtualenv.sh

# Device-free tests pass
python -m unittest tests.test_parameters tests.test_logging tests.test_cli

# CLI surface
python -m genetic.main --help
python -m genetic.main --pad 0 --generations 3 --seed 42

# Run dir layout
ls runs/                                          # 2026-06-10-*-pad0/
cat runs/2026-06-10-*-pad0/config.json            # resolved args + pad_config snapshot
wc -l runs/2026-06-10-*-pad0/generations.jsonl    # == 4  (gen 0 + 3 more)
wc -l runs/2026-06-10-*-pad0/votes.jsonl          # <= pop_size * 4 = 16  (eaMuPlusLambda only re-evaluates invalid individuals; direct-copy offspring inherit fitness and skip evaluation)

# Seed reproducibility
python -m genetic.main --pad 0 --generations 1 --seed 42 --no-log
python -m genetic.main --pad 0 --generations 1 --seed 42 --no-log
#   → identical initial population (verify by reading printed Pad-summary or adding a debug dump)

# Manual hardware:
#   - Twist LPD8 knob 1 mid-run → champion sound replays, vote still pending
#   - Vote 8 in gen 0, vote 1 thereafter → best_fitness stays at 8 in generations.jsonl (elitism)
#   - Ctrl-C mid-run → run dir + champion summary printed, exit 0
```

## Non-goals (deferred to later milestones)

- Saving champions as named, reloadable patches — M3.
- Resuming a stopped run from `runs/` — M3.
- Smarter fitness (multi-vote, A/B) — M4.
- Removing module-level `AnalogRytmMidiMessageCollectionSender` randomization in `__init__` — M5.

## Files

**New:**
- `genetic/cli.py`
- `genetic/logging.py`
- `tests/test_cli.py`
- `tests/test_logging.py`

**Modified:**
- `genetic/main.py` — argparse wiring, inline mu+lambda loop, try/except, champion summary
- `genetic/evaluate.py` — extract `send_individual()` helper, accept `state` + `vote_logger`
- `user_interface/voter.py` — `on_replay` callback in `get_vote()`
- `synthesizer/parameters.py` — remove module-level `seed(time())`
- `synthesizer/midicontrol.py` — remove module-level `seed(time())`
- `.gitignore` — add `runs/`
- `CLAUDE.md` — mark the RNG-seeding gotcha resolved; refresh the "Common commands" block with the new CLI usage
- `README.md` — replace M1 run instructions with M2 CLI examples + run-directory description
