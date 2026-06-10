import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from genetic.logging import (
    make_run_dir,
    write_config,
    log_generation,
    log_vote,
    read_last_generation,
)


class TestMakeRunDir(unittest.TestCase):
    def test_creates_named_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            run_dir = make_run_dir(base, pad=0, now=ts)
            self.assertTrue(run_dir.is_dir())
            self.assertEqual(run_dir.name, "2026-06-10-1422-pad0")
            self.assertEqual(run_dir.parent, base)

    def test_pad_suffix_distinguishes_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            d0 = make_run_dir(base, pad=0, now=ts)
            d3 = make_run_dir(base, pad=3, now=ts)
            self.assertNotEqual(d0, d3)
            self.assertTrue(d0.is_dir())
            self.assertTrue(d3.is_dir())


class TestWriteConfig(unittest.TestCase):
    def test_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            config = {"pad": 0, "seed": 42, "pop_size": 4}
            write_config(run_dir, config)
            text = (run_dir / "config.json").read_text()
            self.assertEqual(json.loads(text), config)


class TestLogGeneration(unittest.TestCase):
    def test_writes_one_jsonl_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=5.0, avg_fitness=3.2,
                               min_fitness=1.0, best_individual=[3, 64, 70],
                               n_evaluated=4)
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["gen"], 0)
            self.assertEqual(row["best_fitness"], 5.0)
            self.assertEqual(row["best_individual"], [3, 64, 70])
            self.assertEqual(row["n_evaluated"], 4)

    def test_two_lines_appended(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=5.0, avg_fitness=3.2,
                               min_fitness=1.0, best_individual=[1], n_evaluated=4)
                log_generation(fh, gen=1, best_fitness=7.0, avg_fitness=4.0,
                               min_fitness=2.0, best_individual=[2], n_evaluated=3)
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["gen"], 1)


class TestLogVote(unittest.TestCase):
    def test_writes_one_jsonl_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "votes.jsonl"
            with path.open("w") as fh:
                log_vote(fh, gen=0, eval_idx=2, machine=13,
                         evolved_ccs={"17": 64, "109": 60},
                         fixed_ccs={"70": 0},
                         vote=5, timestamp_iso="2026-06-10T14:22:31")
            row = json.loads(path.read_text().strip())
            self.assertEqual(row["gen"], 0)
            self.assertEqual(row["eval_idx"], 2)
            self.assertEqual(row["machine"], 13)
            self.assertEqual(row["evolved_ccs"], {"17": 64, "109": 60})
            self.assertEqual(row["vote"], 5)


class TestMakeRunDirCollision(unittest.TestCase):
    def test_collision_uses_dash_one_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            first = make_run_dir(base, pad=0, now=ts)
            second = make_run_dir(base, pad=0, now=ts)
            self.assertEqual(first.name, "2026-06-10-1422-pad0")
            self.assertEqual(second.name, "2026-06-10-1422-pad0-1")
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())

    def test_collision_increments_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            d0 = make_run_dir(base, pad=0, now=ts)
            d1 = make_run_dir(base, pad=0, now=ts)
            d2 = make_run_dir(base, pad=0, now=ts)
            self.assertEqual(d2.name, "2026-06-10-1422-pad0-2")

    def test_collision_raises_after_ten_tries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ts = datetime(2026, 6, 10, 14, 22)
            for _ in range(10):
                make_run_dir(base, pad=0, now=ts)
            with self.assertRaises(RuntimeError):
                make_run_dir(base, pad=0, now=ts)


class TestReadLastGeneration(unittest.TestCase):
    def test_returns_row_with_highest_best_fitness(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            path = run_dir / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=3.0, avg_fitness=2.0,
                               min_fitness=1.0, best_individual=[0], n_evaluated=4)
                log_generation(fh, gen=1, best_fitness=7.0, avg_fitness=4.0,
                               min_fitness=2.0, best_individual=[1, 64], n_evaluated=4)
                log_generation(fh, gen=2, best_fitness=5.0, avg_fitness=3.5,
                               min_fitness=1.0, best_individual=[2], n_evaluated=4)
            row = read_last_generation(run_dir)
            self.assertEqual(row["gen"], 1)
            self.assertEqual(row["best_fitness"], 7.0)
            self.assertEqual(row["best_individual"], [1, 64])

    def test_tiebreak_picks_latest_gen(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            path = run_dir / "generations.jsonl"
            with path.open("w") as fh:
                log_generation(fh, gen=0, best_fitness=5.0, avg_fitness=3.0,
                               min_fitness=1.0, best_individual=[1], n_evaluated=4)
                log_generation(fh, gen=1, best_fitness=5.0, avg_fitness=4.0,
                               min_fitness=2.0, best_individual=[2], n_evaluated=4)
            row = read_last_generation(run_dir)
            self.assertEqual(row["gen"], 1)   # tiebreak: latest gen wins


if __name__ == "__main__":
    unittest.main()
