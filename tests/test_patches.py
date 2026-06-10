import json
import tempfile
import unittest
from pathlib import Path

from genetic.patches import (
    save,
    load,
    from_individual,
    to_individual,
    machine_name_for,
)


class TestMachineNameFor(unittest.TestCase):
    def test_bd_classic_for_drum_pad(self):
        self.assertEqual(machine_name_for(pad=0, machine_num=0), "bd classic")

    def test_bd_acoustic_for_drum_pad(self):
        self.assertEqual(machine_name_for(pad=0, machine_num=30), "bd acoustic")

    def test_drum_machines_same_across_drum_pads(self):
        for pad in (0, 1, 2, 3):
            self.assertEqual(machine_name_for(pad=pad, machine_num=13), "bd fm")

    def test_unknown_falls_back_to_machine_number(self):
        # Pad 4 is BT track — drum machine table doesn't apply
        self.assertEqual(machine_name_for(pad=4, machine_num=30), "machine_30")

    def test_unknown_machine_on_drum_pad(self):
        # Machine 99 isn't in the table
        self.assertEqual(machine_name_for(pad=0, machine_num=99), "machine_99")


class TestSaveLoad(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            patch = {
                "version": 1,
                "name": "test",
                "pad": 0,
                "midi_channel": 0,
                "machine_number": 30,
                "machine_name": "bd acoustic",
                "parameters": [{"cc": 16, "value": 127, "name": "Source Level"}],
                "fitness": 8.0,
                "source": {
                    "run_dir": "runs/2026-06-10-1422-pad0",
                    "generation": 4,
                    "eval_idx": 2,
                },
            }
            path = Path(tmp) / "test.json"
            save(path, patch)
            loaded = load(path)
            self.assertEqual(loaded, patch)


class _FakeParam:
    """Stand-in for synthesizer.parameters.Parameter — just cc, value, name."""
    def __init__(self, cc, value, name="n/a"):
        self.cc = cc
        self.value = value
        self.name = name


class TestFromIndividual(unittest.TestCase):
    def test_builds_full_enumeration_patch(self):
        # Three params, one is machine-select, rest are evolved + fixed
        params = [
            _FakeParam(16, 127, "Source Level"),
            _FakeParam(17, 64, "Tune"),
            _FakeParam(70, 0, "Filter Attack"),
        ]
        patch = from_individual(
            pad=0, midi_channel=0,
            machine_num=30, machine_name="bd acoustic",
            params=params, fitness=8.0,
            source={"run_dir": "runs/x", "generation": 1, "eval_idx": 0},
        )
        self.assertEqual(patch["version"], 1)
        self.assertEqual(patch["pad"], 0)
        self.assertEqual(patch["midi_channel"], 0)
        self.assertEqual(patch["machine_number"], 30)
        self.assertEqual(patch["machine_name"], "bd acoustic")
        self.assertEqual(patch["fitness"], 8.0)
        self.assertEqual(len(patch["parameters"]), 3)
        self.assertEqual(patch["parameters"][0],
                         {"cc": 16, "value": 127, "name": "Source Level"})


class TestToIndividual(unittest.TestCase):
    def test_decodes_patch_to_individual(self):
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 30, "machine_name": "bd acoustic",
            "parameters": [
                {"cc": 16, "value": 127, "name": "Source Level"},
                {"cc": 17, "value": 64, "name": "Tune"},
                {"cc": 70, "value": 0, "name": "Filter Attack"},
            ],
            "fitness": 8.0, "source": {},
        }
        machines = [0, 13, 21, 22, 26, 30]    # 30 is at index 5
        evolved_ccs = [16, 17]                # CC 70 is fixed, not in genome
        ind, dropped = to_individual(patch, machines, evolved_ccs, list)
        self.assertEqual(ind, [5, 127, 64])
        # CC 70 is in the patch but not in evolved_ccs — it gets "dropped"
        # from the genome. Caller (e.g. _make_initial_population) is expected
        # to filter dropped against its own fixed_values dict before warning.
        self.assertEqual(dropped, {70: 0})

    def test_drops_ccs_not_in_evolved(self):
        # Patch carries CC 109 (LFO Depth) but current pad doesn't evolve it
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 30, "machine_name": "bd acoustic",
            "parameters": [
                {"cc": 16, "value": 127, "name": "Source Level"},
                {"cc": 109, "value": 60, "name": "LFO Depth"},
            ],
            "fitness": 8.0, "source": {},
        }
        machines = [0, 30]
        evolved_ccs = [16]   # 109 is not evolved here
        ind, dropped = to_individual(patch, machines, evolved_ccs, list)
        self.assertEqual(ind, [1, 127])
        self.assertEqual(dropped, {109: 60})

    def test_machine_not_in_filter_raises(self):
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 30, "machine_name": "bd acoustic",
            "parameters": [{"cc": 16, "value": 127, "name": "Source Level"}],
            "fitness": 8.0, "source": {},
        }
        machines = [0, 13, 21]   # 30 isn't here
        evolved_ccs = [16]
        with self.assertRaises(ValueError) as cm:
            to_individual(patch, machines, evolved_ccs, list)
        self.assertIn("30", str(cm.exception))

    def test_evolved_cc_missing_from_patch_raises(self):
        # evolved_ccs expects CC 17 but patch doesn't have it
        patch = {
            "version": 1, "name": "x", "pad": 0, "midi_channel": 0,
            "machine_number": 0, "machine_name": "bd classic",
            "parameters": [{"cc": 16, "value": 127, "name": "Source Level"}],
            "fitness": 5.0, "source": {},
        }
        machines = [0]
        evolved_ccs = [16, 17]
        with self.assertRaises(ValueError) as cm:
            to_individual(patch, machines, evolved_ccs, list)
        self.assertIn("17", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
