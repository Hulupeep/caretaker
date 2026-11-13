#!/usr/bin/env python3
"""Read a T4 engine ECU and output records compatible with Caretaker's log."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from acv import group_observations, part_number
from kw1281 import ACK, ALLOWED_GROUPS, MEASURED, NAK, Block, EngineSession, KLine, LinkError


def observation(args, kind, value, unit="", *, timestamp=None, **details):
    return {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "machine": args.machine,
        "kind": kind,
        "value": value,
        "unit": unit,
        "source": "vw-t4-kw1281",
        "context": args.context,
        "simulated": args.command == "demo",
        "details": details,
    }


def identification_record(args, lines, keywords):
    part = part_number(lines)
    return observation(
        args, "ecu_identification", part or lines[0],
        address="01", protocol="KW1281", baud=args.baud,
        keywords=" ".join(f"{byte:02X}" for byte in keywords),
        part_number=part, identification=lines,
    )


def fault_records(args, part, status, faults):
    yield observation(
        args, "ecu_fault_memory", str(len(faults)) if status == "read" else "unavailable",
        ecu_part_number=part, status=status,
    )
    for fault in faults:
        yield observation(
            args, "ecu_fault_code", fault["code"], ecu_part_number=part,
            status_hex=fault["status_hex"],
        )


def measurement_records(args, part, block, sample):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    for name, value, unit, details in group_observations(block, args.group, part):
        yield observation(
            args, name, value, unit, timestamp=timestamp, ecu_part_number=part, sample=sample,
            **details,
        )


def demo(args, records):
    args.group = 1
    args.baud = 9600
    ident = identification_record(args, ["074906021F", "SYNTHETIC DEMO"], (0x01, 0x8A))
    records.append(ident)
    part = ident["value"]
    records.extend(fault_records(args, part, "read", []))
    block = Block(1, MEASURED, bytes.fromhex("01 14 C3 27 08 A0 15 64 10 05 0A B5"))
    records.extend(measurement_records(args, part, block, 1))


def serial_support():
    try:
        import serial
        from serial.tools import list_ports
    except ImportError as exc:
        raise LinkError("Install pyserial using tools/t4/requirements.txt.") from exc
    return serial, list_ports


def ports():
    _, list_ports = serial_support()
    for port in sorted(list_ports.comports()):
        if port.vid is not None and port.pid is not None:
            print(f"{port.device}  {port.vid:04x}:{port.pid:04x}  {port.description}")


def capture(args, records):
    serial, list_ports = serial_support()
    path = str(Path(args.port).resolve())
    if not any(port.device == path and port.vid == 0x0403 for port in list_ports.comports()):
        raise LinkError(f"{path} was not detected as FTDI. Run 'ports' and check the cable.")
    port = serial.Serial(
        baudrate=args.baud, timeout=0.75, write_timeout=0.5, exclusive=True,
        bytesize=8, parity="N", stopbits=1, xonxoff=False, rtscts=False, dsrdtr=False,
    )
    port.port = path
    port.dtr = False
    port.rts = False
    with port:
        session = EngineSession(KLine(port, args.byte_delay_ms))
        lines = session.connect()
        ident = identification_record(args, lines, session.keywords)
        records.append(ident)
        part = ident["details"]["part_number"]

        if args.command == "faults":
            status, faults = session.read_faults()
            records.extend(fault_records(args, part, status, faults))
        elif args.command == "log":
            for sample in range(1, args.count + 1):
                block = session.read_group(args.group)
                records.extend(measurement_records(args, part, block, sample))
                if block.title in (ACK, NAK):
                    break
        # Send the end block only after a complete exchange. After link loss
        # or Ctrl-C mid-block the port closes and the ECU session times out.
        session.close()


def count_argument(value):
    count = int(value)
    if not 1 <= count <= 300:
        raise argparse.ArgumentTypeError("count must be between 1 and 300")
    return count


def arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ports", help="List USB serial devices and their USB IDs")
    for name, help_text in (
        ("demo", "Emit a labelled synthetic capture, with no cable or dependencies"),
        ("identify", "Read the engine controller identification"),
        ("faults", "Read stored engine fault codes"),
        ("log", "Log one measuring block"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--machine", default="t4-demo" if name == "demo" else "t4")
        command.add_argument("--context", default="")
        command.add_argument("--output", type=Path, help="Append JSONL here instead of printing it")
        if name != "demo":
            command.add_argument("--port", required=True, help="FTDI USB serial device path")
            command.add_argument("--baud", type=int, choices=(4800, 9600, 10400), default=9600)
            command.add_argument("--byte-delay-ms", type=int, choices=range(2, 11), default=5)
        if name == "log":
            command.add_argument("--group", type=int, choices=ALLOWED_GROUPS, default=1)
            command.add_argument("--count", type=count_argument, default=1)
    return parser.parse_args(argv)


def append_records(output, records):
    for record in records:
        output.write(json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n")
    output.flush()


def run(args, output):
    records = []
    try:
        if args.command == "demo":
            demo(args, records)
        else:
            capture(args, records)
    finally:
        # Keep completed observations if the connection drops. Disk/terminal
        # output happens after acquisition so it cannot slow the handshake.
        append_records(output, records)


def main(argv=None):
    args = arguments(argv)
    try:
        if args.command == "ports":
            ports()
        elif args.output is None:
            run(args, sys.stdout)
        else:
            path = args.output.expanduser()
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8") as output:
                run(args, output)
    except (OSError, LinkError) as exc:
        print(f"Caretaker T4: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Caretaker T4: interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
