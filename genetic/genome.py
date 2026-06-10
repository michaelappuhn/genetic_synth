from random import random, randint

from synthesizer.midicontrol import AnalogRytmMachineSelector
from synthesizer.parameters import Parameter

from genetic.pad_config import DEFAULT


def apply_pad_config(canonical_params, machine_palette, pad_config):
    """Split canonical_params into (evolved, fixed) and filter machines per pad config.

    Returns:
        evolved_params: list of Parameter (with capped bounds applied) for the genome.
        fixed_values:   dict {cc: value} pinned every evaluation.
        machines:       subset of machine_palette honoring machine_filter.
    """
    machine_filter = pad_config.get('machine_filter')
    fixed_ccs = pad_config.get('fixed_ccs', {})
    cc_caps = pad_config.get('cc_value_caps', {})

    if machine_filter is not None:
        machines = [m for m in machine_palette if m in machine_filter]
    else:
        machines = list(machine_palette)

    evolved_params = []
    fixed_values = {}
    for p in canonical_params:
        if p.cc in fixed_ccs:
            v = fixed_ccs[p.cc]
            fixed_values[p.cc] = p.value if v == DEFAULT else v
            continue
        if p.cc in cc_caps:
            lo, hi = cc_caps[p.cc]
            p = Parameter(p.cc, p.value, lo, hi, p.name)
        evolved_params.append(p)

    return evolved_params, fixed_values, machines


def build_bounds(machines, evolved_params):
    bounds = [(0, len(machines) - 1)]
    bounds.extend((p.value_min, p.value_max) for p in evolved_params)
    return bounds


def make_individual(bounds, individual_cls):
    return individual_cls(randint(lo, hi) for lo, hi in bounds)


def bounded_mutate(individual, bounds, indpb):
    for i, (lo, hi) in enumerate(bounds):
        if random() < indpb:
            individual[i] = randint(lo, hi)
    return (individual,)
