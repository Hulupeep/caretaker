# Caretaker: visual roadmap

**Imagine never having to buy another car.** Imagine a workshop that knows your machines, keeps them working and brings them back to life—while you sleep. This is the journey we want to take together.

This is a starting map for an open-source experiment. The dates are illustrative: we'll redraw them as people contribute, experiments succeed and we learn what it takes to build the workshop.

## First 12 months: establish the care loop

```mermaid
gantt
    title First year — proposed experiments
    dateFormat YYYY-MM-DD
    axisFormat %b %Y
    section One machine
    Real T4 or candidate record           :a1, 2026-11-16, 2027-01-15
    One verified care or repair loop      :a2, 2026-12-01, 2027-02-28
    section Learning and product
    Owner and repairer interviews         :b1, 2026-11-16, 2027-02-28
    Test a paid pilot offer                :b2, 2027-01-01, 2027-03-31
    Machine record and evidence prototype :b3, 2027-01-01, 2027-05-31
    section Observation and repair
    Evaluate one useful sensor            :c1, 2027-03-01, 2027-08-31
    Human-led household repair experiment  :c2, 2027-02-01, 2027-08-31
    Review evidence and choose next stage :milestone, 2027-11-01, 0d
```

**First gate:** a real observation leads to an understandable action, and an owner or repairer records the actual outcome. If no T4 is available, use an identified candidate or a real household object; do not invent measurements.

**Commercial gate:** put a real case and paid-pilot offer in front of prospective owners or repair specialists. Before substantial product investment, seek a concrete commitment or payment. No paid signal means park the commercial build or continue as a personal experiment.

## Long view: from caretaker to workshop

```mermaid
gantt
    title Long-term ambition — illustrative, highly uncertain
    dateFormat YYYY-MM-DD
    axisFormat %Y
    section Understand
    Machine records and care loops        :l1, 2026-11-01, 2028-01-01
    Validated observation and sensors     :l2, 2027-03-01, 2029-01-01
    section Repair with people
    Human-led repairs and outcomes        :l3, 2027-02-01, 2029-07-01
    section Workshop
    Supervised constrained robot tasks    :l4, 2028-01-01, 2031-01-01
    Supervised restoration cell trials    :l5, 2030-01-01, 2034-01-01
    section Long-term goal
    Bounded overnight task trials        :l6, 2032-01-01, 2036-01-01
    Broader lifetime workshop research    :l7, 2034-01-01, 2040-01-01
```

The long view is an invitation to experiment, not a fixed delivery schedule. Different people can explore different pieces in parallel; the evidence from each experiment helps shape what comes next.

| Transition | Evidence needed before advancing |
| --- | --- |
| Advice to observation | Repeatable, contextualised measurements; comparisons against known results; false alarms and missed detections recorded. |
| Observation to repair | A bounded repair plan, competent human involvement, a documented independent check and a recorded outcome. |
| Human repair to robot task | Appropriate fixtures and safeguards, supervised repeatability, failure recovery, emergency stops and independent review of the actual workspace and task. |
| Supervised to overnight | Task-specific evidence, guarded access, loss-of-power and fault handling, fire and environmental controls, and independent safety review. A remote camera alone is insufficient. |
| One object to many | Evidence for each new object, procedure, tool and hazard; qualified specialists and inspection where needed. |

## What a successful morning could look like

> “The bicycle was inspected, cleaned and the approved part fitted. Here are the before-and-after images and test results. The brakes still need a qualified check before use. I stopped work on the mixer because the part didn't match.”

That's the kind of morning we're working towards. Each experiment, repaired object and contribution brings the workshop a little closer.

[Read the detailed roadmap](roadmap.md) · [Explore the first T4 experiment](../experiments/001-t4-caretaker.md)
