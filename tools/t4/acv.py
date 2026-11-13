"""Provisional measuring-block map for the early 75 kW T4 ACV ECU."""

import re
from collections.abc import Iterator

from kw1281 import ACK, MEASURED, NAK, Block

PROFILE_PART = "074906021F"
PART_PATTERN = re.compile(r"^([0-9]{3}\s*[0-9]{3}\s*[0-9]{3}\s*[A-Z]{0,2})(?=\s|$)")
# (group, field) -> (name, expected KW1281 value type, units).
# Even on this part number, compare the first capture with a workshop tool.
FIELDS = {
    (1, 1): ("engine_rpm", 1, "rpm"),
    (1, 2): ("injection_quantity", 39, "mg/stroke"),
    (1, 3): ("quantity_adjuster_feedback_voltage", 21, "V"),
    (1, 4): ("coolant_temperature", 5, "°C"),
    (3, 1): ("engine_rpm", 1, "rpm"),
    (3, 2): ("air_mass_requested", 49, "mg/stroke"),
    (3, 3): ("air_mass_actual", 49, "mg/stroke"),
    (3, 4): ("egr_duty_cycle", 23, "%"),
    (7, 1): ("fuel_temperature", 5, "°C"),
    (7, 3): ("intake_air_temperature", 5, "°C"),
    (7, 4): ("coolant_temperature", 5, "°C"),
    (11, 1): ("engine_rpm", 1, "rpm"),
    (11, 2): ("charge_pressure_requested_absolute", 18, "mbar"),
    (11, 3): ("charge_pressure_actual_absolute", 18, "mbar"),
    (11, 4): ("charge_pressure_valve_duty_cycle", 23, "%"),
    (12, 3): ("ecu_supply_voltage", 6, "V"),
    (12, 4): ("coolant_temperature", 5, "°C"),
}
PRODUCT_DIVISORS = {1: 5, 6: 1000, 18: 25, 21: 1000, 23: 256, 39: 256, 49: 40}


def part_number(identification: list[str]) -> str | None:
    if identification and (match := PART_PATTERN.match(identification[0].upper())):
        return "".join(match[1].split())
    return None


def group_observations(
    block: Block, group: int, part: str | None
) -> Iterator[tuple[str, str, str, dict]]:
    prefix = f"kw1281_group_{group:03d}"
    details = {"group": group, "reply_title_hex": f"{block.title:02X}"}
    if block.title in (ACK, NAK):
        yield prefix, "unavailable", "", details
        return
    if block.title != MEASURED:
        yield prefix, block.data.hex(" ").upper(), "", {**details, "decode": "raw"}
        return

    for offset in range(0, len(block.data), 3):
        field = offset // 3 + 1
        raw = block.data[offset:offset + 3]
        type_id, first, second = raw
        evidence = {**details, "field": field, "raw_hex": raw.hex(" ").upper()}
        mapping = FIELDS.get((group, field)) if part == PROFILE_PART else None
        if mapping is None or mapping[1] != type_id:
            if mapping is not None:
                evidence["expected_type"] = mapping[1]
            yield f"{prefix}_field_{field}", evidence["raw_hex"], "", {**evidence, "decode": "raw"}
            continue
        name, _, unit = mapping
        if type_id == 5:
            value = first * (second - 100) / 10
        else:
            value = first * second / PRODUCT_DIVISORS[type_id]
        formatted = f"{value:.3f}".rstrip("0").rstrip(".")
        yield name, formatted, unit, {**evidence, "decode": "acv-provisional"}
