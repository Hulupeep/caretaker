# First tool: observation log

A tiny local starting point for recording what we actually observe about a machine. It stores JSON Lines, one record per observation; it makes no diagnosis and does not connect to equipment. Python 3 is the only requirement.

```sh
python3 tools/caretaker.py add --file my-machine.jsonl --machine tractor-1 --kind battery_voltage --value 12.4 --unit V --source multimeter --context "engine off; example only" --simulated
python3 tools/caretaker.py show --file my-machine.jsonl --machine tractor-1
```

The example is simulated, not a recommended voltage or evidence of a working tractor. Use your own observations and remove `--simulated`. Add `--time 2026-11-13T10:00:00+00:00` to record when a past observation was made. Include operating conditions, placement and method in context. Values are strings to allow notes; any analysis must explicitly validate numeric values and units.

Keep your JSONL and machine identifiers private. The tool stores a local file; it does not upload, encrypt, enforce consent, validate readings or detect failures.

Next: agree a machine-readable observation contract, accept exports from real adapters and compare with a repeatable baseline—without pretending a measurement proves a diagnosis.
