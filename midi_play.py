import mido

# LPD8 input play
#port = mido.open_input(mido.get_input_names()[0])
port = mido.open_input('LPD8')

for msg in port:
    #print(msg)
    #print(dir(msg))
    #print("bytes", msg.bytes())
    #print("channel", msg.channel)

    # Turning the LPD8 into a voting system?
    if (msg.type == 'note_on'):
        #print("note:", msg.note)
        if msg.note == 36:
            vote=1
        if msg.note == 37:
            vote=2
        if msg.note == 38:
            vote=3
        if msg.note == 39:
            vote=4
        if msg.note == 40:
            vote=5
        if msg.note == 41:
            vote=6
        if msg.note == 42:
            vote=7
        if msg.note == 43:
            vote=8
        print (vote)

    if (msg.is_cc()):
        print(msg)
        print(msg.control, msg.value)
        #print("")
        #print(msg.type)


