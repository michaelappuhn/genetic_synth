# Huh?
This is an attempt to map [DeLanda's usage](https://web.archive.org/web/20240203233005/https://www.cddc.vt.edu/host/delanda/pages/algorithm.htm) of the [genetic algorithm](https://www.youtube.com/watch?v=50-d_J0hKz0) as a generative process to for synthesizer parameters. The goal is to create patches that are interesting, generative, and surprising, rather than sticking to a few default behaviors of patch-making.

It works by:

 - iterating through randomized values for the synth
 - applying quanitative "fit" measures of "intensity" to them
 - honing them over generations. 

   The "intensive property" here is (unfortunately) the users' own subjective sense of the sound quality. To facilitate this, I'm creating a 1 to 8 "voting system" based on the [LPD-8](https://www.akaipro.com/lpd8), which I have lying around. Totally unnecessary, but feels nicer than a keyboard.

## Running

Prerequisites:
- Elektron Analog Rytm MKII connected (MIDI port name: `Elektron Analog Rytm MKII`)
- Akai LPD8 on Prog1 (port name: `LPD8`) — optional, falls back to keyboard input if missing
- Python venv set up: `source ./activate_virtualenv.sh` (or `source venv/bin/activate`)
- Dependencies installed: `pip install -r requirements.txt`

Start a GA run:

```bash
source ./activate_virtualenv.sh
python -m genetic.main
```

This runs the M1 loop: channel 0 (BD voice, 17 machines), population 4, 5 generations. Each candidate plays one trig on the Rytm and waits for a 1–8 vote from the LPD8 (or keyboard). Configuration is currently hardcoded at the top of `genetic/main.py` — CLI flags arrive in M2.

Tests:

```bash
./unittests.sh                                # full suite (requires Rytm connected)
python -m unittest tests.test_parameters      # device-free unit tests only
```

## Customizing the search space

The single most important customization point is **`genetic/pad_config.py`**. For each pad (0=BD, 1=SD, ... — see `kits_10.md`), it declares:

- **`machine_filter`** — which machines from `avail_machines_by_channel[pad]` the GA may pick (e.g. BD-only on pad 0).
- **`fixed_ccs`** — CCs that should NOT evolve. Map a CC to `DEFAULT` (keep the canonical CSV value) or to an integer to pin it (e.g. `82: 0` to zero out the delay send).
- **`cc_value_caps`** — per-CC bound overrides. Use for bipolar params: cap centered on MIDI 64 (e.g. `(58, 70)` for a tight Tune range, `(54, 74)` for subtle LFO depth).

Pads not in `PAD_CONFIG` evolve every curated CC with no machine filter (the M1 default). To target a different voice, change `PAD` at the top of `genetic/main.py`. If your Rytm MIDI routing reassigns pads to different channels, override `MIDI_CHANNEL` separately.

## Reference materials

Beyond this README, see:

- **`CLAUDE.md`** — codebase tour and gotchas.
- **`docs/specs/`** — milestone specs M0-M7. `M0` and `M1` are shipped; later milestones are planned.
- **`docs/Analog-Rytm-MKII-User-Manual_ENG_OS1.72.pdf`** — official Elektron manual. Appendix C is the MIDI implementation chart; Appendix D describes every machine's SRC parameters.
- **`docs/rytm-machine-ranges.csv`** — audit of all 36 Rytm machines + shared Filter/Amp/LFO pages, classifying every CC slot as `linear` / `bipolar` / `discrete`. Use this when picking caps in `pad_config.py` — bipolar params need centered ranges, not capped extremes.
- **`kits_10.md`** — which machines are valid per Rytm channel (1-based labels; subtract 1 for the 0-based MIDI values the code uses).
- **`synthesizer/rytm-limited.csv`** — curated runtime parameter map. **`Rytm MKII.csv`** at the repo root is the full upstream CC map.
