"""Per-pad evolution configuration.

For each pad, declare:
- machine_filter: set of allowed machine numbers (intersected with
  AnalogRytmMachineSelector.avail_machines_by_channel[pad])
- fixed_ccs: CCs NOT in the genome — a dict {cc: value | DEFAULT}. DEFAULT
  keeps the canonical CSV value for that CC.
- cc_value_caps: per-CC (lo, hi) override on the bounds for evolved CCs.

Pads not in PAD_CONFIG evolve everything in the canonical collection with no
machine filter (the M1 default behavior).
"""

# kits_10.md Channel 1 BD machines, after the -1 offset that
# AnalogRytmMachineSelector.avail_machines_by_channel uses.
#   bd classic (1)  -> 0
#   bd fm      (14) -> 13
#   bd plastic (22) -> 21
#   bd silky   (23) -> 22
#   bd sharp   (27) -> 26
#   bd acoustic(31) -> 30
BD_MACHINES = {0, 13, 21, 22, 26, 30}

# Sentinel for "pin this CC to whatever the canonical CSV value is".
DEFAULT = 'default'

_FILTER_CCS = {70, 71, 72, 73, 74, 75, 76, 77}
_AMP_ENV_CCS = {78, 79, 80}
_AMP_OVERDRIVE_CC = 81
_AMP_DELAY_SEND_CC = 82
_AMP_REVERB_SEND_CC = 83
_AMP_PAN_CC = 10
_AMP_VOLUME_CC = 7
_LFO_DEPTH_CC = 109

# On every BD machine, the "Synth parameter 1" slot is the SRC Level — verified
# across BD plastic/sharp/hard/classic/FM/silky/acoustic in the full Rytm MKII.csv.
_SRC_LEVEL_CC = 16

# Filter env depth is a bipolar -64..+63 knob; MIDI 64 = noon (no modulation).
_FILTER_ENV_DEPTH_CC = 77
_FILTER_ENV_DEPTH_NOON = 64

# Amp pan is also bipolar (L..C..R); MIDI 64 = center.
_AMP_PAN_CENTER = 64

_FILTER_ATTACK_CC = 70
_FILTER_RESONANCE_CC = 75
_FILTER_MODE_CC = 76
_FILTER_MODE_LP2 = 0   # Rytm filter modes: 0=LP2, 1=LP1, 2=BP, 3=HP1, 4=HP2, 5=BS, 6=PK
_AMP_ATTACK_CC = 78


def _bd_kick_fixed():
    fixed = {cc: DEFAULT for cc in (
        _FILTER_CCS
        | _AMP_ENV_CCS
        | {_AMP_OVERDRIVE_CC, _AMP_PAN_CC, _AMP_VOLUME_CC}
    )}
    fixed[_AMP_DELAY_SEND_CC] = 0
    fixed[_AMP_REVERB_SEND_CC] = 0
    # Kick-specific shaping:
    fixed[_SRC_LEVEL_CC] = 127             # Source level at 100% (was evolving)
    fixed[_FILTER_ATTACK_CC] = 0           # Filter attack instant (was maxed)
    fixed[_AMP_ATTACK_CC] = 0              # Amp attack instant (was maxed)
    fixed[_FILTER_ENV_DEPTH_CC] = _FILTER_ENV_DEPTH_NOON  # Filter env contributes nothing
    fixed[_AMP_PAN_CC] = _AMP_PAN_CENTER   # Center pan (was hard-right at 127)
    fixed[_FILTER_RESONANCE_CC] = 0        # Filter resonance off
    fixed[_FILTER_MODE_CC] = _FILTER_MODE_LP2  # Lowpass 2-pole (was PK at canonical max)
    fixed[_AMP_OVERDRIVE_CC] = 0           # No distortion
    return fixed


# Bipolar-knob range overrides. Per the user manual:
#   - LFO Depth (CC 109): "A dead center setting, 0, equals no modulation"
#     — MIDI 64 is musical zero; values < 64 invert the modulation.
#   - BD Tune (CC 17): "chromatic semitones", bipolar around MIDI 64.
#
# Both knobs need ranges CENTERED on 64, not capped at the extremes, or the
# GA samples only one polarity (e.g. always-inverted LFO) or covers a musically
# absurd pitch range (~10 octaves total for Tune across the raw MIDI range).
_BD_TUNE_CC = 17
_BD_TUNE_RANGE = (58, 70)   # ±6 semitones around canonical pitch
_LFO_DEPTH_RANGE = (54, 74) # ±10 around center for subtle bipolar modulation


PAD_CONFIG = {
    0: {
        'machine_filter': BD_MACHINES,
        'fixed_ccs': _bd_kick_fixed(),
        'cc_value_caps': {
            _LFO_DEPTH_CC: _LFO_DEPTH_RANGE,
            _BD_TUNE_CC: _BD_TUNE_RANGE,
        },
    },
}


def get_pad_config(pad):
    """Return the config for the pad, or an empty default that evolves everything."""
    return PAD_CONFIG.get(pad, {})
