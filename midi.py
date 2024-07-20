import mido
from midi_play import vote, get_lpd8_port
import pandas as pd


# data pulled from https://github.com/pencilresearch/midi/blob/main/Elektron/Rytm%20MKII.csv 

#port = mido.open_output('Port Name')
#print(port)
outport = mido.open_output(name='foo', virtual=True)
rdf = pd.read_csv("Rytm MKII.csv")


sections = [
"Trig",
"Kit",
"Sample",
"Filter",
"Amp",
"LFO"
]


synths = [
"Synth, BD plastic",
"Synth, BD sharp",
"Synth, BD hard",
"Synth, BD classic",
"Synth, BD FM",
"Synth, BD silky",
"Synth, SD natural",
"Synth, SD hard",
"Synth, SD classic",
"Synth, SD FM",
"Synth, RS hard",
"Synth, RS classic",
"Synth, CP classic",
"Synth, Dual VCO",
"Synth, BT classic",
"Synth, LT, MT, HT classic",
"Synth, CH classic",
"Synth, CH metallic",
"Synth, OH classic",
"Synth, OH metallic",
"Synth, HH basic",
"Synth, CY metallic",
"Synth, CY classic",
"Synth, CY ride",
"Synth, CB classic and metallic",
"Synth, noise",
"Synth, impulse"
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
                'cc_min': j['cc_max_value']
            }
        )
    return cc_vals


def send_cc(channel=1, cc=1, value=122, time=0):
    #msg = mido.Message('note_on', note=60)
    #mido.Message('control_change', note=60)
    #port.send(msg)
    msg = mido.Message(type='control_change', channel=channel, control=cc, value=value, time=time)
    print(msg)

def main():
    inport = get_lpd8_port()

    for i in range(0,3):
        vote_out = vote(inport)
        print(vote_out)
        send_cc(1,4,vote_out,0)

    for i in range(0, len(sections)):
        print(get_cc_lookup(sections[i]))


    for i in range(0, 6):
        print("---")
        print(synths[i])
        print(get_cc_lookup(synths[i]))

    return True

main()
