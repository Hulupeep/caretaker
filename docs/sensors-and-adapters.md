# Give any machine senses

A machine doesn't need an ECU to have a caretaker. Start with the owner's question, then choose the least intrusive observation that could answer it.

| Signal | Candidate method | Placement idea | Starting point |
| --- | --- | --- | --- |
| Visual | Phone or fixed camera | Repeat the same views of accessible housings, hoses and the ground. | Parked photo walk-around. |
| Temperature | Contact probe or thermal image | Same accessible painted surface or manufacturer-approved measurement point. | Repeat at the same operating state and ambient conditions. |
| Electrical | Meter or appropriately protected logger | Battery supply or approved diagnostic point. | Identify electrical system and measure with a competent person. |
| Sound | Phone or microphone | Same safe position and operating mode. | Capture a short baseline with context and permission. |
| Vibration | Suitable accelerometer | Secure, known position on a housing; never near moving parts. | Decide what frequency range and mounting the question needs. |
| Pressure | Correctly rated transducer and approved test connection. | Model-specific oil, fuel or hydraulic test point, chosen by a specialist. | First confirm the circuit, instrument range and test procedure; this is not a generic installation. |
| Existing electronics | Compatible scanner / adapter | Manufacturer diagnostic connector. | Identify protocol and model; prove readings against a known tool. |

Compare like with like: date, sensor, placement, operating state, temperature, load and units. An unusual signal is a question, not a diagnosis. A missing observation is unknown. Sensor and machine conditions vary; no generic alert thresholds are supplied.

## The adapter idea

An adapter turns an observation into a common record while preserving provenance. It might read a diagnostic log, a sensor file, a phone image, or a human-entered note. The first contract and example are in [adapter contract](adapter-contract.md). See [1970s tractor](../machines/tractors/1970s-tractor.md), [JCB-type plant](../machines/plant/jcb-backhoe-concept.md) and [T4](../experiments/001-t4-caretaker.md).

## Why not rewrite the Jeep scanner in Rust?

[MZULALI/xj-scanner](https://github.com/MZULALI/xj-scanner) already tackles a specific Jeep computer. Use it as inspiration and work with the community. First establish a real need and compatible source/licence. A Rust rewrite of the same protocol is a possible contributor experiment, but would not by itself add T4, tractor or hydraulic coverage. Keep its GPL-3.0 obligations in mind before copying or adapting code. A future adapter can ingest an authorised export without pretending the Jeep protocol is universal.
