# M0 — Foundation cleanup

## Context

The repo is mid-refactor. Before adding the GA layer, three sharp edges need filing down: (1) modules run code at import time, (2) `synth_data.py` duplicates `parameters.py` with a broken import path, (3) `test_midicontrol.py` opens a real MIDI port at module import, so any test run requires the Rytm to be plugged in. None of this blocks M1 in isolation, but each one will bite repeatedly as the GA code grows.

## Scope

**In:**
- Guard `main()` calls behind `if __name__ == "__main__":`
- Remove `synthesizer/synth_data.py`
- Decide on `z-old/` — keep nothing on the import path
- Add `deap` to `requirements.txt`
- Move device-dependent test setup out of module scope

**Out:**
- Any genetic algorithm code (M1)
- Renaming public APIs of `Parameter` / `ParameterCollection` / `MidiConnection`

## Approach

### Module-level `main()` calls

Three files call `main()` at the bottom unconditionally:
- `synthesizer/midicontrol.py:204` — body is currently commented out; the call is harmless but the pattern is a trap
- `synthesizer/synth_data.py:50` — runs a CSV read on import
- `user_interface/voter.py:204` — instantiates `LPD8VoteController` and blocks on a MIDI read

Wrap each with `if __name__ == "__main__":`. This is the single change that lets the GA driver import these modules without side effects.

### Drop `synth_data.py`

It predates `parameters.py`, does the same job, and imports `from parameters import ...` (no package prefix) — it only works when run from inside `synthesizer/`. Delete the file. Nothing in `synthesizer/midicontrol.py`, `tests/`, or `user_interface/` imports it.

### `z-old/` triage

The user has flagged this as not necessary. `z-old/genetic.py` is worth keeping as a reference for what an end-to-end loop looked like; the rest can go. Options:
- Delete the whole directory and rely on git history
- Keep `z-old/genetic.py` as `docs/reference/legacy-genetic.py` with a one-line README explaining where it came from

Recommended: delete the directory. Git preserves it.

### Add `deap`

Append `deap==1.4.1` (latest stable as of writing) to `requirements.txt`. Verify install in the existing `venv`.

### Test isolation

`tests/test_midicontrol.py:9` does `conn = MidiConnection('Elektron Analog Rytm MKII')` at module scope. Move it into each test class's `setUp` (or a `setUpClass`) so importing the module doesn't open a port. This lets `python -m unittest tests.test_parameters` run without the Rytm connected.

## Files

- `synthesizer/midicontrol.py` — guard `main()`
- `synthesizer/synth_data.py` — delete
- `user_interface/voter.py` — guard `main()`
- `requirements.txt` — add `deap`
- `tests/test_midicontrol.py` — move `MidiConnection(...)` into test setup
- `z-old/` — delete

## Verification

```bash
# Device-free path
python -m unittest tests.test_parameters         # should pass with no Rytm

# Importability check
python -c "from synthesizer.midicontrol import AnalogRytmMidiMessageCollectionSender; print('ok')"
python -c "from user_interface.voter import LPD8VoteController; print('ok')"
# Neither should print anything beyond 'ok' — no MIDI port operations, no blocking reads

# DEAP installed
python -c "import deap; print(deap.__version__)"

# With Rytm + LPD8 connected, full suite still passes
./unittests.sh
```
