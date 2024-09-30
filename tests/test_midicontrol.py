from unittest import TestCase
import mido
from synthesizer.midicontrol import MidiConnection, MidiMessage, MidiCCMessage, MidiMessageCollectionSender, AnalogRytmMidiMessageCollectionSender
from synthesizer.parameters import Parameter, ParameterCollection
from time import sleep
from random import randint


conn = MidiConnection('Elektron Analog Rytm MKII')

class TestMidiConnection(TestCase):

    def setUp(self):
        pass

    def test_connection(self):
        self.assertTrue(conn.check_is_connected())

    """
    def test_connection_virtual(self):
        self.fake_in = mido.open_input(name='foo', virtual=True)
        print("OUTPORTS:", mido.get_output_names())
        self.conn_virtual_good = MidiConnection('foo')
        #self.assertTrue(self.conn_virtual_good.is_connected)
    """

    def test_connection_failure(self):
        self.conn_bad = MidiConnection('foobar')
        self.assertFalse(self.conn_bad.check_is_connected())
 
class TestMidiMessage(TestCase):
    def setUp(self):
        #self.conn = MidiConnection('Elektron Analog Rytm MKII')
        self.msg_on = mido.Message('note_on', channel=1, note=35, velocity = 127, time=0)
        #self.msg_off = mido.Message('note_off', note=35, velocity = 127, time=0)

    def test_message_send(self):
        msg = MidiMessage(conn, 2, self.msg_on)
        msg.send()
        sleep(.2)
        msg2 = MidiMessage(conn, 3, self.msg_on)
        msg2.send()

class TestMidiCCMessage(TestCase):
    def setUp(self):
        self.p = Parameter(17, 30, 12, 102)
        self.ccmsg = MidiCCMessage(conn, 3, self.p)

    def test_cc_construct(self):
        self.assertEqual(self.ccmsg.cc, 17)
        self.assertEqual(self.ccmsg.msg.control, 17)
    
    def test_cc_send(self):
        self.ccmsg.send()


class TestMidiMessageCollectionSender(TestCase):
    def setUp(self):
        self.pc = ParameterCollection()
        self.channel = 2

        for i in range(17,21):
            p = Parameter(i,40+i)
            self.pc.add_parameter(p)


        self.mcs = MidiMessageCollectionSender(conn, self.channel)

    def test_convert_params_messages(self):
        self.mcs.convert_parameters_to_messages(self.pc)
        self.assertEqual(self.mcs.messages[0].cc, 17)
        self.assertEqual(self.mcs.messages[2].cc, 19)
        
    def test_set_new_channel(self):
        self.mcs.set_channel(3)
        self.assertEqual(self.mcs.channel, 3)

    def test_send_collection_messages(self):
        self.mcs.send_collection_messages()
