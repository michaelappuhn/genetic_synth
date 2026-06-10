# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A genetic-algorithm-driven sound design tool for the **Elektron Analog Rytm MKII** drum machine. The GA randomizes synth parameters, sends them over MIDI as CC messages, and uses the user's subjective vote (1–8 from an Akai LPD8 pad controller, or keyboard fallback) as the fitness function. Inspired by Manuel DeLanda's framing of the genetic algorithm as a generative process — the "intensive property" being driven up over generations is the user's perception of sound quality.

M0 (foundation cleanup), M1 (end-to-end GA loop), and M2 (quality of life — CLI, logging, replay-best, elitism, graceful Ctrl-C) are done. `genetic/` wires DEAP to the existing `synthesizer/` and `user_interface/` code; `python -m genetic.main --help` shows the CLI surface. Future milestones (M3 persistence, M4 better fitness, M5 device abstraction, M6 Mopho, M7 multi-device) are specced in `docs/specs/`.

## Common commands

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

## Architecture

Three packages plus reference data:

- **`synthesizer/`** — parameter modeling and MIDI output.
  - `parameters.py` is the live data layer: `Parameter` (cc + value + min/max + name, with bounds clamping in `set_value`), `ParameterCollection` (a `UserList` of `Parameter`s — this is what a "patch" is), and `ParameterCSVReader` / `AnalogRytmParameterCSVReader` which build collections from `rytm-limited.csv`. The Rytm reader filters to `Synth, general`, `Filter`, `Amp`, `LFO` sections only.
  - `midicontrol.py` is the live MIDI layer, wrapping `mido`. Hierarchy: `MidiConnection` → `MidiMessage` / `MidiCCMessage` → `MidiMessageCollectionSender` → `AnalogRytmMidiMessageCollectionSender`. The Rytm sender also owns machine selection via `AnalogRytmMachineSelector`. Note: the GA driver bypasses `AnalogRytmMidiMessageCollectionSender` (which randomizes internally) and uses the parent class directly — see `genetic/evaluate.py`.

- **`genetic/`** — the GA layer on top of DEAP.
  - `genome.py` — `apply_pad_config` splits canonical params into evolved-in-genome vs fixed-each-evaluation; `build_bounds`, `make_individual`, `bounded_mutate` are the DEAP-facing pieces.
  - `evaluate.py` — `make_evaluate` builds the fitness closure: decode genome → clone canonical params → apply evolved values + fixed values → send machine CC → send all param CCs → trigger note → block on voter.get_vote().
  - `pad_config.py` — **per-pad customization point**. For each pad, declares (a) which machines from `avail_machines_by_channel[pad]` are allowed, (b) which CCs to pin to fixed values, (c) per-CC bound overrides (e.g. centered caps for bipolar params). Pad 0 is configured for BD-kick search; other pads default to "evolve everything".
  - `main.py` — driver. Argparse layer (`--pad`, `--midi-channel`, GA hyperparams, `--seed`, `--no-log`) → seed RNG → make `runs/` directory → DEAP toolbox → inline `mu+lambda` loop with HallOfFame elitism, replay-best callback, and per-vote/per-generation JSONL logging. `--midi-channel` defaults to `--pad`; override when Rytm MIDI routing reassigns pads to different channels.

- **`user_interface/voter.py`** — fitness input. `LPD8VoteController` listens for `note_on` 36–43 from an Akai LPD8 (must be on **Prog1**) and maps them to votes 1–8. `KeyboardVoteController` is the fallback. These are the fitness function for the GA.

- **`tests/`** — `unittest` style. `test_parameters.py` is pure unit tests (device-free). `test_midicontrol.py` opens a real MIDI connection in `setUpModule` and several tests actually send notes/CC to the device — they will fail unless a port named `Elektron Analog Rytm MKII` is connected.

### Reference data

- **`synthesizer/rytm-limited.csv`** — curated CC subset the runtime actually loads (Synth-general + Filter + Amp + LFO). **`Rytm MKII.csv`** at the repo root is the full upstream CC map from `pencilresearch/midi`.
- **`kits_10.md`** — documents which Rytm machine numbers are valid per channel. Source of truth for `avail_machines_by_channel`. Code uses 0-based machine numbers (kits_10 lists 1-based + 0-based; we apply -1 to convert).
- **`docs/Analog-Rytm-MKII-User-Manual_ENG_OS1.72.pdf`** — official Elektron manual (OS 1.72). Appendix C is the MIDI implementation chart, Appendix D is per-machine parameter descriptions.
- **`docs/rytm-machine-ranges.csv`** — audit derived from the manual. For every machine (36 of them) and every CC slot, classifies the parameter as `linear` / `bipolar` / `discrete` so that future per-pad configs can pick the right bound style. Bipolar params (Tune, Sweep Depth, Detune, Balance, etc.) need ranges **centered on MIDI 64**, not capped at extremes.
- **`docs/specs/`** — milestone specs (M0-M7). See `docs/specs/README.md` for the index.

## Gotchas

- **MIDI tests require hardware.** `tests/test_midicontrol.py` opens a `MidiConnection('Elektron Analog Rytm MKII')` in `setUpModule` and several tests actually send notes/CC. Run `python -m unittest tests.test_parameters` alone for device-free work.
- **Channel numbering.** `kits_10.md` lists both 1-based human labels and 0-based; all code uses **0-based** internally. `AnalogRytmMachineSelector.avail_machines_by_channel[i]` is indexed by 0-based channel directly. kits_10's listed machine numbers are 1-based — convert by subtracting 1.
- **Bipolar parameters need centered caps.** Many Rytm params are bipolar around MIDI 64 (Tune, Sweep Depth, Detune, Balance, Pan, Filter Env Depth, LFO Depth, LFO Speed, LFO Fade). Capping to `(0, 40)` samples only the "inverted modulation" half. See `docs/rytm-machine-ranges.csv` for the full per-machine type map.
- **CSV-driven ranges are not authoritative.** `rytm-limited.csv` ranges (and the full `Rytm MKII.csv`) are community-curated, not vendor-published. The manual's MIDI implementation chart (Appendix C) confirms CC assignments but does NOT publish numeric MIDI ranges per machine. Use `docs/rytm-machine-ranges.csv` for orientation (linear/bipolar/discrete); pick musical ranges by ear.
- **Pad ≠ MIDI channel.** `--pad` (semantic; drives the machine palette and pad_config lookup) is separate from `--midi-channel` (where MIDI sends actually go). `--midi-channel` defaults to `--pad`. Override when Rytm MIDI routing reassigns pads to different channels for external-device triggering.
- **GA bypasses the high-level Rytm sender.** `AnalogRytmMidiMessageCollectionSender.__init__` randomizes parameters and picks a machine internally. The GA driver (`genetic/evaluate.py`) constructs the parent `MidiMessageCollectionSender` directly to avoid that — the GA owns randomization, not the sender. M5 is slated to remove the high-level sender's embedded randomization.
- **RNG seeded by the driver, not at import.** `genetic.main.run()` calls `random.seed(args.seed)` after CLI parse; the seed is logged in `config.json` so any run is reproducible by passing `--seed <N>`.
