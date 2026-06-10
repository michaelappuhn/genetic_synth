import sys
import time

import mido


class VoteController():
    def get_vote(self):
        pass


class LPD8VoteController(VoteController):
    is_connected = False

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
        else:
            return False

    def get_vote(self, on_replay=None, replay_cc=1):
        while True:
            for msg in self.port.iter_pending():
                if msg.type == 'note_on' and 36 <= msg.note <= 43:
                    return msg.note - 35   # 36→1, 43→8
                if msg.type == 'note_on':
                    print("Your LPD8 should be on Prog1!")
                    continue
                if msg.type == 'control_change' and msg.control == replay_cc:
                    if on_replay is not None:
                        on_replay()
            time.sleep(0.01)


class KeyboardVoteController(VoteController):

    def get_vote(self, on_replay=None, replay_cc=1):
        # Keyboard fallback has no replay support — accept the params for
        # signature parity with LPD8VoteController and ignore them.
        _ = on_replay, replay_cc
        got_info = False
        try:
            vote = int(input("Please rate the pad between 1-8: "))
            if (vote > 0 and vote <= 8):
                got_info = True
            else:
                keyboard_vote_instructions()

        except KeyboardInterrupt:
            sys.exit(0)
        except:
            keyboard_vote_instructions()
            got_info = False

        if (got_info == True):
            return vote
        else:
            return keyboard_vote()


def keyboard_vote_instructions():
    print("Needs to be an integer between 1-8.")


def keyboard_vote():
    got_info = False
    try:
        vote = int(input("Please rate the pad between 1-8: "))
        if (vote > 0 and vote <= 8):
            got_info = True
        else:
            keyboard_vote_instructions()

    except KeyboardInterrupt:
        sys.exit(0)
    except:
        keyboard_vote_instructions()
        got_info = False

    if (got_info == True):
        return vote
    else:
        return keyboard_vote()
