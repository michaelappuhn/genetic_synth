import mido
from midi import send_cc
import time


outport = mido.open_output('Elektron Analog Rytm MKII')

channel = 11
channel_controls = "synth trig"
cc = 17
lfod = []
minv = 80
maxv = 90


"""
for i in range(minv,maxv):
    if (i < minv):
        i = minv 
    send_cc(outport, channel, cc, i)
    lfod_name = input("what " + channel_controls + " is this?")
    lfod.append(lfod_name)
    time.sleep(.2)
    lfod.append(str(i) + ': test')

for i in range(0, len(lfod)):
    print(str(i+minv-1) + " - " + str(lfod[i+minv-1]))
"""



for i in range(minv,maxv):
    if (i < minv):
        i = minv 
    send_cc(outport, channel, cc, i)
    print(i)
    time.sleep(.2)

