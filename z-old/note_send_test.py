import mido

"""
c = mido.get_input_names()[0]
co = mido.open_input(c)

for m in co:
    print(m)
"""


c = mido.get_output_names()[0]
co = mido.open_output(c)


def note_send():
    m1 = mido.Message('note_on', channel=2, note=30, velocity =127)
    m3 = mido.Message('note_off', channel=2, note=30, velocity =0)
    co.send(m1)
    #co.send(m3)

    m2 = mido.Message('polytouch', channel=2, note=36, value=100)
    #co.send(m2)

note_send()

co.close()
