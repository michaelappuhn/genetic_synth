import mido
from voter import vote, get_lpd8_port
import pandas as pd
from random import randint


# data pulled from https://github.com/pencilresearch/midi/blob/main/Elektron/Rytm%20MKII.csv 

outport = mido.open_output('Elektron Analog Rytm MKII')
#print(port)
#outport = mido.open_output(name='foo', virtual=True)
#rdf = pd.read_csv("Rytm MKII.csv")
rdf = pd.read_csv("rytm-limited.csv")


sections = [
    "Trig",
    #"Kit",
    #"Sample",
    "Filter",
    "Amp",
    "LFO"
]

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


synths = [
    "Synth, BD hard",
    "Synth, BD classic",
    "Synth, SD hard",
    "Synth, SD classic",
    "Synth, RS hard",
    "Synth, RS classic",
    "Synth, CP classic",
    "Synth, BT classic",
    "Synth, LT, MT, HT classic",
    "Synth, CH classic",
    "Synth, OH classic",
    "Synth, CY classic",
    "Synth, CB classic and metallic",
    "Synth, BD FM",
    "Synth, SD FM",
    "Synth, noise",
    "Synth, impulse",
    "Synth, CH metallic",
    "Synth, OH metallic",
    "Synth, CY metallic",
    "Synth, CB classic and metallic",
    "Synth, BD plastic",
    "Synth, BD silky",
    "Synth, SD natural",
    "Synth, HH basic",
    "Synth, CY ride",
    "Synth, BD sharp",
    "",
    "Synth, Dual VCO",
]

def get_cc_lookup(section):
    cc_vals = []
    section_selection = rdf[rdf['section']==section]
    for i, j in section_selection.iterrows():
        cc_vals.append(
            {
                'section': section,
                'param': j['parameter_name'],
                'cc_msb': j['cc_msb'],
                'cc_min': j['cc_min_value'],
                'cc_max': j['cc_max_value']
            }
        )
    return cc_vals

def generate_values(min_val, max_val):
    return randint(min_val, max_val)



def send_cc(port, channel=10, cc=1, value=122, time=0):
    #msg = mido.Message('note_on', note=60)
    #mido.Message('control_change', note=60)
    msg = mido.Message(type='control_change', channel=channel, control=cc, value=value, time=time)
    print(msg)
    outport.send(msg)

def main():
    inport = get_lpd8_port()

    """
    for i in range(0,3):
        vote_out = vote(inport)
        print(vote_out)
        send_cc(1,4,vote_out,0)
    """

    for i in range(0, len(sections)):
        print("---")
        print(sections[i])
        for j in get_cc_lookup(sections[i]):
            send_val = generate_values(0,127)
            print(j['param'], "CC:", j['cc_msb'], send_val)
            send_cc(outport, 1, j['cc_msb'], send_val,  0)



    bd_selection = randint(1, 6)
    print("---")
    print(synths[bd_selection])
    for synth_param in get_cc_lookup(synths[i]):
        send_val = generate_values(0,127)
        print(synth_param['param'], "CC:", synth_param['cc_msb'], send_val)
        send_cc(outport, 10, synth_param['cc_msb'], send_val, 0)

    print(mido.get_output_names())
    """
    for i in range(0, 6):
        print("---")
        print(synths[i])
        for synth_param in get_cc_lookup(synths[i]):
            print(synth_param['param'], "CC:", synth_param['cc_msb'])
    """

    return True

main()
