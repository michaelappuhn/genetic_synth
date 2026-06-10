# M5 — Device abstraction

## Context

M1–M4 deliver a working GA loop, but every piece of the pipeline — parameter modeling, MIDI sending, categorical selection, audition — is Rytm-shaped. The user owns other devices (starting with a DSI Mopho) and wants to evolve sounds on those too. The Mopho exposes most of its interesting parameters via **NRPN**, not CC, and is a monosynth that wants a sustained note for audition rather than a percussion trig — both of which expose where the current code is implicitly Rytm-specific.

This milestone is a pure refactor: behavior of M1–M4 is preserved, with the Rytm becoming the first concrete `Device`. The abstraction is designed knowing the next device is a Mopho — i.e., it must accommodate CC + NRPN, no categorical primary selection, and a sustained-note audition. That's the second concrete data point that keeps the interface honest. M6 then validates the abstraction by actually porting the Mopho.

## Scope

**In:**
- Address-type-polymorphic `Parameter` (`CCParameter`, `NRPNParameter`; `SysExParameter` reserved)
- `Device` descriptor (data + a small Python file per device for quirks)
- `AuditionStrategy` interface with `OneTrigAudition` and `SustainedNoteAudition`
- Device registry (`--device <name>` CLI flag, resolves via name lookup)
- Rytm ported into the new structure; all existing behavior preserved
- Unit tests for NRPN message construction (no hardware needed)

**Out:**
- Adding any new device (M6)
- Multi-device runs (M7)
- SysEx-based parameter writes — the class exists as a stub for future work, no live implementation
- Pitch bend, aftertouch, program change as parameter addressing modes (low priority; can be added later as additional `Parameter` subclasses without disturbing the design)

## Approach

### Parameter address polymorphism

`synthesizer/parameters.py` currently has a single `Parameter` class hardcoded to CC semantics. Restructure:

```
Parameter (abstract)
├── CCParameter         # current class, renamed
├── NRPNParameter       # new
└── SysExParameter      # stub class with NotImplementedError on to_messages()
```

Each implements `to_messages(channel: int) -> list[mido.Message]`. For `CCParameter` that's a single-element list; for `NRPNParameter` it's four messages:

```
CC 99 (NRPN MSB)  = param_msb
CC 98 (NRPN LSB)  = param_lsb
CC 6  (data MSB)  = value >> 7
CC 38 (data LSB)  = value & 0x7F
```

`NRPNParameter` supports 14-bit values (0–16383) and 14-bit parameter addresses (0–16383). Bounds clamping in `_check_value_bounds()` still applies; the range constants change per subclass.

### Sender becomes address-agnostic

`MidiMessageCollectionSender.convert_parameters_to_messages()` currently constructs `MidiCCMessage` objects directly. Replace with `param.to_messages(self.channel)` and flatten. `MidiCCMessage` stays as a thin wrapper around a `mido.Message` for the existing test surface but no longer hard-codes CC construction.

Result: adding a new addressing mode is one new `Parameter` subclass with one method. Nothing else in the MIDI pipeline changes.

### Device descriptor

A `Device` carries everything the GA needs to know about a target:

```
Device(
    name="rytm",
    port_name="Elektron Analog Rytm MKII",
    parameters=[Parameter, ...],
    audition=OneTrigAudition(note=60, hold_ms=100),
    categorical_selection=AnalogRytmMachineSelector(),   # Optional; None for Mopho
    program_change=None,                                  # Optional; for preset slot reset
)
```

