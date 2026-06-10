import copy
import time

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


def make_evaluate(midi_connect, midi_channel, voter, machines, canonical_params,
                  evolved_params, fixed_values):
    evolved_ccs = [p.cc for p in evolved_params]

    def evaluate(individual):
        machine_num = machines[individual[0]]
        cc_values = individual[1:]

        params = copy.deepcopy(canonical_params)
        cc_to_param = {p.cc: p for p in params}

        for cc, value in zip(evolved_ccs, cc_values):
            cc_to_param[cc].set_value(value)
        for cc, value in fixed_values.items():
            cc_to_param[cc].set_value(value)

        machine_param = Parameter(cc=MACHINE_CC, value=machine_num, value_min=0, value_max=127)
        MidiCCMessage(midi_connect, midi_channel, machine_param).send()

        sender = MidiMessageCollectionSender(midi_connect, midi_channel)
        sender.convert_parameters_to_messages(params)
        sender.send_collection_messages()

        note_on = mido.Message('note_on', note=TRIGGER_NOTE, velocity=TRIGGER_VELOCITY)
        MidiMessage(midi_connect, midi_channel, note_on).send()
        time.sleep(TRIGGER_HOLD_SECONDS)
        note_off = mido.Message('note_off', note=TRIGGER_NOTE, velocity=0)
        MidiMessage(midi_connect, midi_channel, note_off).send()

        vote = voter.get_vote()
        if not vote:
            vote = 1
        return (float(vote),)

    return evaluate
