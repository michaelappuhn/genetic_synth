import mido
from random import randint, seed
from time import time

from synthesizer.parameters import ParameterCollection, Parameter, AnalogRytmParameterCSVReader

seed(time())

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
        return outport.name

class MidiMessage():
    def __init__(self, midi_connect:MidiConnection, channel, msg:mido.Message = mido.Message('note_on', note=60)):
        self.midi_connect = midi_connect
        #self.msg = mido.Message('note_on', note=60)
        self.channel = channel
        msg.channel = channel
        self.msg = msg

    def send(self):
        self.midi_connect.port.send(self.msg)
        print(self.msg)


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
    def __init__(self, midi_connect:MidiConnection, channel):
        self.midi_connect = midi_connect
        self.channel = channel
        self.messages = []

    def convert_parameters_to_messages(self, collection: ParameterCollection):
        for param in collection:
            print(param)   
            message = MidiCCMessage(self.midi_connect, self.channel, param)
            self.messages.append(message)
            print(message)

        
    def send_collection_messages(self):
        pass

    def set_channel(self, channel):
        self.channel = channel


class AnalogRytmMidiMessageCollectionSender(MidiMessageCollectionSender):

    def __init__(self, channel, need_send_machine=False, current_machine:int = 200):
        super().__init__(channel)
        print("Channel: ", avail_machines_by_channel[0,1])
        if (current_machine < 200) and (need_send_machine == True):
            self.machine = current_machine
        else:
            self.select_random_machine()

        self.convert_parameters_to_messages(AnalogRytmParameterCSVReader.get_random_parameter_collection())

    def select_random_machine(self):
        # set the default machine as 200, which is way out of bounds
            ms = AnalogRytmMachineSelector(self.channel)
            ms.get_random_machine()

    def send_machine_selection(self):
        print("send machine selection message to analog")
        pass

class AnalogRytmMachineSelector():
    avail_machines_by_channel = [
            [0, 13, 21, 22, 26],
            [0, 1, 2, 13, 14, 15, 16, 21, 22, 26, 28],
            [0, 1, 2, 3, 4, 5, 13, 14, 15, 16, 21, 22, 26, 28],
            [0, 1, 2, 3, 4, 5, 13, 14, 15, 16, 21, 22, 26, 28],
            [7, 15, 16],
            [8, 15, 16],
            [8, 15, 16],
            [8, 15, 16],
            [9, 10, 15, 16, 17, 18, 24],
            [9, 10, 15, 16, 17, 18, 24],
            [11, 12, 16, 17, 19, 20, 25],
            [11, 12, 16, 17, 19, 20, 25],
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


main()
