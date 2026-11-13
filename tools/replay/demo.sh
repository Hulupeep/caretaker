#!/bin/sh
# Run from any directory with a Rust toolchain and Python 3. No network needed.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:-"$ROOT/target/caretaker-replay-demo"}
mkdir -p "$OUT"
python3 "$ROOT/tools/t4/t4_logger.py" demo > "$OUT/t4-python.jsonl"
cargo run --quiet --manifest-path "$ROOT/tools/replay/Cargo.toml" -- \
  demo --fixtures "$ROOT/tools/replay/fixtures" --t4-input "$OUT/t4-python.jsonl" --output "$OUT"
python3 "$ROOT/tools/replay/tests/reference_check.py" "$ROOT" "$OUT"
printf '\nDemo JSONL and verification records: %s\n' "$OUT"
