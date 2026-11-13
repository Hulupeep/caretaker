# Caretaker

An open-source experiment in helping people keep old machines useful for longer.

A caretaker learns the history of an individual machine, gathers observations from people and sensors, helps investigate changes, and follows a problem through to a recorded outcome. The first use case is Colm's planned 1996 VW T4 2.5 TDI. The actual van, ECU, sensors and measurements have not yet been verified.

## Inspiration

[MZULALI/xj-scanner](https://github.com/MZULALI/xj-scanner) connects an AI agent to a 1990s Jeep's engine computer for diagnosis. This project is inspired by that work, but explores a wider problem: persistent care for an individual machine using electronics, photographs, thermal images, sound, human observations, maintenance records and, eventually, other sensors and physical assistance. We have not copied its code; it is GPL-3.0. Check third-party licences before incorporating code.

## First journey

Record a T4's identity and service history; collect a dated observation or diagnostic export; create a grounded caretaker brief showing evidence, unknowns and a recommended next check; record what a mechanic or owner found. Start with real information and manual inputs. See [first experiment](experiments/001-t4-caretaker.md).

No T4 is assumed purchased and no actual readings are included. No automated sensor analysis, ECU support or predictive accuracy is claimed.

## Contents

- [Product hypothesis](docs/product-hypothesis.md)
- [Roadmap and gates](docs/roadmap.md)
- [First experiment and acceptance criteria](experiments/001-t4-caretaker.md)
- [Machine record template](examples/machine-record.md)
- [Contribution guide](CONTRIBUTING.md)

## Design principles

Evidence before diagnosis. Label unknowns. Preserve the source and date of observations. A change in a measurement is a lead, not proof of a fault. An unobserved component is unknown, not healthy. Record failed predictions as well as successful ones. Keep the owner in control of their data. Early prototypes are read-only with respect to vehicle systems.

## Licence

MIT for original repository material; see LICENSE. Third-party code and data retain their own licences.
