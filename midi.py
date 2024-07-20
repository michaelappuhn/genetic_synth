import mido
#from midi_play import lpd8_vote
import pandas as pd


# data pulled from https://github.com/pencilresearch/midi/blob/main/Elektron/Rytm%20MKII.csv 

#port = mido.open_output('Port Name')
port = mido.open_output(name='foo', virtual=True)
#print(port)
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
    print(cc_vals)


def send_cc(channel=9, cc=1, value=122, time=0):
    #msg = mido.Message('note_on', note=60)
    msg = mido.Message(type='control_change', channel=channel, control=cc, value=value, time=time)
    #mido.Message('control_change', note=60)
    print(msg)
    #port.send(msg)
    
def main():
    """
    for i in range(0,3):
        vote = lpd8_vote()
        #send_cc(3,4,vote,0)
        print(vote)
    """

    for i in range(0, len(sections)):
        get_cc_lookup(sections[i])
    print(synths[1])
    get_cc_lookup(synths[1])


main()
