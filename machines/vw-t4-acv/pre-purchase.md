# Take Caretaker to a VW T4 viewing

You arrive with your laptop, a USB K-line lead and a phone. While the van is still cold, Caretaker reads the engine controller and starts an inspection record. The passenger collects a short log once the van is warm. Park, check the readings again, add the service invoices and what the lift inspection found, and leave with a report you can discuss before handing over money.

## Before travelling

- Confirm the ACV engine code and get a photo of the diagnostic socket. Pack the [FTDI KKL cable](README.md#parts) and any socket adapter the photo calls for. Set up the logger and test the cable's Linux USB connection at home. Use the battery-powered laptop for the viewing. The Pi can do the same recording if you want a dedicated logger later.
- Ask the seller to leave the van cold and send photos of the dated belt and water-pump invoices and the latest inspection report. Ask for a test drive and a nearby lift inspection if the van looks promising. [ADAC used-car checklist](https://www.adac.de/rund-ums-fahrzeug/auto-kaufen-verkaufen/gebrauchtwagenkauf/gebrauchtwagen-kaufen/) · [ADAC inspection centres](https://www.adac.de/rund-ums-fahrzeug/reparatur-pflege-wartung/reparatur-rueckruf/pruefdienste/)
- Take a torch and a phone. Photograph the whole area for orientation, then take a close-up. Record where each picture was taken. Keep each van's photos, report and raw log together locally.

> Bitte lassen Sie den Motor vor der Besichtigung kalt. Ich würde gern bei der Probefahrt die Motordaten auslesen. Können Sie mir die Rechnungen für Zahnriemen und Wasserpumpe sowie den letzten HU-Bericht zeigen? Wäre bei Interesse eine Besichtigung auf der Hebebühne möglich?

## At the van

| When | From the engine ECU | From you or the mechanic |
| --- | --- | --- |
| **Before starting** | Identify the ECU, read stored engine faults and, if supported, read coolant, intake and fuel temperature. | Record ambient temperature and whether the engine really is cold. Photograph visible seams, wheel arches, sills and the windscreen surround. Match invoice dates and mileages to the van. |
| **First start** | Capture RPM and coolant once the engine is running. The logger may lose its link while the starter is turning. | Observe how it cranks, how quickly it starts and whether smoke, rough idle or warning lights persist. |
| **Normal drive** | With the engine warm, have the passenger record group `011` during a short segment. It pairs requested and actual charge pressure at the same engine speed. | Note when it hesitates, feels weak or makes an unusual sound. Record the driving conditions once parked. The seller or driver can decline the segment. |
| **Parked, after the drive** | Read warm idle, coolant and, if supported, ECU supply voltage and requested and actual air mass at idle. Read engine faults again with the ignition on after stopping. | Observe the hot restart and look for fresh fluid around the van. Ask a mechanic to assess sills and jacking points, brake pipes, suspension mounts and leaks on a lift. |

The supported group labels vary by ECU revision. Compare the first RPM and coolant readings with a workshop scanner at stable idle before relying on them. Charge pressure is reported as absolute pressure. For a formal boost or air-mass test, the workshop manual supplies the conditions and interpretation. [VW workshop manual contents, repair groups 01 and 23](https://www.kfz-verlag.de/1990-2003-diesel-injection-glow-plug-system-workshop-ebook/p-22770.html?action=download&datei=en-ebook-vw-bus-t4-0293.pdf&filename=en-ebook-vw-bus-t4-0293.pdf) · [Ross-Tech on measuring blocks](https://register.ross-tech.com/vcds-lite/manual/measblocks.html)

### What each piece of evidence can tell you

| Question | What to collect |
| --- | --- |
| Why did it feel weak on that hill? | Compare the requested and actual pressure trace from the same samples. If there is a repeated gap under comparable load, ask the mechanic to check the charge-air plumbing and boost control. Keep both the driver's observation and the raw trace. |
| Is a battery cable or ground strap weak? | The ECU supply reading can raise the question. A battery-post measurement and a voltage-drop test across the circuit under load can narrow it down. [Fluke on voltage-drop diagnosis](https://www.fluke.com/en-us/learn/blog/automotive/electrical-automotive-troubleshooting) |
| Is it rusted underneath? | Photograph visible clues. Record the mechanic's assessment of material loss, repaired areas and hidden or coated areas on the lift. A clean scan leaves this open. [ADAC T4 used-vehicle guide](https://assets.adac.de/image/upload/Autodatenbank/GWInfo/gw0074-vw-t4-multivan-1990-2003-bericht.pdf) · [DEKRA body and mechanical checks](https://www.dekra.de/de/dekra-siegel-gebrauchtfahrzeuge/) |
| Has the belt work been done? | Use the dated invoice and mileage, with the specific parts and work itemised. Mark missing history as unresolved. |
| Can it run a test while parked? | Caretaker can run the read sequence below. A compatible workshop scanner can also run documented actuator tests on the stationary van where the particular controller supports them. These can show whether a commanded part responds, and belong with the manual and the person operating the tool. [Ross-Tech on output tests](https://register.ross-tech.com/vcds-lite/manual/output.html) |

## Run the inspection

From the repository root, try it at home with a synthetic session. Choose a new file each time you start a viewing or demo.

```sh
python3 tools/t4/t4_inspect.py demo --session t4-demo-viewing.jsonl
```

At the viewing, follow the [USB and Python setup](README.md#run-the-logger) first. Use the actual port reported by the cable.

```sh
T4_PORT=/dev/ttyUSB0
.venv-t4/bin/python tools/t4/t4_inspect.py run --port "$T4_PORT" \
  --session t4-viewing.jsonl --drive-seconds 180
```

The programme asks before each capture. Press Enter to skip an unavailable stage and carry on with the inspection. The road capture uses one measuring group for a timed interval after connection. The report shows how many paired readings it obtained and their time span. If the cable disconnects, the record keeps completed observations and the reported error. If you end the viewing early, you can still regenerate the report from what was saved. Group labels remain provisional until checked against the actual ECU.

After the mechanic's inspection, append the actual lift finding and regenerate a Markdown report. Repeat `note` with `--kind service`, `body` or `road_feel` if more evidence arrives. Use your own finding in place of the sample text.

```sh
python3 tools/t4/t4_inspect.py note --session t4-viewing.jsonl --kind lift \
  'Lift report saved in the local viewing folder.'
python3 tools/t4/t4_inspect.py report --session t4-viewing.jsonl > t4-report.md
```

The report lists the cold and warm observations, fault reads, road samples, body notes and what is pending. The software produces the report locally. For an agent review, point Claude Code or Codex to the log, the report and only the photos or paperwork you want it to see. Ask for the most important unresolved check and the evidence that would settle it. A weak or missing signal stays unknown. The report can guide a purchase discussion or a workshop check before an Ireland-to-Italy trip. It takes a confirmed mechanical inspection and service history to make that trip decision.
