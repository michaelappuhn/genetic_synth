import unittest

from genetic.cli import parse_args


class TestRunSubcommandDefaults(unittest.TestCase):
    def test_bare_invocation_defaults_to_run(self):
        args = parse_args([])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 0)
        self.assertEqual(args.pop_size, 4)
        self.assertEqual(args.generations, 5)
        self.assertEqual(args.crossover_rate, 0.5)
        self.assertEqual(args.mutation_rate, 0.3)
        self.assertEqual(args.mutation_indpb, 0.15)
        self.assertEqual(args.tournament_size, 2)
        self.assertIsInstance(args.seed, int)
        self.assertFalse(args.no_log)
        self.assertIsNone(args.seed_from_patch)

    def test_bare_flags_default_to_run(self):
        args = parse_args(["--pad", "3"])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 3)
        self.assertEqual(args.midi_channel, 3)

    def test_explicit_run_subcommand(self):
        args = parse_args(["run", "--pad", "2"])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 2)

    def test_midi_channel_override(self):
        args = parse_args(["--pad", "0", "--midi-channel", "10"])
        self.assertEqual(args.subcommand, "run")
        self.assertEqual(args.pad, 0)
        self.assertEqual(args.midi_channel, 10)

    def test_seed_override(self):
        args = parse_args(["--seed", "42"])
        self.assertEqual(args.seed, 42)

    def test_no_log_flag(self):
        args = parse_args(["--no-log"])
        self.assertTrue(args.no_log)

    def test_seed_from_patch(self):
        args = parse_args(["--seed-from-patch", "kraken"])
        self.assertEqual(args.seed_from_patch, "kraken")

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


class TestSaveBestSubcommand(unittest.TestCase):
    def test_with_name(self):
        args = parse_args(["save-best", "runs/2026-x-pad0", "--name", "kraken"])
        self.assertEqual(args.subcommand, "save-best")
        self.assertEqual(args.run_dir, "runs/2026-x-pad0")
        self.assertEqual(args.name, "kraken")

    def test_name_optional(self):
        args = parse_args(["save-best", "runs/2026-x-pad0"])
        self.assertEqual(args.subcommand, "save-best")
        self.assertIsNone(args.name)


class TestPlaySubcommand(unittest.TestCase):
    def test_positional_name(self):
        args = parse_args(["play", "kraken"])
        self.assertEqual(args.subcommand, "play")
        self.assertEqual(args.patch_name, "kraken")


class TestResumeSubcommand(unittest.TestCase):
    def test_positional_dir(self):
        args = parse_args(["resume", "runs/2026-x-pad0"])
        self.assertEqual(args.subcommand, "resume")
        self.assertEqual(args.run_dir, "runs/2026-x-pad0")

    def test_generations_override(self):
        args = parse_args(["resume", "runs/2026-x-pad0", "--generations", "3"])
        self.assertEqual(args.generations, 3)


if __name__ == "__main__":
    unittest.main()
