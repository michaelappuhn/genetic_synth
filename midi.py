import mido

#port = mido.open_output('Port Name')
port = mido.open_output(name='foo', virtual=True)
#print(port)
msg = mido.Message('note_on', note=60)
#print(msg)
port.send(msg)

print(mido.get_input_names())

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
print(bd_sharp["cc msb"])
