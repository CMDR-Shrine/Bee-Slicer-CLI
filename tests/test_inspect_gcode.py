import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("inspect_gcode", Path(__file__).resolve().parents[1] / "src/inspect_gcode.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OfflineInspectionTests(unittest.TestCase):
    def report(self, text, manifest=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.gcode"
            path.write_text(text)
            return module.inspect(path, manifest)

    def test_first_target_is_not_later_layer_or_comment(self):
        r = self.report("; M109 S260\nM109 S215 ; M104 S250\nM104 S210\nM104 S0\n")
        self.assertEqual(r["first_positive_nozzle_target_c"], 215)
        self.assertEqual([t["target_c"] for t in r["nozzle_temperature_commands"]], [215, 210])

    def test_line_numbers_lowercase_and_r_target(self):
        r = self.report("N14 m109 R240\nM190 S70\n")
        self.assertEqual(r["first_positive_nozzle_target_c"], 240)
        self.assertEqual(r["heated_bed_command_lines"], [2])

    def test_known_effects_and_missing_dispatch(self):
        r = self.report("M206 X500\nM206 X400\nM24\n", {"firmware_dispatch_commands": {"M": [206], "G": []}})
        self.assertEqual(r["commands"]["M206"], 2)
        self.assertEqual(r["not_in_inspected_firmware_dispatch"], ["M24"])
        self.assertEqual(len(r["bee_command_notes"]), 2)

    def test_no_temperature_does_not_guess(self):
        self.assertIsNone(self.report("G28\nM104 S0\n")["first_positive_nozzle_target_c"])

    def test_compact_parameters(self):
        self.assertEqual(self.report("M109S240\n")["first_positive_nozzle_target_c"], 240)


if __name__ == "__main__":
    unittest.main()