Static data lives in `synthesizer/devices/<name>.json` (parameter list, port name, audition defaults). Quirks live in `synthesizer/devices/<name>.py` (Rytm's machine selector goes here). A small `registry.py` maps names → loader functions.

### Audition strategy

```
AuditionStrategy (interface)
├── OneTrigAudition         # send note_on + note_off ~immediately after; existing Rytm path
└── SustainedNoteAudition   # note_on, sleep duration_ms, note_off; for monosynths
```

The audition takes a `MidiConnection` and a channel and is invoked from the GA evaluator after parameters have been sent. Devices declare their default strategy; users can override per-run with a CLI flag.

### Rytm port

- `AnalogRytmMachineSelector` moves to `synthesizer/devices/rytm.py` unchanged.
- The `avail_machines_by_channel` table stays in code (not JSON) — it's logic, not data.
- A one-shot script (`scripts/build_rytm_json.py` or similar) reads `rytm-limited.csv` and emits `synthesizer/devices/rytm.json`. After M5, the CSV is no longer on the runtime path; it's a build artifact.
- `AnalogRytmMidiMessageCollectionSender`'s embedded randomization (`synthesizer/midicontrol.py:108–124`) is already a documented anti-pattern in M1 — M5 finally removes it. The GA owns randomization; the device just sends what it's told.

### GA driver becomes device-agnostic

`genetic/genome.py` builds bounds from `device.parameters`; for each `Parameter` the bounds come from `(value_min, value_max)` regardless of addressing mode. `NRPNParameter` contributes 0–16383 ranges; `CCParameter` contributes 0–127. The mutator already operates per-gene with bounds drawn from a list, so no special-casing is needed.

`genetic/evaluate.py` calls `device.audition.audition(midi_connection, channel)` after sending parameters. Categorical selection (machine on Rytm) becomes an optional pre-send step that the device descriptor owns.

CLI gains `--device <name>` (default: `rytm` for back-compat with M1–M4).

### Naming

Keep `Parameter` as the abstract base name — code reading `Parameter` keeps reading naturally. The concrete classes get the address-mode suffix.

## Files

New:
- `synthesizer/devices/__init__.py`
- `synthesizer/devices/registry.py` — `load_device(name) -> Device`
- `synthesizer/devices/rytm.py` — Rytm descriptor + `AnalogRytmMachineSelector`
- `synthesizer/devices/rytm.json` — parameter list (built from `rytm-limited.csv`)
- `genetic/audition.py` — `AuditionStrategy`, `OneTrigAudition`, `SustainedNoteAudition`
- `scripts/build_device_json.py` — one-shot CSV → JSON converter
- `tests/test_parameter_types.py` — unit tests for `CCParameter`, `NRPNParameter` message construction

Touched:
- `synthesizer/parameters.py` — `Parameter` → abstract; `CCParameter`, `NRPNParameter`, `SysExParameter` siblings
- `synthesizer/midicontrol.py` — sender uses `param.to_messages()`; Rytm-specific classes removed (moved to `devices/rytm.py`)
- `genetic/genome.py`, `genetic/evaluate.py`, `genetic/main.py` — accept a `Device`, no hardcoded Rytm
- `tests/test_parameters.py` — update for renamed class; verify backwards-compatible factory if used elsewhere
- `tests/test_midicontrol.py` — update Rytm-specific tests to import from `synthesizer.devices.rytm`

Removed from runtime path (but kept as build inputs):
- `synthesizer/rytm-limited.csv` — used only by `scripts/build_device_json.py`

## Verification

```bash
# Unit tests pass without hardware
python -m unittest tests.test_parameters tests.test_parameter_types

# NRPN message construction is correct
python -c "
from synthesizer.parameters import NRPNParameter
p = NRPNParameter(param_msb=1, param_lsb=20, value=8192, value_min=0, value_max=16383, name='LFO 1 rate')
msgs = p.to_messages(channel=1)
assert len(msgs) == 4
assert msgs[0].control == 99 and msgs[0].value == 1       # NRPN MSB
assert msgs[1].control == 98 and msgs[1].value == 20      # NRPN LSB
assert msgs[2].control == 6  and msgs[2].value == 64      # data MSB (8192 >> 7)
assert msgs[3].control == 38 and msgs[3].value == 0       # data LSB (8192 & 0x7F)
print('NRPN ok')
"

# Existing M1 behavior preserved on Rytm with new flag
python -m genetic.main run --device rytm --channel 2 --generations 3
# - Indistinguishable from pre-M5 M1–M4 runs

# Full suite with hardware
./unittests.sh
```

Success criterion: a maintainer who only knows M5 can read `synthesizer/devices/rytm.py` + `rytm.json` and accurately predict what M6 (`mopho.py` + `mopho.json`) will look like, without needing the M6 spec.

## Open question deferred to implementation

Whether `AnalogRytmMidiMessageCollectionSender` is fully removed or kept as a Rytm-specific convenience wrapper around the generic sender. If kept, it lives in `devices/rytm.py`. Likely: remove — the generic sender + Rytm descriptor cover its use cases.
