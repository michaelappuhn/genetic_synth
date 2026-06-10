import copy
import time
from datetime import datetime

import mido

from synthesizer.parameters import Parameter
from synthesizer.midicontrol import (
    MidiMessage,
    MidiCCMessage,
    MidiMessageCollectionSender,
)


MACHINE_CC = 15
TRIGGER_NOTE = 36
TRIGGER_VELOCITY = 100
TRIGGER_HOLD_SECONDS = 0.1


def build_params_for_individual(individual, machines, canonical_params,
                                evolved_ccs, fixed_values):
    """Decode a genome into (machine_num, params): a list of Parameter objects
    with evolved + fixed values applied, ready to send."""
    machine_num = machines[individual[0]]
    cc_values = individual[1:]

    params = copy.deepcopy(canonical_params)
    cc_to_param = {p.cc: p for p in params}

    for cc, value in zip(evolved_ccs, cc_values):
        cc_to_param[cc].set_value(value)
    for cc, value in fixed_values.items():
        cc_to_param[cc].set_value(value)

    return machine_num, params


def send_individual(midi_connect, midi_channel, machine_num, params):
    """Send machine CC + all param CCs + a trig note. Used by evaluate() and
    by the replay-best callback so both paths produce identical sound."""
    machine_param = Parameter(cc=MACHINE_CC, value=machine_num,
                              value_min=0, value_max=127)
    MidiCCMessage(midi_connect, midi_channel, machine_param).send()

    sender = MidiMessageCollectionSender(midi_connect, midi_channel)
    sender.convert_parameters_to_messages(params)
    sender.send_collection_messages()

    note_on = mido.Message('note_on', note=TRIGGER_NOTE, velocity=TRIGGER_VELOCITY)
    MidiMessage(midi_connect, midi_channel, note_on).send()
    time.sleep(TRIGGER_HOLD_SECONDS)
    note_off = mido.Message('note_off', note=TRIGGER_NOTE, velocity=0)
    MidiMessage(midi_connect, midi_channel, note_off).send()


def make_evaluate(midi_connect, midi_channel, voter, machines, canonical_params,
                  evolved_params, fixed_values,
                  state=None, vote_logger=None, on_replay=None):
    """Build the GA fitness closure.

    state: optional {'gen': int, 'eval_idx': int} dict the driver mutates between
           generations. Used to stamp gen/eval_idx into vote log lines.
    vote_logger: optional callable(gen, eval_idx, machine, evolved_ccs, fixed_ccs,
                                   vote, timestamp_iso) -> None.
    on_replay: optional callable passed through to voter.get_vote() so the user
               can re-hear best-so-far without spending a vote.
    """
    evolved_ccs = [p.cc for p in evolved_params]

    def evaluate(individual):
        machine_num, params = build_params_for_individual(
            individual, machines, canonical_params, evolved_ccs, fixed_values,
        )
        send_individual(midi_connect, midi_channel, machine_num, params)

        vote = voter.get_vote(on_replay=on_replay)
        if not vote:
            vote = 1

        if vote_logger is not None and state is not None:
            evolved_ccs_log = {str(cc): int(v)
                               for cc, v in zip(evolved_ccs, individual[1:])}
            fixed_ccs_log = {str(cc): (int(v) if isinstance(v, int) else v)
                             for cc, v in fixed_values.items()}
            vote_logger(
                gen=state['gen'],
                eval_idx=state['eval_idx'],
                machine=machine_num,
                evolved_ccs=evolved_ccs_log,
                fixed_ccs=fixed_ccs_log,
                vote=vote,
                timestamp_iso=datetime.now().isoformat(timespec='seconds'),
            )
            state['eval_idx'] += 1

        return (float(vote),)

    return evaluate
