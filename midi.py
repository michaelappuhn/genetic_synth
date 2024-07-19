import mido
from midi_play import lpd8_vote
import pandas as pd

# data pulled from https://github.com/pencilresearch/midi/blob/main/Elektron/Rytm%20MKII.csv 

#port = mido.open_output('Port Name')
port = mido.open_output(name='foo', virtual=True)
#print(port)

def get_cc_lookup(section):
    rdf = pd.read_csv("Rytm MKII.csv")
    cc_vals = {}
    for i, j in rdf[rdf['section']==section].iterrows():
        print('section', section)
        print('param', j['parameter_name'])
        print('cc_msb', j['cc_msb'])
        print('cc_min', j['cc_min_value'])
        print('cc_min', j['cc_max_value'])

def send_cc(channel=9, cc=1, value=122, time=0):
    #msg = mido.Message('note_on', note=60)
    msg = mido.Message(type='control_change', channel=channel, control=cc, value=value, time=time)
    #mido.Message('control_change', note=60)
    print(msg)
    #port.send(msg)
    

for i in range(0,3):
    vote = lpd8_vote()
    send_cc(3,4,vote,0)


sections = [
"Trig",
"Kit",
"Sample",
"Filter",
"Amp",
"LFO"
]

get_cc_lookup(sections[0])

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

print(synths[1])
get_cc_lookup(synths[1])


bd_sharp = {
    "parameters" : [
            "level", 
            'tune', 
            'decay', 
            'sweep depth', 
            "sweep time", 
            "hold time", 
            "tick level"
    ], 
    "cc msb" : [16, 17, 18, 19, 20, 21, 22, 23],
    "cc lsb" : [0, 0, 0, 0, 0, 0, 0, 0],
    "nprn msb" : [1, 1, 1, 1, 1, 1, 1, 1]
}

