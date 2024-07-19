import mido

# LPD8 input play
#port = mido.open_input(mido.get_input_names()[0])
port = mido.open_input('LPD8')

for msg in port:
    #print(msg)
    #print(dir(msg))
    #print("bytes", msg.bytes())
    #print("channel", msg.channel)
    if (msg.type == 'note_on'):
        print("note:", msg.note)
    if (msg.is_cc()):
        print(msg)
        #print("")
        print(msg.type)


