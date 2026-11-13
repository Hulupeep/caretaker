# Adapter contract: proposal

**Status: draft, not implemented.** A machine adapter is a small bridge between an observation source and Caretaker's local record. Examples: manual entry, CSV import, a compatible sensor logger, or a vehicle scanner export.

## Journey

1. Identify machine and source without publishing private identifiers.
2. Collect an observation, its timestamp with timezone and operating context.
3. Preserve raw values, units, source and evidence reference; report unsupported, missing or invalid data explicitly.
4. Present observations to a person; retain simulated / real distinction.
5. Record a follow-up check and its actual outcome separately.

## Minimum fields

`timestamp`, `machine`, `kind`, `value`, `unit`, `source`, `context`, `simulated`. See the [local log](../tools/README.md) for the first simple implementation. `value` is currently a string; this is not a validated interchange standard.

## Invariants

- Do not silently invent readings, infer a healthy state from missing data or discard original units.
- Do not call a sensor value a diagnosis or introduce unverified thresholds.
- Read-only integrations first; physical or ECU actions require their own explicit design and review.
- Avoid sending data externally by default; private records must not be committed.
- Format and protocol compatibility are specific to each source and must be demonstrated.

## Acceptance criteria for a first CSV adapter

Given a documented CSV with timestamp, machine, kind, value, unit, source and context, import records into a private JSONL file without changing units. Reject invalid timestamps or missing required fields with row numbers; label sample data simulated. Import the same file twice without silent duplicate observations or explicitly report duplicates. Preserve source and report skipped/rejected rows. Verify with real exports only after obtaining consent.

A CSV adapter is a proposed next contribution; it has not been built.
