import io
import json
import sys
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acv
import t4_logger
from kw1281 import Block, EngineSession, KLine, LinkError, address_bits


class TranscriptPort:
    """Expect an independent sequence of tester writes and ECU reads."""

    def __init__(self, transcript):
        self.transcript = deque(transcript)
        self.break_condition = False

    def reset_input_buffer(self):
        pass

    def read(self, size=1):
        direction, value = self.transcript.popleft()
        if direction != "read" or size != 1:
            raise AssertionError(f"Unexpected read before {direction} {value!r}")
        return value

    def write(self, value):
        expected = self.transcript.popleft()
        if expected != ("write", value):
            raise AssertionError(f"Expected {expected!r}, wrote {value!r}")
        return len(value)


def ecu_bytes(*values):
    return [("read", bytes((value,))) for value in values]


def tester_byte(value, *, complement=None):
    steps = [("write", bytes((value,))), ("read", bytes((value,)))]
    if complement is not None:
        steps.extend(ecu_bytes(complement))
    return steps


def from_ecu(frame):
    steps = []
    for byte in frame[:-1]:
        steps.extend(ecu_bytes(byte))
        steps.extend(tester_byte(255 - byte))
    return steps + ecu_bytes(frame[-1])


def to_ecu(frame):
    steps = []
    for byte in frame[:-1]:
        steps.extend(tester_byte(byte, complement=255 - byte))
    return steps + tester_byte(frame[-1])


def connected(*, repeat_sync=False):
    steps = ecu_bytes(0x55, 0x01, 0x8A) + tester_byte(0x75)
    if repeat_sync:
        steps += ecu_bytes(0x55, 0x01, 0x0A) + tester_byte(0xF5)
    # Synthetic identification starting near the counter wrap boundary.
    steps += from_ecu(b"\x0D\xFE\xF6074906021F\x03")
    steps += to_ecu(bytes.fromhex("03 FF 09 03"))
    steps += from_ecu(bytes.fromhex("03 00 09 03"))
    return steps


def session(transcript):
    port = TranscriptPort(transcript)
    link = KLine(port, sleep=lambda _: None)
    return port, EngineSession(link)


class LinkTests(unittest.TestCase):
    def test_address_waveform_and_early_rx_purge(self):
        class Clock:
            now = 0.0

            def monotonic(self):
                return self.now

            def sleep(self, seconds):
                self.now += seconds

        clock = Clock()
        events = []

        class Cable:
            @property
            def break_condition(self):
                return events[-1][1]

            @break_condition.setter
            def break_condition(self, value):
                events.append((round(clock.now, 3), value))

            def reset_input_buffer(self):
                events.append((round(clock.now, 3), "purge"))

        self.assertEqual(address_bits(1), (0, 1, 0, 0, 0, 0, 0, 0, 0, 1))
        self.assertEqual(address_bits(3)[8], 1)
        KLine(Cable(), sleep=clock.sleep, clock=clock.monotonic).slow_init()
        self.assertEqual(events, [(0.0, False), (0.35, True), (0.55, False),
                                  (0.75, True), (2.15, False), (2.18, "purge")])

    def test_identification_group_and_unavailable_group(self):
        transcript = connected(repeat_sync=True)
        transcript += to_ecu(bytes.fromhex("04 01 29 01 03"))
        transcript += from_ecu(bytes.fromhex("0F 02 E7 01 14 C3 27 08 A0 15 64 10 05 0A B5 03"))
        transcript += to_ecu(bytes.fromhex("04 03 29 0C 03"))
        transcript += from_ecu(bytes.fromhex("03 04 0A 03"))
        transcript += to_ecu(bytes.fromhex("03 05 06 03"))
        port, reader = session(transcript)
        self.assertEqual(reader.connect(), ["074906021F"])
        values = list(acv.group_observations(reader.read_group(1), 1, "074906021F"))
        self.assertEqual([row[:3] for row in values],
                         [("engine_rpm", "780", "rpm"),
                          ("injection_quantity", "5", "mg/stroke"),
                          ("quantity_adjuster_feedback_voltage", "1.6", "V"),
                          ("coolant_temperature", "81", "°C")])
        self.assertEqual(values[-1][3]["raw_hex"], "05 0A B5")
        result = list(acv.group_observations(reader.read_group(12), 12, "074906021F"))
        self.assertEqual(result[0][1], "unavailable")
        reader.close()
        self.assertFalse(port.transcript)

    def test_multiple_fault_blocks(self):
        transcript = connected()
        transcript += to_ecu(bytes.fromhex("03 01 07 03"))
        transcript += from_ecu(bytes.fromhex("06 02 FC 02 01 88 03"))
        transcript += to_ecu(bytes.fromhex("03 03 09 03"))
        transcript += from_ecu(bytes.fromhex("06 04 FC 46 5A A3 03"))
        transcript += to_ecu(bytes.fromhex("03 05 09 03"))
        transcript += from_ecu(bytes.fromhex("03 06 09 03"))
        transcript += to_ecu(bytes.fromhex("03 07 06 03"))
        port, reader = session(transcript)
        reader.connect()
        self.assertEqual(reader.read_faults(), ("read", [
            {"code": "00513", "status_hex": "88"}, {"code": "18010", "status_hex": "A3"},
        ]))
        reader.close()
        self.assertFalse(port.transcript)

    def test_empty_fault_memory_is_distinct_from_rejection(self):
        prefix = connected() + to_ecu(bytes.fromhex("03 01 07 03"))
        for reply, expected in (("03 02 09 03", "unavailable"),
                                ("03 02 0A 03", "unavailable"),
                                ("06 02 FC FF FF 88 03", "read")):
            with self.subTest(reply=reply):
                transcript = prefix + from_ecu(bytes.fromhex(reply))
                if expected == "read":
                    transcript += to_ecu(bytes.fromhex("03 03 09 03"))
                    transcript += from_ecu(bytes.fromhex("03 04 09 03"))
                    transcript += to_ecu(bytes.fromhex("03 05 06 03"))
                else:
                    transcript += to_ecu(bytes.fromhex("03 03 06 03"))
                port, reader = session(transcript)
                reader.connect()
                self.assertEqual(reader.read_faults(), (expected, []))
                reader.close()
                self.assertFalse(port.transcript)

    def test_wrong_protocol_or_complement_stops_the_exchange(self):
        port, reader = session(ecu_bytes(0x55, 0xE9, 0x8F))
        with self.assertRaisesRegex(LinkError, "protocol 2025"):
            reader.connect()
        self.assertFalse(port.transcript)
        port, reader = session(connected() + tester_byte(4, complement=0))
        reader.connect()
        with self.assertRaisesRegex(LinkError, "ECU complement"):
            reader.read_group(1)
        self.assertFalse(port.transcript)

    def test_truncated_frame_and_mismatched_counter_stop(self):
        for tail, expected in (
            ([("read", b"")], "Timed out"),
            (ecu_bytes(0x03) + tester_byte(0xFC) + ecu_bytes(0x55), "block counter"),
        ):
            with self.subTest(expected=expected):
                port, reader = session(connected() + to_ecu(bytes.fromhex("04 01 29 01 03")) + tail)
                reader.connect()
                with self.assertRaisesRegex(LinkError, expected):
                    reader.read_group(1)
                self.assertFalse(port.transcript)

    def test_unallowed_requests_never_send_bytes(self):
        port, reader = session(connected())
        reader.connect()
        with self.assertRaises(ValueError):
            reader.read_group(0)
        with self.assertRaises(ValueError):
            reader._send(0x05)
        self.assertFalse(port.transcript)


