#!/usr/bin/env python3
"""Guide a T4 viewing and turn the local record into a pre-purchase report."""

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import t4_logger
from kw1281 import MEASURED, Block, LinkError

PHASES = {
    "cold_key_on": "Cold, ignition on",
    "first_idle": "First idle",
    "road": "Road test",
    "warm_idle": "Warm idle, parked",
    "after_drive": "After the drive, ignition on",
}
NOTES = {
    "cold_start": "Cold start and smoke",
    "service": "Belts, water pump and service invoices",
    "body": "Visible rust, damage or fresh coatings",
    "road_feel": "Road observations",
    "hot_restart": "Hot restart",
    "lift": "Lift inspection, leaks and underside",
}
MEASUREMENTS = {
    "engine_rpm": ("Engine speed", "rpm"),
    "coolant_temperature": ("Coolant", "°C"),
    "intake_air_temperature": ("Intake air", "°C"),
    "fuel_temperature": ("Fuel temperature", "°C"),
    "ecu_supply_voltage": ("ECU supply", "V"),
    "charge_pressure_requested_absolute": ("Requested charge pressure (absolute)", "mbar"),
    "charge_pressure_actual_absolute": ("Actual charge pressure (absolute)", "mbar"),
    "air_mass_requested": ("Requested air mass", "mg/stroke"),
    "air_mass_actual": ("Actual air mass", "mg/stroke"),
    "injection_quantity": ("Injection quantity", "mg/stroke"),
}


def read_phase(args, output, phase, command, *, group=None, samples=None, seconds=None):
    options = [command, "--port", args.port, "--baud", str(args.baud),
               "--byte-delay-ms", str(args.byte_delay_ms), "--machine", args.machine,
               "--context", phase]
    if group is not None:
        options.extend(("--group", str(group)))
    if samples is not None:
        options.extend(("--count", str(samples)))
    if seconds is not None:
        options.extend(("--seconds", str(seconds)))
    capture_args = t4_logger.arguments(options)
    records = []
    try:
        t4_logger.capture(capture_args, records)
    except (LinkError, OSError) as exc:
        records.append(t4_logger.observation(
            capture_args, "inspection_capture_error", str(exc), request=command, group=group,
        ))
        print(f"{PHASES[phase]} — {exc}", file=sys.stderr)
    finally:
        t4_logger.append_records(output, records)


def note(args, output, kind, prompt):
    value = input(f"{NOTES[kind]} — {prompt} (Enter to skip): ").strip()
    if value:
        t4_logger.append_records(output, [note_record(args, kind, value)])


def note_record(args, kind, value):
    return t4_logger.observation(
        args, kind, value, source="viewing-note", context="manual-inspection",
    )


def confirmed(prompt):
    return input(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}


def viewing(args, output):
    print("Caretaker T4 viewing. The laptop records engine data and your observations.")
    if confirmed("Van still cold, adapter connected and ignition on with engine stopped?"):
        read_phase(args, output, "cold_key_on", "faults")
        read_phase(args, output, "cold_key_on", "log", group=7, samples=1)
    if confirmed("Engine just started and now idling outdoors?"):
        read_phase(args, output, "first_idle", "log", group=1, samples=10)
    note(args, output, "cold_start", "record ambient conditions, cranking, idle and visible smoke")
    note(args, output, "service", "record the invoice date, mileage and work actually listed")
    note(args, output, "body", "record locations and local photo filenames")
    print(f"The road log runs for {args.drive_seconds} seconds after connecting. "
          "Warm the engine on the drive first and have the passenger operate the laptop.")
    if confirmed("Warm engine and ready for a normal road-test segment?"):
        read_phase(args, output, "road", "log", group=11, seconds=args.drive_seconds)
        input("Capture ended. Press Enter once parked. ")
    note(args, output, "road_feel", "record any hesitation, smoke, vibration, noise or warning light")
    if confirmed("Parked outdoors with the engine warm and idling?"):
        read_phase(args, output, "warm_idle", "log", group=12, samples=5)
        read_phase(args, output, "warm_idle", "log", group=3, samples=5)
        read_phase(args, output, "warm_idle", "log", group=1, samples=10)
    note(args, output, "hot_restart", "record whether the warm engine restarted cleanly")
    if confirmed("Parked after the test, ignition on with engine stopped, ready to re-read faults?"):
        read_phase(args, output, "after_drive", "faults")
    note(args, output, "lift", "record the shop's written findings or leave pending")


