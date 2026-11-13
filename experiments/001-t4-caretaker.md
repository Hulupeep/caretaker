# Experiment 001: One T4, one actionable care loop

## User story

As Colm, I want to understand what is known about a particular T4 and what to check next, so I can keep it working and have a useful conversation with a mechanic.

## Inputs

Actual vehicle identity if available, service records and one real observation: owner note, photo or existing scan. If there is no van, use an explicitly labelled prospective vehicle with real public information and leave unavailable fields unknown. Synthetic data may exercise the format but is never evidence of performance.

For an early ACV, use the [T4 diagnostic build](../machines/vw-t4-acv/README.md) to capture the engine ECU identity, faults and measuring blocks. Its first physical test uses a parked comparison with a workshop scanner.

## Procedure

1. Create a private copy of the machine record template. Record source and dates. Do not put identifying or location data into a public repository.
2. Add a genuine observation; describe when and under what conditions it was made.
3. Draft a brief with facts, plausible hypotheses, unknowns, urgency if supported, and one specific next check with a named human role.
4. A competent person performs or reviews the check; record what happened and whether the original interpretation was useful.
5. Show the anonymised result to a T4 specialist or owner and ask whether they would use or pay for this service.

## Acceptance criteria

- A reader can trace each factual claim to an observation, document or person and date.
- The brief separates observation from interpretation and explicitly states unknowns.
- The suggested check is practical, includes who could perform it and does not require unsafe user action.
- Actual check result is recorded, even if the hypothesis was wrong; no evidence means no claimed success.
- Nothing writes to vehicle controls; no customer or vehicle private data is published without consent.

## Failure cases

No real vehicle or check: experiment remains open. Contradictory or poor-quality data: flag it. No communication with ECU: use manual evidence and investigate compatibility separately. A sensor or model fails: mark it unavailable, never report all clear.
