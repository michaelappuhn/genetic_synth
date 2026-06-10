"""Patch I/O and DEAP individual conversion. Pure data; no MIDI, no DEAP setup."""

import json
from pathlib import Path
from typing import Tuple


PATCH_VERSION = 1


# Machine names for the BD/SD/RS/CP drum-track family (pads 0-3). Derived from
# kits_10.md (1-based human labels, -1 to 0-based MIDI). Other pad families
# (BT/XT/HH/CY) use different machines at the same MIDI numbers — patches saved
# from those pads use "machine_<N>" as machine_name. This is informational only;
# machine_number is the source of truth.
_DRUM_TRACK_MACHINES = {
    0: "bd classic",
    1: "sd hard",
    2: "sd classic",
    3: "rs hard",
    4: "rs classic",
    5: "cp classic",
    13: "bd fm",
    14: "sd fm",
    15: "ut noise",
    16: "ut impulse",
    21: "bd plastic",
    22: "bd silky",
    23: "sd natural",
    26: "bd sharp",
    27: "disable",
    28: "sy dual vco",
    29: "sy chip",
    30: "bd acoustic",
    31: "sd acoustic",
    32: "sy raw",
}


def machine_name_for(pad: int, machine_num: int) -> str:
    if pad in (0, 1, 2, 3) and machine_num in _DRUM_TRACK_MACHINES:
        return _DRUM_TRACK_MACHINES[machine_num]
    return f"machine_{machine_num}"


def save(path: Path, patch: dict) -> None:
    """Write patch JSON to path. Caller ensures parent dir exists."""
    path.write_text(json.dumps(patch, indent=2, sort_keys=False))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def from_individual(pad, midi_channel, machine_num, machine_name,
                    params, fitness, source):
    """Build a patch dict from a decoded individual's send-ready state.
    `params` is an iterable of objects with .cc, .value, .name."""
    return {
        "version": PATCH_VERSION,
        "name": None,   # caller sets this from the filename
        "pad": pad,
        "midi_channel": midi_channel,
        "machine_number": machine_num,
        "machine_name": machine_name,
        "parameters": [
            {"cc": p.cc, "value": int(p.value), "name": p.name}
            for p in params
        ],
        "fitness": float(fitness),
        "source": source,
    }


def to_individual(patch, machines, evolved_ccs, individual_cls) -> Tuple[list, dict]:
    """Decode a patch into a DEAP-style individual list.

    Returns (individual, dropped_ccs) where:
    - individual = [machine_idx, evolved_cc_val_0, evolved_cc_val_1, ...]
    - dropped_ccs = {cc: value, ...} for patch CCs not in evolved_ccs

    Raises ValueError if patch's machine_number isn't in machines, or if any
    evolved_cc is missing from the patch's parameter list.
    """
    machine_num = patch["machine_number"]
    try:
        machine_idx = machines.index(machine_num)
    except ValueError:
        raise ValueError(
            f"patch machine {machine_num} ({patch.get('machine_name', '?')}) "
            f"not available in current pad's filter"
        )

    cc_to_value = {p["cc"]: p["value"] for p in patch["parameters"]}

    missing = [cc for cc in evolved_ccs if cc not in cc_to_value]
    if missing:
        raise ValueError(
            f"patch missing evolved CCs {missing}"
        )

    cc_values = [cc_to_value[cc] for cc in evolved_ccs]
    dropped = {cc: v for cc, v in cc_to_value.items() if cc not in set(evolved_ccs)}

    return individual_cls([machine_idx] + cc_values), dropped