class ObservationTests(unittest.TestCase):
    def test_wrong_type_or_ecu_keeps_raw_bytes(self):
        self.assertEqual(acv.part_number(["074 906 021 F"]), "074906021F")
        for part, triplet in ((None, "01 14 C3"), ("074906021F", "07 14 C3")):
            with self.subTest(part=part):
                result = list(acv.group_observations(Block(1, 0xE7, bytes.fromhex(triplet)), 1, part))
                self.assertEqual(result[0][:3], ("kw1281_group_001_field_1", triplet, ""))
                self.assertEqual(result[0][3]["decode"], "raw")

    def test_voltage_is_ecu_supply_and_boost_is_absolute(self):
        voltage = Block(1, 0xE7, bytes.fromhex("10 00 00 1F 00 00 06 64 7E 05 0A B5"))
        pressure = Block(1, 0xE7, bytes.fromhex("01 14 C3 12 FA 64 12 FA 63 17 64 40"))
        observations = [*acv.group_observations(voltage, 12, "074906021F"),
                        *acv.group_observations(pressure, 11, "074906021F")]
        result = {name: (value, unit) for name, value, unit, _ in observations}
        self.assertEqual(result["ecu_supply_voltage"], ("12.6", "V"))
        self.assertEqual(result["charge_pressure_requested_absolute"], ("1000", "mbar"))
        self.assertEqual(result["charge_pressure_actual_absolute"], ("990", "mbar"))

    def test_demo_and_partial_capture_produce_usable_jsonl(self):
        output = io.StringIO()
        args = t4_logger.arguments(["demo"])
        t4_logger.run(args, output)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertTrue(row["simulated"])
            self.assertTrue({"timestamp", "machine", "kind", "value", "unit", "source", "context"} <= row.keys())

        def interrupted_capture(args, records):
            records.append(t4_logger.observation(args, "ecu_identification", "074906021F"))
            raise LinkError("Lost link")

        output = io.StringIO()
        args = t4_logger.arguments(["log", "--port", "/dev/fake"])
        with patch.object(t4_logger, "capture", side_effect=interrupted_capture):
            with self.assertRaisesRegex(LinkError, "Lost link"):
                t4_logger.run(args, output)
        self.assertFalse(json.loads(output.getvalue())["simulated"])


if __name__ == "__main__":
    unittest.main()
