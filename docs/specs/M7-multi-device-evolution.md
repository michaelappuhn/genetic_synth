# M7 — Multi-device evolution

## Context

By M6 the GA runs on either a Rytm or a Mopho, one at a time. The next interesting question is whether the *combination* of two devices can be evolved — a Mopho bass layered with a Rytm kick, both driven by the same trig, with the user voting on the combined sound. Musically, this is where the tool starts to feel like a *composition* instrument rather than a sound-design instrument: you're not finding "a kick" or "a bass," you're finding a *texture*.

This is a stretch milestone. It's deferred from the main path because (a) audition gets harder — two devices have to fire together or in close succession, (b) the fitness signal gets coarser — a single 1–8 vote on a combination is less surgical than on a single voice, and (c) it's only useful if the user actually wants this musically. M5's `Device` abstraction is deliberately shaped to make M7 a composition, not a rewrite.

## Scope

**In:**
- `MultiDevice` that wraps N concrete devices and presents itself as a single `Device` to the GA
- Two audition modes: **layered** (both devices fire simultaneously) and **sequential** (device A audition, brief gap, device B audition, single vote covers both)
- CLI: `--devices rytm,mopho` or similar, with per-device channel/audition overrides
- Logging that splits the combined genome back into per-device segments at write time, so saved patches are usable on each device independently

**Out:**
- More than two devices simultaneously (the design supports N, but the spec only validates 2)
- Independent fitness for each device (you'd need per-device voters; possible but a different problem)
- Tempo / clock sync between devices — the user does this externally with hardware clock as today

## Approach

### Genome shape

A `MultiDevice` parameter list is the concatenation of its members' lists, in declaration order:

```
genome = [rytm_machine_idx, rytm_cc_0, ..., rytm_cc_N, mopho_cc_0, ..., mopho_nrpn_M]
```

Bounds vector is the concatenation. The bounded mutator from M1 already handles heterogeneous per-gene ranges, so it just works. Crossover across the device boundary is *especially* interesting — a Rytm kick's envelope crossed with a Mopho's filter sweep can produce surprising hybrid character.

### Layered audition

Both devices' parameters are sent in parallel (Python threads, or sequential sends fast enough that perceptual simultaneity is preserved — at USB MIDI speeds, < 20 ms is fine). Then both audition strategies fire at the same wall-clock instant:

```
def audition(self, conn_a, conn_b, channel_a, channel_b):
    Thread(target=lambda: self.device_a.audition.audition(conn_a, channel_a)).start()
    Thread(target=lambda: self.device_b.audition.audition(conn_b, channel_b)).start()
    # wait for both to complete
```

Vote follows the combined audition.

### Sequential audition

Useful when the two timbres should be heard distinctly — e.g., a Mopho bass that *follows* a Rytm kick rather than layering with it.

```
device_a.audition.audition(conn_a, channel_a)
sleep(gap_ms / 1000)
device_b.audition.audition(conn_b, channel_b)
```

Single vote covers the pair. Gap is configurable, default 200 ms.

### Connections

Each device needs its own `MidiConnection`. The driver opens both at startup and binds them to the `MultiDevice` instance. Failure of either device's port fails the whole run early — no partial mode.

### Saving champions across devices

M3's patch format gains a `devices: [...]` array when the source is a `MultiDevice`:

```json
{
  "version": 2,
  "name": "kraken-stack",
  "devices": [
    {"name": "rytm", "channel": 2, "machine_number": 31, "parameters": [...]},
    {"name": "mopho", "channel": 1, "parameters": [...]}
  ],
  "fitness": 7.0,
  "audition_mode": "layered"
}
```

A saved multi-device patch can also be played back on a single device — the play command picks the relevant segment. This means M7 patches are forward-compatible with single-device workflows.

### Why this works with M5 unchanged

`MultiDevice` implements the same interface as a single `Device` — it has `parameters`, `audition.audition(...)`, optional `categorical_selection`, etc. The GA driver doesn't know or care that it's a composite. The only place the abstraction leaks is the driver's MIDI connection setup (now N connections instead of 1) and the patch save format (now an array). Both are at the system boundary, not in the GA core.

### Pairing with M4

A single 1–8 vote on a combined audition is a noisy fitness signal. M4's **mini-tournament** voting mode is a strong complement: "did the combination A sound better than combination B?" is much easier to answer than "rate this combination 1–8." Recommend M7 runs use `--vote-mode tournament` by default.

## Files

New:
- `synthesizer/devices/multi.py` — `MultiDevice` composite + audition modes
- `tests/test_multi_device.py` — unit tests for genome concatenation, audition mode dispatch, patch save/load round-trip

Touched:
- `genetic/main.py` — `--devices a,b`, `--audition-mode {layered, sequential}`, per-device channel overrides
- `genetic/patches.py` (from M3) — v2 patch schema with `devices` array; v1 patches still load
- `genetic/audition.py` — layered/sequential strategies live here for symmetry

## Verification

### Without hardware

```bash
# Genome concatenation is correct
python -c "
from synthesizer.devices.registry import load_device
from synthesizer.devices.multi import MultiDevice
multi = MultiDevice([load_device('rytm'), load_device('mopho')])
print(len(multi.parameters))
# - Equals len(rytm.parameters) + len(mopho.parameters)
"

# v2 patch round-trip
python -m unittest tests.test_multi_device.TestPatchSchema
```

### With both devices connected

```bash
# Layered audition, tournament vote
python -m genetic.main run \
  --devices rytm,mopho \
  --audition-mode layered \
  --vote-mode tournament \
  --generations 5

# Sequential audition (e.g. kick then bass)
python -m genetic.main run \
  --devices rytm,mopho \
  --audition-mode sequential \
  --gap-ms 150 \
  --generations 5

# Saved patch plays back on either device alone
python -m genetic.main save-best runs/2026-*/ --name combo-1
python -m genetic.main play combo-1 --device rytm-only
python -m genetic.main play combo-1 --device mopho-only
```

Success criterion: a layered run produces combined textures that neither device produces alone, and a saved champion can be reproduced (Rytm + Mopho together) months later by name.

## Open questions deferred to implementation

- **Per-device tempo and trig timing.** Layered audition assumes both devices' audition starts at the same instant. If a Rytm `OneTrigAudition` returns in 100 ms but a Mopho `SustainedNoteAudition` runs 1500 ms, the combined audition's total length is 1500 ms — fine, but worth confirming the GA driver waits for both.
- **More than two devices.** The `MultiDevice` design accepts N, but N > 2 makes per-channel CLI args verbose and audition timing more fragile. Defer until there's a concrete reason.
- **Independent per-device evolution rates.** Could be interesting to mutate the Rytm gene block at a different rate than the Mopho block (rationale: Rytm machine switches are bigger jumps than NRPN tweaks). Deferred — start with uniform mutation, revisit if results converge on one device too aggressively.
