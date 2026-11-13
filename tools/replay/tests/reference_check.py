#!/usr/bin/env python3
"""Independent standard-library checks on the Rust demo's emitted JSONL."""
import json
import sys
from pathlib import Path

root, out = map(Path, sys.argv[1:3])
fixtures = root / "tools" / "replay" / "fixtures"

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

python_t4 = rows(out / "t4-python.jsonl")
rust_t4 = rows(out / "t4-replayed.jsonl")
assert rust_t4 == python_t4, "Rust changed the existing T4 observations"
assert len(rust_t4) == 6 and all(row["simulated"] for row in rust_t4)

capture = {line.split(",")[0]: line.split(",")[2]
           for line in (fixtures / "can-holdout.csv").read_text().splitlines()[1:]}
can = rows(out / "can-holdout.jsonl")
physical = [row for row in can if row["kind"] == "vehicle_speed"]
assert len(physical) == len(capture) == 30
for row in physical:
    raw = int.from_bytes(bytes.fromhex(capture[row["timestamp"]])[:2], "little")
    assert row["details"]["raw_hex"] == capture[row["timestamp"]]
    assert row["details"]["raw_value"] == raw
    assert abs(float(row["value"]) - raw * 0.01) < 1e-9
    assert row["unit"] == "km/h" and row["simulated"] is True
assert can[-1]["kind"] == "decoder_verification" and can[-1]["value"] == "PASS"

wrong = rows(out / "can-wrong-match.jsonl")
assert not any(row["kind"] == "vehicle_speed" for row in wrong)
assert wrong[-1]["value"] == "UNCONFIRMED"
assert all(row["simulated"] for row in wrong)
print("Independent Python check: PASS (T4 equality, 30 CAN decodes, raw wrong-match containment)")
