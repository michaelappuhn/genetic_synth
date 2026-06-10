# M2 — Quality of life

## Context

After M1, the GA runs but the experience is rough: hardcoded config means editing source between runs, there's no record of what happened, no way to re-hear the best sound without finishing the run, and Ctrl-C loses everything. This milestone makes the tool usable for actual sound-design sessions (an hour at the Rytm, dozens of generations) without losing work or your place.

## Scope

**In:**
- CLI config (channel, pop size, generations, mutation/crossover rates, tournament size, seed)
- Per-generation logging to disk
- "Replay best" hotkey on the LPD8 that re-sends the best-so-far without consuming a vote
- Elitism so champions survive
- Graceful Ctrl-C: print state, exit cleanly

**Out:**
- Saving champion patches as named, reloadable artifacts (M3)
- Resuming a stopped run from disk (M3)
- Smarter fitness signal (M4)

## Approach

### CLI

Use `argparse`. One subcommand for now, `run`:

```
python -m genetic.main run \
  --channel 2 \
  --pop-size 4 \
  --generations 10 \
  --mutation-rate 0.15 \
  --crossover-rate 0.5 \
  --tournament-size 2 \
  --seed 42
```

Defaults match M1's hardcoded values so existing muscle memory still works.

### Logging

Each run writes to `runs/YYYY-MM-DD-HHMM/`:
- `config.json` — the resolved CLI args + Rytm port name + LPD8 status
- `generations.jsonl` — one line per generation: `{gen, best_fitness, avg_fitness, best_individual}`
- `votes.jsonl` — one line per evaluation: `{gen, individual_idx, genome, vote, timestamp}`

Use stdlib `json` + `pathlib`. No new dependencies.

### Replay-best

The LPD8's Prog1 maps pads 1–8 to votes (notes 36–43). Reserve **one CC knob** (any of the 8 LPD8 knobs sends CC) as "replay best": when the voter sees that CC, it re-sends the best-so-far's machine + CCs + trig and continues waiting for an actual vote. No vote is recorded for the replay.

Implementation lives in `LPD8VoteController.get_vote()` — give it an optional `on_replay` callback so the voter doesn't need to know about the GA. The driver wires `on_replay = lambda: send(best_so_far)`.

### Elitism

Swap `algorithms.eaSimple` for `algorithms.eaMuPlusLambda` with `mu = pop_size`, `lambda_ = pop_size`. Champions never get evicted by a bad generation.

### Graceful shutdown

Wrap the main loop in `try / except KeyboardInterrupt`. On Ctrl-C:
- Finish writing the current `generations.jsonl` line
- Print the path to the run directory + the best individual seen so far
- Exit 0

### Signal-handling caveat

`mido`'s `for msg in port:` blocks inside C code; Python signals only deliver between Python opcodes. Ctrl-C during a vote-wait may not return promptly. Fix in M2 if it's annoying in practice; defer otherwise. The likely fix: switch the LPD8 read to `port.poll()` in a small loop.

## Files

Touched:
- `genetic/main.py` — argparse, run directory setup, swap to `eaMuPlusLambda`, try/except wrapper
- `genetic/evaluate.py` — write `votes.jsonl` line per evaluation
- `user_interface/voter.py` — add `on_replay` callback to `LPD8VoteController.get_vote()`, recognize the replay CC

New:
- `genetic/logging.py` — small helpers: `make_run_dir()`, `log_generation()`, `log_vote()`

## Verification

```bash
# CLI works, defaults sensible
python -m genetic.main run --help
python -m genetic.main run --channel 2 --generations 3

# Run dir exists and is populated
ls runs/
ls runs/2026-*/
cat runs/2026-*/config.json
wc -l runs/2026-*/generations.jsonl   # == 3
wc -l runs/2026-*/votes.jsonl         # == pop_size * (generations + 1)  (initial pop is gen 0)

# Replay-best (manual): mid-run, twist the designated knob — best-so-far should sound again without advancing
# Graceful exit (manual): Ctrl-C mid-run — should print run dir + champion, exit 0

# Elitism: vote 8 on one candidate in gen 0, vote 1 on everything afterwards.
# The best_fitness in generations.jsonl should never drop below 8.
```
