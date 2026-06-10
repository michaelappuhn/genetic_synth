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


if __name__ == "__main__":
    unittest.main()
