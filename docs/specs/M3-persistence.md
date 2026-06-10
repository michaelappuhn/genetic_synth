# M3 — Persistence

## Context

M2 logs everything that happened, but a champion is still just a row in a JSONL file. To use these sounds musically — across sessions, in a track, on the device itself — they need to be first-class artifacts: named, reloadable, and ideally writable back to the Rytm as actual kit slots. This milestone makes the GA's output durable.

## Scope

**In:**
- Save champions to disk as named, reloadable JSON patches
- Load a saved patch and audition it directly (no GA run required)
- Resume a stopped run from its `runs/` directory
- Seed a new run from a saved patch (use champion as a starting point, mutate around it)

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

Reads the last generation's individuals from `generations.jsonl`, reconstructs the DEAP `Individual` objects (with fitnesses), and continues with `eaMuPlusLambda`. Append to the same `generations.jsonl` and `votes.jsonl`.

Caveat: the config (pop size, mutation rate, channel, bounds) must come from the original `config.json`, not new CLI flags. Resume should refuse if CLI args conflict with `config.json` unless `--override` is passed.

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

## Files

New:
- `patches/` directory (gitignored — these are personal artifacts)
- `genetic/patches.py` — `save()`, `load()`, `to_individual()`, `from_individual()`
- `genetic/cli.py` — extracted argparse setup with subcommands

Touched:
- `genetic/main.py` — wire `save-best`, `play`, `resume`, `--seed-from-patch`
- `genetic/logging.py` — add a `read_last_generation(run_dir)` helper

## Verification

```bash
# Run, then save champion
python -m genetic.main run --channel 2 --generations 5
python -m genetic.main save-best runs/2026-*/ --name test-patch
ls patches/test-patch.json

# Play it without re-running GA
python -m genetic.main play test-patch
# - Plays one trig on the Rytm, matches what was heard at end of run

# Resume that run
python -m genetic.main resume runs/2026-*/
# - Picks up at generation 6, same channel, same bounds

# Seed-from-patch
python -m genetic.main run --channel 2 --seed-from-patch test-patch --generations 3
# - Initial population contains the saved patch; first audition sounds identical to `play`
```

Patches survive a delete + checkout cycle (they're plain JSON), and `play` on a patch saved months ago still produces the same sound (assuming the Rytm firmware hasn't changed the CC mapping).