def demo(args, output):
    print("Generating a simulated inspection.")
    args.baud = 9600
    args.context = "cold_key_on"
    part = "074906021F"
    ident = t4_logger.identification_record(args, [part, "SYNTHETIC DEMO"], (0x01, 0x8A))
    records = [ident, *t4_logger.fault_records(args, part, "read", [])]
    start = datetime.now(timezone.utc) - timedelta(minutes=20)
    for phase, group, sample, seconds, payload in (
        ("cold_key_on", 7, 1, 0, "05 0A 71 11 00 00 05 0A 72 05 0A 71"),
        ("first_idle", 1, 1, 30, "01 14 CC 27 08 A0 15 64 10 05 0A 72"),
        ("road", 11, 1, 800, "01 64 69 12 FA 9B 12 FA 94 17 64 40"),
        ("road", 11, 2, 805, "01 64 7D 12 FA AD 12 FA A8 17 64 40"),
        ("warm_idle", 12, 1, 905, "11 00 00 1F 00 00 06 64 89 05 0A B5"),
        ("warm_idle", 3, 1, 910, "01 14 C3 31 64 64 31 64 68 17 64 40"),
        ("warm_idle", 1, 1, 915, "01 14 C3 27 08 A0 15 64 10 05 0A B5"),
    ):
        args.context, args.group = phase, group
        block = Block(sample, MEASURED, bytes.fromhex(payload))
        timestamp = (start + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")
        records.extend(t4_logger.measurement_records(args, part, block, sample, timestamp=timestamp))
    args.context = "after_drive"
    records.extend(t4_logger.fault_records(args, part, "read", []))
    records.append(note_record(
        args, "body", "Bubbling paint noted by the right sill. Lift check requested.",
    ))
    t4_logger.append_records(output, records)


def load_records(path):
    with path.open(encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("expected a JSON object")
                for field in ("machine", "kind", "value", "context", "unit", "timestamp"):
                    if not isinstance(record.get(field), str):
                        raise ValueError(f"missing or invalid {field}")
                if datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00")).utcoffset() is None:
                    raise ValueError("timestamp needs a timezone")
                if not isinstance(record.get("simulated"), bool):
                    raise ValueError("missing or invalid simulated flag")
                if not isinstance(record.get("details", {}), dict):
                    raise ValueError("invalid details")
            except ValueError as exc:
                raise ValueError(f"{path}, line {number}: {exc}") from exc
            yield record


def measurements(records):
    values = defaultdict(list)
    for record in records:
        expected = MEASUREMENTS.get(record["kind"])
        if expected is None or record["unit"] != expected[1]:
            continue
        value = numeric_value(record)
        if value is not None:
            values[record["kind"]].append(value)
    for kind, (label, unit) in MEASUREMENTS.items():
        samples = values[kind]
        if samples:
            low, high = min(samples), max(samples)
            span = f"{low:g}" if low == high else f"{low:g}–{high:g}"
            yield f"{label} {span} {unit}"


def numeric_value(record):
    try:
        value = float(record["value"])
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def pressure_comparison(rows):
    requested = "charge_pressure_requested_absolute"
    actual = "charge_pressure_actual_absolute"
    samples = defaultdict(set)
    for row in rows:
        if row["kind"] not in (requested, actual) or row["unit"] != "mbar":
            continue
        details = row.get("details", {})
        sample = details.get("sample")
        capture_id = details.get("capture_id")
        if not isinstance(sample, int) or details.get("group") != 11:
            continue
        if capture_id is not None and not isinstance(capture_id, str):
            continue
        if numeric_value(row) is not None:
            samples[(row["timestamp"], sample, capture_id)].add(row["kind"])
    timestamps = [datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                  for (stamp, _, _), fields in samples.items() if requested in fields and actual in fields]
    if timestamps:
        span = (max(timestamps) - min(timestamps)).total_seconds()
        return f"Paired pressure samples: {len(timestamps)} over {span:.1f} s."
    return "No paired charge-pressure readings."


def render_report(records):
    lines = ["# T4 pre-purchase inspection", ""]
    if len({row["machine"] for row in records}) > 1:
        raise ValueError("Use one machine per inspection report.")
    if any(row["simulated"] for row in records):
        lines.extend(("**Contains simulated data. Use as a software example only.**", ""))
    started = next((row for row in records if row["kind"] == "inspection_started"), None)
    if started and not started["simulated"]:
        lines.extend((f"Viewing started {started['timestamp']}.", ""))
    ids = sorted({row["value"] for row in records if row["kind"] == "ecu_identification"})
    lines.extend((f"Engine ECU: {', '.join(ids) if ids else 'unconfirmed'}.", ""))
    if len(ids) > 1:
        lines.extend(("**Multiple ECU identities recorded. Review the raw log before using these readings.**", ""))
    by_phase = defaultdict(list)
    for record in records:
        by_phase[record["context"]].append(record)

    for phase, label in PHASES.items():
        rows = by_phase[phase]
        facts = list(measurements(rows))
        for row in rows:
            if row["kind"] == "ecu_fault_memory":
                facts.append("Engine fault memory unavailable" if row["value"] == "unavailable"
                             else f"Stored engine faults reported: {row['value']}")
            elif row["kind"] == "ecu_fault_code":
                facts.append(f"Code {row['value']} (status byte {row.get('details', {}).get('status_hex', '?')})")
            elif row["kind"] == "inspection_capture_error":
                details = row.get("details", {})
                request = details.get("request", "capture")
                if isinstance(details.get("group"), int):
                    request = f"group {details['group']:03d}"
                facts.append(f"{str(request).capitalize()} incomplete: {row['value']}")
        raw = sum(row.get("details", {}).get("decode") == "raw" for row in rows)
        unavailable = sorted({row["kind"] for row in rows
                              if row["kind"].startswith("kw1281_group_") and row["value"] == "unavailable"})
        if raw:
            facts.append(f"{raw} undecoded readings kept in the log")
        if unavailable:
            facts.append("Unavailable: " + ", ".join(unavailable))
        if phase == "road" and rows:
            facts.append(pressure_comparison(rows))
        lines.append(f"- **{label}.** {' · '.join(facts) if facts else 'No measurements recorded.'}")

    lines.extend(("", "## Inspection and paperwork", ""))
    for kind, label in NOTES.items():
        notes = [row["value"] for row in records if row["kind"] == kind]
        lines.append(f"- **{label}.** {' · '.join(notes) if notes else 'Pending.'}")
    lines.extend((
        "", "ECU values are reported readings. The ACV field labels still need a workshop comparison. "
        "Review requested and actual pressure in the same timestamped sample and look for a pattern under "
        "comparable load. A single gap cannot establish a fault. Lift findings and invoices have their own evidence.",
    ))
    return "\n".join(lines)


def arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in (
        ("run", "Start an inspection and save a new local JSONL record"),
        ("demo", "Save a simulated inspection to a new JSONL record"),
        ("report", "Regenerate the report from an existing record"),
        ("note", "Add a finding or photo reference after the viewing"),
    ):
        command = commands.add_parser(name, help=description)
        command.add_argument("--session", type=Path, required=True)
        if name in {"run", "demo"}:
            command.add_argument("--machine", default="t4-demo" if name == "demo" else "t4-viewing")
        if name == "note":
            command.add_argument("--kind", required=True, choices=NOTES)
            command.add_argument("value", help="Finding, date or local photo reference")
        if name == "run":
            command.add_argument("--port", required=True)
            command.add_argument("--baud", type=int, choices=(4800, 9600, 10400), default=9600)
            command.add_argument("--byte-delay-ms", type=int, choices=range(2, 11), default=5)
            command.add_argument("--drive-seconds", type=t4_logger.seconds_argument, default=180)
    return parser.parse_args(argv)


def main(argv=None):
    args = arguments(argv)
    path = args.session.expanduser()
    try:
        if args.command == "report":
            print(render_report(list(load_records(path))))
            return 0
        if args.command == "note":
            records = list(load_records(path))
            machines = {row["machine"] for row in records}
            if len(machines) != 1 or not args.value.strip():
                raise ValueError("A note needs a non-empty finding and a session for exactly one machine.")
            args.machine = machines.pop()
            record = note_record(args, args.kind, args.value.strip())
            record["simulated"] = any(row["simulated"] for row in records)
            with path.open("a", encoding="utf-8") as output:
                t4_logger.append_records(output, [record])
            print(f"Finding added to {path}.")
            return 0

        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                record = t4_logger.observation(
                    args, "inspection_started", "viewing", context="inspection",
                    source="caretaker-t4-inspection",
                )
                t4_logger.append_records(output, [record])
                if args.command == "demo":
                    demo(args, output)
                else:
                    viewing(args, output)
        except (KeyboardInterrupt, EOFError):
            print(f"Viewing stopped. The partial record is in {path}.", file=sys.stderr)
            return 130
        print(f"\nRecord saved to {path}.\n")
        print(render_report(list(load_records(path))))
    except FileExistsError:
        print(f"{path} already exists. Use 'report' or choose a new session file.", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Caretaker T4: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
