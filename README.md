# Caretaker

**Keep the machines you love alive.**

Caretaker is an open-source experiment in helping people understand, repair, restore and extend the lives of the things they own.

Our long-term vision is a workshop on your property where software agents, sensors, tools, people and eventually robots care for your machines. Leave an old bicycle, motorbike, boat component, 1950s Kenwood mixer or fridge in its care. One day, a robot might inspect and repair suitable items overnight, verify the work and leave you a clear report in the morning. When it cannot safely handle a job, it stops and brings in the right person.

We want “buy another one” to be a choice rather than the default. Longer useful lives can reduce waste and resource use, though the best environmental choice depends on the object and circumstances.

## Start with one T4

The first user is Colm and the first vehicle use case is his planned 1996 Volkswagen T4 2.5 TDI. The actual van, ECU, sensors and measurements have not yet been verified.

Record its history; collect a dated observation; produce a brief with evidence, unknowns and the next useful check; record what a mechanic or owner finds. A simple household object can be a parallel first physical-repair case. See the [first experiment](experiments/001-t4-caretaker.md).

This repository currently contains the product hypothesis and experiment plan. It does **not** yet implement vehicle diagnostics, sensor analysis, physical robotics or autonomous repair.

## Inspiration

[MZULALI/xj-scanner](https://github.com/MZULALI/xj-scanner) connects an AI agent to a 1990s Jeep's engine computer for diagnosis. Caretaker is inspired by that work and explores a broader, longer-lived relationship between people and machines: ongoing care informed by observations, records, people, many kinds of sensors and eventually physical repair.

We have not copied its code; xj-scanner is GPL-3.0. Check third-party licences before incorporating code.

## Where we're going

1. One machine record and one real care loop.
2. Evidence-based assistance and useful sensor observations.
3. Human-led repair and verified outcomes.
4. Narrow, supervised robotic work in a guarded workshop.
5. Carefully validated, bounded overnight tasks.
6. A lifetime caretaker for many kinds of objects.

Read the full [roadmap](docs/roadmap.md). These are stages of a hypothesis, not promises or a delivery schedule.

## Repository

- [Product hypothesis](docs/product-hypothesis.md)
- [Roadmap and gates](docs/roadmap.md)
- [First T4 experiment](experiments/001-t4-caretaker.md)
- [Machine record template](examples/machine-record.md)
- [Contribution guide](CONTRIBUTING.md)

## Principles

Evidence before diagnosis. Unknown is not healthy. Human and expert involvement where needed. Owner control of data and actions. Verify repairs and record failures. Gradually expand robot autonomy only after task-specific testing, safety controls and independent review. Never promise to detect every failure.

## Licence

MIT for original repository material; see LICENSE. Third-party code and data retain their own licences.
