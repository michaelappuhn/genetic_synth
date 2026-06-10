import unittest

from genetic.cli import parse_args


class TestParseArgs(unittest.TestCase):
    def test_defaults(self):
        args = parse_args([])
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 0)  # defaults to pad
        self.assertEqual(args.pop_size, 4)
        self.assertEqual(args.generations, 5)
        self.assertEqual(args.crossover_rate, 0.5)
        self.assertEqual(args.mutation_rate, 0.3)
        self.assertEqual(args.mutation_indpb, 0.15)
        self.assertEqual(args.tournament_size, 2)
        self.assertIsInstance(args.seed, int)
        self.assertFalse(args.no_log)

    def test_pad_override_propagates_to_midi_channel(self):
        args = parse_args(["--pad", "3"])
        self.assertEqual(args.pad, 3)
        self.assertEqual(args.midi_channel, 3)

    def test_midi_channel_override(self):
        args = parse_args(["--pad", "0", "--midi-channel", "10"])
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 10)

    def test_seed_override(self):
        args = parse_args(["--seed", "42"])
        self.assertEqual(args.seed, 42)

    def test_no_log_flag(self):
        args = parse_args(["--no-log"])
        self.assertTrue(args.no_log)

    def test_all_numeric_overrides(self):
        args = parse_args([
            "--pop-size", "8",
            "--generations", "10",
            "--mutation-rate", "0.4",
            "--crossover-rate", "0.7",
            "--mutation-indpb", "0.2",
            "--tournament-size", "3",
        ])
        self.assertEqual(args.pop_size, 8)
        self.assertEqual(args.generations, 10)
        self.assertEqual(args.mutation_rate, 0.4)
        self.assertEqual(args.crossover_rate, 0.7)
        self.assertEqual(args.mutation_indpb, 0.2)
        self.assertEqual(args.tournament_size, 3)


if __name__ == "__main__":
    unittest.main()
