import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import t4_inspect
import t4_logger
from kw1281 import MEASURED, Block, LinkError


class InspectionTests(unittest.TestCase):
    def test_viewing_records_partial_capture_and_allows_lift_note(self):
        def capture(args, records):
            if args.context == "cold_key_on":
                raise LinkError("No ECU response")
            if args.context == "road":
                self.assertEqual((args.group, args.seconds), (11, 20))
                block = Block(1, MEASURED, bytes.fromhex("01 64 69 12 FA 9B 12 FA 94"))
                records.extend(t4_logger.measurement_records(args, "074906021F", block, 1))
                raise LinkError("USB disconnected")
            self.fail(f"Unexpected capture for {args.context}")

        answers = ["y", "", "", "", "Bubbling by right sill", "y", "",
                   "Hesitation on the hill", "", "", "", ""]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "viewing.jsonl"
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()), \
                    patch("builtins.input", side_effect=answers), \
                    patch.object(t4_logger, "capture", side_effect=capture):
                status = t4_inspect.main(["run", "--port", "/dev/test", "--session", str(path),
                                          "--drive-seconds", "20"])
            self.assertEqual(status, 0)
            self.assertIn("Paired pressure samples: 1", output.getvalue())
            self.assertIn("Group 011 incomplete: USB disconnected", output.getvalue())
            self.assertIn("**Lift inspection, leaks and underside.** Pending.", output.getvalue())
            self.assertNotIn("Stored engine faults reported: 0", output.getvalue())

            with redirect_stdout(io.StringIO()):
                status = t4_inspect.main(["note", "--session", str(path), "--kind", "lift",
                                          "Mechanic report saved locally"])
            self.assertEqual(status, 0)
            rows = list(t4_inspect.load_records(path))
            self.assertEqual(rows[-1]["source"], "viewing-note")
            self.assertEqual(rows[-1]["machine"], "t4-viewing")
            self.assertIn("Mechanic report saved locally", t4_inspect.render_report(rows))
            self.assertFalse(any(row["simulated"] for row in rows))

    def test_demo_is_replayable_and_cannot_overwrite_a_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.jsonl"
            args = ["demo", "--session", str(path)]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(t4_inspect.main(args), 0)
            content = path.read_text()
            rows = [json.loads(line) for line in content.splitlines()]
            self.assertTrue(all(row["simulated"] for row in rows))
            report = t4_inspect.render_report(list(t4_inspect.load_records(path)))
            self.assertIn("Paired pressure samples: 2 over 5.0 s", report)
            self.assertIn("Contains simulated data", report)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(t4_inspect.main(args), 1)
            self.assertEqual(path.read_text(), content)

    def test_timed_logger_stops_at_deadline(self):
        args = t4_logger.arguments(["log", "--port", "/dev/test", "--group", "11", "--seconds", "10"])
        port = unittest.mock.MagicMock()
        session = unittest.mock.Mock()
        session.connect.return_value = ["074906021F"]
        session.keywords = (0x01, 0x8A)
        session.read_group.return_value = Block(1, MEASURED, bytes.fromhex("01 14 C3"))
        serial = SimpleNamespace(Serial=lambda **_: port)
        ports = SimpleNamespace(comports=lambda: [SimpleNamespace(device="/dev/test", vid=0x0403)])
        records = []
        with patch.object(t4_logger, "serial_support", return_value=(serial, ports)), \
                patch.object(t4_logger, "EngineSession", return_value=session), \
                patch.object(t4_logger.time, "monotonic", side_effect=[100.0, 100.0, 103.0, 110.0]):
            t4_logger.capture(args, records)
        self.assertEqual(session.read_group.call_count, 2)
        session.close.assert_called_once_with()
        self.assertEqual([row["kind"] for row in records], ["ecu_identification", "engine_rpm", "engine_rpm"])


if __name__ == "__main__":
    unittest.main()
