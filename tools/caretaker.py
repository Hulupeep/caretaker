#!/usr/bin/env python3
"""Minimal local observation log; stdlib only. It does not diagnose faults."""
import argparse
import json
from datetime import datetime
from pathlib import Path


def add(args):
    timestamp = args.time or datetime.now().astimezone().isoformat(timespec='seconds')
    try:
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if parsed.utcoffset() is None:
            raise ValueError('timezone required')
    except ValueError as exc:
        raise SystemExit(f'Invalid time: use ISO 8601 with timezone ({exc})')
    event = {'timestamp': timestamp, 'machine': args.machine, 'kind': args.kind,
             'value': args.value, 'unit': args.unit, 'source': args.source,
             'context': args.context, 'simulated': args.simulated}
    with Path(args.file).open('a', encoding='utf-8') as out:
        out.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
    print('Observation saved.')


def show(args):
    path = Path(args.file)
    if not path.exists():
        print('No observations yet.')
        return
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if args.machine and item.get('machine') != args.machine:
                continue
            print(json.dumps(item, ensure_ascii=False))
        except (json.JSONDecodeError, AttributeError):
            raise SystemExit(f'Invalid observation at line {number} in {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('add', help='Record one observation')
    p.add_argument('--file', required=True, help='Local JSONL file (keep private)')
    for name in ('machine', 'kind', 'value', 'source'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--unit', default='')
    p.add_argument('--context', default='')
    p.add_argument('--time', help='ISO 8601 with timezone; defaults to current local time')
    p.add_argument('--simulated', action='store_true')
    p.set_defaults(func=add)
    p = sub.add_parser('show', help='Print observations, one JSON object per line')
    p.add_argument('--file', required=True)
    p.add_argument('--machine')
    p.set_defaults(func=show)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
