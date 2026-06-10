import unittest
from unittest.mock import MagicMock

import mido

from user_interface.voter import LPD8VoteController


class FakePort:
    """Minimal mido-port stand-in for tests."""
    def __init__(self, messages):
        self._queue = list(messages)

    def iter_pending(self):
        while self._queue:
            yield self._queue.pop(0)


def _make_controller(messages):
    c = LPD8VoteController()
    c.port = FakePort(messages)
    c.is_connected = True
    return c


class TestLPD8GetVote(unittest.TestCase):
    def test_pad_1_returns_vote_1(self):
        c = _make_controller([mido.Message("note_on", note=36, velocity=100)])
        self.assertEqual(c.get_vote(), 1)

    def test_pad_8_returns_vote_8(self):
        c = _make_controller([mido.Message("note_on", note=43, velocity=100)])
        self.assertEqual(c.get_vote(), 8)

    def test_replay_cc_calls_callback_then_waits_for_vote(self):
        msgs = [
            mido.Message("control_change", control=1, value=100),
            mido.Message("note_on", note=38, velocity=100),  # pad 3 → vote 3
        ]
        c = _make_controller(msgs)
        replay = MagicMock()
        vote = c.get_vote(on_replay=replay)
        self.assertEqual(vote, 3)
        replay.assert_called_once()

    def test_replay_cc_ignored_when_no_callback(self):
        msgs = [
            mido.Message("control_change", control=1, value=100),
            mido.Message("note_on", note=40, velocity=100),  # pad 5 → vote 5
        ]
        c = _make_controller(msgs)
        self.assertEqual(c.get_vote(), 5)  # no on_replay → CC silently ignored

    def test_non_replay_cc_ignored(self):
        msgs = [
            mido.Message("control_change", control=2, value=100),  # not replay CC
            mido.Message("note_on", note=36, velocity=100),
        ]
        c = _make_controller(msgs)
        replay = MagicMock()
        self.assertEqual(c.get_vote(on_replay=replay), 1)
        replay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
