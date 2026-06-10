import mido
from random import randint

from synthesizer.parameters import ParameterCollection, Parameter, AnalogRytmParameterCSVReader

#inport = get_lpd8_port()

class MidiConnection():
    def __init__(self, outport_name):
        # todo generalize
        self.outport_name = outport_name
        self.connect()
        #outport = mido.open_output('Elektron Analog Rytm MKII')
        pass

    def give_instructions():
        pass

    def connect(self):
        ins = mido.get_output_names()
        if (self.outport_name in ins):
            port = mido.open_output(self.outport_name)
            print(f'Outport "{self.outport_name}" is connected.')
            self.is_connected = True
            self.port = port
        else:
            self.is_connected = False
            self.message_failure()


    def message_failure(self):
        print(f'Outport "{self.outport_name}" not connected.')

    def check_is_connected(self):
        if (self.is_connected != False):
            return True
        else: return False


    def __str__(self):
        return self.outport_name

class MidiMessage():
    def __init__(self, midi_connect:MidiConnection, channel, msg:mido.Message = None):
        self.midi_connect = midi_connect
        self.channel = channel
        if msg is None:
            msg = mido.Message('note_on', note=60)
        self.msg = msg.copy(channel=channel)

    def send(self):
        self.midi_connect.port.send(self.msg)
        #print(self.msg)


class MidiCCMessage(MidiMessage):
    def __init__(self, midi_connect: MidiConnection, channel, param: Parameter):
        self.midi_connect = midi_connect
        self.channel = channel
        self.param = param
        self.construct_cc()

    def construct_cc(self):
        self.cc = self.param.cc
        self.value = self.param.value
        time = 0
        self.msg = mido.Message(type='control_change', channel=self.channel, control=self.cc, value=self.value, time=time)

    def __str__(self):
        return f'channel: {self.channel}, param: {self.param}'

    def __repr__(self):
        return f'MidiCCMessage: channel: {self.channel}, param: {self.param}'


class MidiMessageCollectionSender():
    def __init__(self, midi_connect:MidiConnection, channel:int):
        self.midi_connect = midi_connect
        self.channel = channel
        self.messages = []

    def convert_parameters_to_messages(self, collection: ParameterCollection):
        self.messages = []
        for param in collection:
            message = MidiCCMessage(self.midi_connect, self.channel, param)
            self.messages.append(message)

        
    def send_collection_messages(self):
        for message in self.messages:
            message.send()

    def set_channel(self, channel):
        self.channel = channel


class AnalogRytmMidiMessageCollectionSender(MidiMessageCollectionSender):

    def __init__(self, midi_connect:MidiConnection, channel:int, need_send_machine=False, current_machine:int = 200):
        super().__init__(midi_connect, channel)

        #machine selection is isolated from other CCs because complicated
        self.determine_if_machine_change_needed(need_send_machine, current_machine)

        ar_parameter_collection = AnalogRytmParameterCSVReader().get_random_parameter_collection()
        self.convert_parameters_to_messages(ar_parameter_collection)

    def determine_if_machine_change_needed(self, need_send_machine, current_machine):
        if (current_machine < 200) and (need_send_machine == True):
            self.machine = current_machine
        else:
            self.machine_selector = AnalogRytmMachineSelector(self.channel)
            self.select_random_machine()

        
    def select_random_machine(self):
        # set the default machine as 200, which is way out of bounds
        machine_num = self.machine_selector.get_random_machine()
        print(f'MACHINE NUM: {machine_num}')
        self.send_machine_selection(machine_num)

    def send_machine_selection(self, machine_num):
        machine_cc = 15
        selection_param = Parameter(machine_cc, machine_num, 0, 127)
        selection_message = MidiCCMessage(self.midi_connect, self.channel, selection_param)
        selection_message.send()

class AnalogRytmMachineSelector():
    # Derived from kits_10.md (1-based human labels) with a -1 offset to
    # 0-based MIDI machine values. kits_10's "0 - bd hard" entries on
    # Channels 3-4 fall to -1 under that offset and are dropped, matching
    # the convention used by the previous narrower table.
    avail_machines_by_channel = [
            # Channel 0 (kits_10 Channel 1): bd/sd/ut/sy palette
            [0, 1, 2, 13, 14, 15, 16, 21, 22, 23, 26, 27, 28, 29, 30, 31, 32],
            # Channel 1 (kits_10 Channel 2): same as Channel 0
            [0, 1, 2, 13, 14, 15, 16, 21, 22, 23, 26, 27, 28, 29, 30, 31, 32],
            # Channel 2 (kits_10 Channel 3): + rs/cp
            [0, 1, 2, 3, 4, 5, 13, 14, 15, 16, 21, 22, 23, 26, 27, 28, 29, 30, 31, 32],
            # Channel 3 (kits_10 Channel 4): same as Channel 2
            [0, 1, 2, 3, 4, 5, 13, 14, 15, 16, 21, 22, 23, 26, 27, 28, 29, 30, 31, 32],
            # Channel 4 (kits_10 Channel 5): bt + ut + disable
            [7, 15, 16, 26],
            # Channels 5-7 (kits_10 Channels 6-8): xt + ut + disable
            [8, 15, 16, 26],
            [8, 15, 16, 26],
            [8, 15, 16, 26],
            # Channels 8-9 (kits_10 Channels 9-10): hi-hats palette
            [9, 10, 15, 16, 17, 18, 24, 26, 32],
            [9, 10, 15, 16, 17, 18, 24, 26, 32],
            # Channels 10-11 (kits_10 Channels 11-12): cymbal/cowbell palette
            [11, 12, 15, 16, 19, 20, 25, 26],
            [11, 12, 15, 16, 19, 20, 25, 26],
        ]

    def __init__(self, channel:int=0, current_machine:int = 200):
        # set the default machine as 200, which is way out of bounds
        self.channel = channel
        self.current_machine = current_machine

    def get_num_machines(self):
        # return the number of machines available on the selected channel
        return len(self.avail_machines_by_channel[self.channel])

    def get_machine(self, machine_number):
        return self.avail_machines_by_channel[self.channel][machine_number]


    def get_random_machine(self):
        machine_num =  randint(0, self.get_num_machines()-1)
        return self.get_machine(machine_num)



def main():

    """
    chan:int = int(input("Channel? "))
    #mach:int = int(input("Machine? "))
    
    machine = AnalogRytmMachineSelector(chan)
    print('avail', machine.get_num_machines())
    print(machine.get_random_machine())

    #print("outputs:", mido.get_output_names())

    for i in range(0,3):
        vote_out = vote(inport)
        print(vote_out)
        send_cc(1,4,vote_out,0)


    bd_selection = randint(1, 6)
    print("---")
    print(synths[bd_selection])
    for synth_param in get_cc_lookup(synths[i]):
        send_val = generate_values(0,127)
        print(synth_param['param'], "CC:", synth_param['cc_msb'], send_val)
        send_cc(outport, 12, synth_param['cc_msb'], send_val, 0)

    
    for i in range(0, 6):
        print("---")
        print(synths[i])
        for synth_param in get_cc_lookup(synths[i]):
            print(synth_param['param'], "CC:", synth_param['cc_msb'])
    """


if __name__ == "__main__":
    main()
