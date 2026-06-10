# M6 — Mopho port

## Context

M5 introduces the `Device` abstraction but only validates it against the Rytm — the device that shaped the original code. Until a structurally different device runs end-to-end, the abstraction is unproven. The Mopho is that test: it's a monosynth (no machine-style categorical selection), it uses both CC and NRPN for parameter writes, and it wants sustained audition rather than a percussion trig. If M5's design is right, M6 should be almost entirely data + a small descriptor file, with no further refactoring of the GA, sender, or audition code.

The pencilresearch `Mopho x4.csv` covers ~43 CC parameters (oscillators, filter, amp, envelope 3, clock). The Mopho's LFOs (×4), modulation matrix, full envelopes 1 & 2, sequencer, and arpeggiator are NRPN-only and absent from that file. M6 includes transcribing those from the Mopho user manual's MIDI implementation appendix — without that data extension, NRPN is never exercised against hardware and M5 stays structurally unvalidated.

## Scope

**In:**
- Extended `mopho.csv` covering both CC params (from pencilresearch) and NRPN params (from the manual)
- `devices/mopho.json` generated from the CSV via M5's `scripts/build_device_json.py`
- `devices/mopho.py` device descriptor
- Hardware-gated test verifying the Mopho responds to a single CC and a single NRPN write
- End-to-end GA run on Mopho via `python -m genetic.main run --device mopho`

**Out:**
- Mopho preset/program management (program change parameter selection — could come later)
- Mopho SysEx patch dump (analogous to the Rytm SysEx stretch in M3.5)
- Sequencer / arpeggiator *control* via the GA (parameters are exposed for read/edit, but evolving sequencer patterns is a different problem)

## Approach

### Hardware notes

The Mopho enumerates on macOS under a variable port name depending on USB vs MIDI cable — commonly `Mopho`, `Mopho Keyboard`, `Mopho SE`, or appears via a USB MIDI interface as the interface's port name. The descriptor's `port_name` should be the exact string `mido.get_output_names()` returns; if it differs from `"Mopho"`, the spec recommends adding a small CLI flag `--port-override` in M5 (or just editing `mopho.py`).

The original Mopho is monophonic but accepts on multiple MIDI channels (configurable via global setting). Default MIDI channel is 1. The Mopho x4 maps each of its 4 voices to its own channel by default; the user's original Mopho will be channel 1.

### Building `mopho.csv`

Start with the 43 rows from pencilresearch `Mopho x4.csv` — these apply identically to the original Mopho. Then transcribe NRPN rows from the Mopho user manual's MIDI implementation chart. The chart enumerates every NRPN-addressable parameter with its NRPN number, value range, and a short description. Target parameter groups (rough count from the manual):

- **LFO 1–4**: frequency, shape, amount, destination, sync, key sync (≈ 24 params)
- **Modulation matrix**: 4 slots × {source, destination, amount} (≈ 12 params)
- **Envelope 1 (Filter)** and **Envelope 2 (Amp)**: delay/attack/decay/sustain/release for each (Envelope 1's params overlap with the CC chart; record once, prefer the CC form where it exists) (≈ 8 NRPN params for Env 2 amount/velocity/repeat plus any not covered by CC)
- **Arpeggiator**: mode, range, clock divide (≈ 4 params)
- **Misc**: oscillator slop, glide mode, pitch wheel range, mod wheel amount, push-it parameters (≈ 10 params)

Realistic total: ~100 NRPN rows + the 43 CC rows = ~140 parameters. That's a meaty genome — the GA will be slower per generation than on the Rytm but the search space is *much* more interesting.

CSV columns must match pencilresearch's schema so the same M5 loader works:

```
manufacturer,device,section,parameter_name,parameter_description,
cc_msb,cc_lsb,cc_min_value,cc_max_value,cc_default_value,
nrpn_msb,nrpn_lsb,nrpn_min_value,nrpn_max_value,nrpn_default_value,
orientation,notes,usage
```

For each row, either the `cc_*` columns or the `nrpn_*` columns are populated, not both. The M5 loader chooses the address type based on which set is present.

### Device descriptor

```python
# synthesizer/devices/mopho.py
from genetic.audition import SustainedNoteAudition
from synthesizer.devices.registry import Device, load_parameters_from_json

mopho = Device(
    name="mopho",
    port_name="Mopho",  # adjust per actual mido.get_output_names()
    parameters=load_parameters_from_json("synthesizer/devices/mopho.json"),
    audition=SustainedNoteAudition(note=48, duration_ms=1500),  # C3, 1.5s
    categorical_selection=None,
    program_change=None,
)
```

### Audition tuning

`SustainedNoteAudition(note=48, duration_ms=1500)` is the starting point. C3 (note 48) lands in the Mopho's filter sweet spot for most patches; 1.5s lets a slow attack/release patch breathe. The exact values are user-tunable per run via a CLI flag (`--audition-note`, `--audition-duration`). Recommend leaving the note fixed across a session so votes are comparable.

### Mutation rate

The Mopho genome is ~3× the Rytm's size. A flat mutation rate of 0.15 produces ~21 mutations per individual, which is musical noise. Recommend defaulting `--mutation-rate` lower for Mopho runs (try 0.05) — M2's adaptive mutation will catch the rest. The device descriptor can carry a `recommended_mutation_rate` for the driver to pick up.

## Files

New:
- `synthesizer/devices/mopho.csv` — full parameter map (CC + NRPN, transcribed)
- `synthesizer/devices/mopho.json` — generated from CSV
- `synthesizer/devices/mopho.py` — descriptor
- `tests/test_devices_mopho.py` — unit test for descriptor load; hardware-gated live test

Touched:
- `synthesizer/devices/registry.py` — register `mopho`
- `README.md` (project-level) and `docs/specs/README.md` — hardware requirement note

## Verification

### Without hardware

```bash
# Descriptor loads cleanly
python -c "from synthesizer.devices.mopho import mopho; print(len(mopho.parameters), 'params')"
# - Prints a number close to 140

# Unit tests
python -m unittest tests.test_devices_mopho.TestMophoDescriptor
```

### With hardware

```bash
# Mopho responds to a single CC and a single NRPN — sanity before any GA run
python -m genetic.main probe --device mopho --param "Filter frequency" --value 0
python -m genetic.main probe --device mopho --param "Filter frequency" --value 127
python -m genetic.main probe --device mopho --param "LFO 1 rate"      --value 8192   # NRPN
# - For each: the Mopho's screen / sound responds in the expected direction

# End-to-end GA run
python -m genetic.main run --device mopho --channel 1 --generations 5 --mutation-rate 0.05
# - LPD8 voter prompts for 1-8 after each sustained note
# - Champion at end is a Mopho patch that can be reproduced via `play` (M3)
```

Success criterion: a run produces audibly distinct timbres across generations, the user can sit through a session without the audition feeling too short or too long, and at least one NRPN-only parameter (LFO destination is a good one to watch) demonstrably varies across the run.

## Open questions deferred to implementation

- **Mopho NRPN parameter throughput.** Sending 140 parameter writes per individual is ~560 MIDI messages (4 per NRPN). At 31.25 kbps (5-pin DIN MIDI), that's ~180 ms of bus time per evaluation — noticeable but tolerable. USB MIDI is faster. If latency is bad, add a small inter-message sleep in the sender, or batch into a single SysEx.
- **Skipping unused NRPN params.** Some Mopho NRPN params (e.g., MIDI channel, knob behavior, push-it buttons) are settings, not sound design. The transcription should exclude these — flag the section header in `mopho.csv` so it's easy to audit later.
