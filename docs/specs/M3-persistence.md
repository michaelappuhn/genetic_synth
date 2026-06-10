# M3 — Persistence

## Context

M2 logs everything that happened, but a champion is still just a row in a JSONL file. To use these sounds musically — across sessions, in a track, on the device itself — they need to be first-class artifacts: named, reloadable, and ideally writable back to the Rytm as actual kit slots. This milestone makes the GA's output durable.

## Scope

**In:**
- Save champions to disk as named, reloadable JSON patches
- Load a saved patch and audition it directly (no GA run required)
- Resume a stopped run from its `runs/` directory
- Seed a new run from a saved patch (use champion as a starting point, mutate around it)
- Clean up dead code in `user_interface/voter.py` left over from pre-M0 (see "Cleanup" below)
- Robustify `make_run_dir` against same-minute collisions (see "Cleanup")

**Out:**
- SysEx dump back to the Rytm — kept as a stretch goal in this spec, owned by M3.5 if it lands
- Any kind of patch browser / GUI

## Approach

### Patch format

`patches/<name>.json`:

```json
{
  "version": 1,
  "name": "kraken-bd-acoustic",
  "channel": 2,
  "machine_number": 31,
  "machine_name": "bd acoustic",
  "parameters": [
    {"cc": 16, "value": 87, "name": "Synth parameter 1"},
    ...
  ],
  "fitness": 8.0,
  "source": {
    "run_dir": "runs/2026-06-09-1430",
    "generation": 4,
    "individual_idx": 1
  }
}
```

The `parameters` block carries CC + value + name so the patch is human-readable and survives changes to the CSV ordering. The full enumeration is kept (not just non-defaults) so loading is deterministic.

### Save command

```bash
python -m genetic.main save-best <run-dir> --name <patch-name>
```

Reads the best individual from `<run-dir>/generations.jsonl`, decodes it via the same logic the evaluator uses, writes `patches/<patch-name>.json`. If `--name` is omitted, prompt or auto-name from `<run-dir>` + timestamp.

### Audition command

```bash
python -m genetic.main play <patch-name>
```

Loads the patch JSON, opens the Rytm connection, sends machine + CCs + a single trig. No GA. Good for A/B-ing patches outside a run.

### Resume command

```bash
python -m genetic.main resume <run-dir>
```

Reads the last generation's individuals from `generations.jsonl`, reconstructs the DEAP `Individual` objects (with fitnesses), and continues with the same inline `mu+lambda` loop M2 uses. Append to the same `generations.jsonl` and `votes.jsonl`.

Caveat: the config (pop size, mutation rate, pad, midi-channel, bounds) must come from the original `config.json`, not new CLI flags. Resume should refuse if CLI args conflict with `config.json` unless `--override` is passed.

### Seed-from-patch

```bash
python -m genetic.main run --seed-from-patch <patch-name> --generations 10
```

Loads the patch and uses it as one of the initial population members; the rest are random. Lets you say "this kick is almost right, evolve around it."

### Stretch: SysEx dump to Rytm

The Rytm accepts SysEx kit dumps. With a champion in memory, it's possible to write it to a specific kit slot via SysEx. This requires:
- Researching the Rytm MKII SysEx kit format (Elektron has published docs; community libraries exist)
- Mapping our flat CC list to the full Rytm sound structure
- Testing on hardware

This is a meaningful chunk of work and reasonably independent. **Recommended: ship M3 without it, then decide.** If wanted, it becomes M3.5 with its own short spec.

### Cleanup

Two carryover items surfaced by the M2 final review. Small, independent, ship them alongside the persistence work.

**`user_interface/voter.py` dead code** — Pre-M0 module-level functions (`VotingSystem`, `VoteProcessor`, `get_lpd8_port`, `lpd8_vote`, `vote(port)`, the module-level `main()`) and the unused `VoteController.give_instructions()` stubs are still on disk. M1's `LPD8VoteController` and `KeyboardVoteController` are the live path; the rest is dead. Delete ~80 lines so the file reads as just the two controller classes the GA driver actually uses. `keyboard_vote()` (module-level, called by `KeyboardVoteController.get_vote()` via `keyboard_vote_instructions()` / recursion) needs review — fold its logic into the controller method, or keep just the helpers it actually references.

**`make_run_dir` same-minute collision** — `genetic/logging.py:make_run_dir()` uses `mkdir(exist_ok=False)` with minute-resolution timestamps. Starting a run, Ctrl-C, restarting within the minute raises a bare `FileExistsError`. Add a seconds-resolution fallback (or a short suffix like `-1`, `-2`) so the user can iterate quickly without waiting out the clock. M3 needs to write to these directories from `save-best` and `resume` anyway, so it's a natural place to harden the format.

## Files

New:
- `patches/` directory (gitignored — these are personal artifacts)
- `genetic/patches.py` — `save()`, `load()`, `to_individual()`, `from_individual()`

Touched:
- `genetic/cli.py` — already exists from M2; extend with subcommand structure (`run`, `save-best`, `play`, `resume`)
- `genetic/main.py` — wire `save-best`, `play`, `resume`, `--seed-from-patch`
- `genetic/logging.py` — add `read_last_generation(run_dir)` helper; harden `make_run_dir` against same-minute collisions
- `user_interface/voter.py` — delete dead pre-M0 module-level code

## Verification

```bash
# Run, then save champion
python -m genetic.main run --pad 2 --generations 5
python -m genetic.main save-best runs/2026-*/ --name test-patch
ls patches/test-patch.json

# Play it without re-running GA
python -m genetic.main play test-patch
# - Plays one trig on the Rytm, matches what was heard at end of run

# Resume that run
python -m genetic.main resume runs/2026-*/
# - Picks up at generation 6, same channel, same bounds

# Seed-from-patch
python -m genetic.main run --pad 2 --seed-from-patch test-patch --generations 3
# - Initial population contains the saved patch; first audition sounds identical to `play`
```

Patches survive a delete + checkout cycle (they're plain JSON), and `play` on a patch saved months ago still produces the same sound (assuming the Rytm firmware hasn't changed the CC mapping).
