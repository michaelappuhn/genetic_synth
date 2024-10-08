import mido

def main():
    x = LPD8VoteController()
    x.connect()
    print(x.check_is_connected())
    print(x.get_vote())

    """
    vote_result = vote(get_lpd8_port())
    print(vote_result)
    """

class VotingSystem():
    def choose_controller(self):
        self.controller = LPD8Controller()

    def initialize_voting(self):
        self.controller.get_vote()

    def vote(self):
        pass


class VoteController():
    def give_instructions(self):
        pass

    def get_vote(self):
        pass


class LPD8VoteController(VoteController):
    is_connected = False

    def give_instructions():
        pass

    def connect(self):
        ins = mido.get_input_names()
        if ('LPD8' in ins):
            print("LPD8 connected")
            port = mido.open_input('LPD8')
            self.is_connected = True
            self.port = port
        else:
            self.message_failure()

    def message_failure(self):
        print("LPD8 port not connected.") 
        print("Using keyboard instead of external controller.") 

    def check_is_connected(self):
        if (self.is_connected != False):
            return True
        else: return False

    def get_vote(self):
        for msg in self.port:
            #print(msg)
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
                elif (msg.note < 36 or msg.note > 43):
                    print("Your LPD8 should be on Prog1!")
                    vote = False
                return(vote)
                #break
        
    

class KeyboardVoteController(VoteController):

    def get_vote():
        #vote = int(input("Please rate the pad between 1-8: "))
        got_info = False
        try:
            vote = int(input("Please rate the pad between 1-8: "))
            if (vote > 0 and vote <= 8):
                got_info = True
            else:
                keyboard_vote_instructions()

        except KeyboardInterrupt:
            # allows for exiting despite recursion
            sys.exit(0)
        except:
            keyboard_vote_instructions()
            got_info = False

        if (got_info == True) :
            return vote
        else:
            return keyboard_vote()

    def keyboard_vote_instructions():
        print("Needs to be an integer between 1-8.")

    def give_instructions():
        pass

class VoteProcessor():
    def record_vote():
        pass

def get_lpd8_port():
    ins = mido.get_input_names()
    if ('LPD8' in ins):
        print("LPD8 connected")
        port = mido.open_input('LPD8')
        return port
    else: return False

def keyboard_vote_instructions():
    print("Needs to be an integer between 1-8.")

def keyboard_vote():
    #vote = int(input("Please rate the pad between 1-8: "))
    got_info = False
    try:
        vote = int(input("Please rate the pad between 1-8: "))
        if (vote > 0 and vote <= 8):
            got_info = True
        else:
            keyboard_vote_instructions()

    except KeyboardInterrupt:
        # allows for exiting despite recursion
        sys.exit(0)
    except:
        keyboard_vote_instructions()
        got_info = False

    if (got_info == True) :
        return vote
    else:
        return keyboard_vote()


def lpd8_vote(port):
    for msg in port:
        #print(msg)
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
            elif (msg.note < 36 or msg.note > 43):
                print("Your LPD8 should be on Prog1!")
                vote = False
            return(vote)
            #break
            

        if (msg.is_cc()):
            print(msg)
            print(msg.type, ": ", msg.control, msg.value, msg.time)
            #print("")
            #print(msg.type)
            #break

def vote(port):
    if port:
        vote_result = lpd8_vote(port)
    else:
        print("LPD8 port not connected. Using keyboard instead.") 
        vote_result = keyboard_vote()
    return vote_result

main()
