"""Human-readable descriptions for RAMSES message types (UI / API)."""

from __future__ import annotations

from typing import Optional

# Keyed by ramses_tx code_name (lowercase), matching message_code_counts.code_name
_DESCRIPTIONS: dict[str, str] = {
    "temperature": (
        "Zone or device temperature report (30C9). Controller or TRV broadcasts "
        "current sensed temperature per zone or for a single device."
    ),
    "setpoint": (
        "Heating/cooling setpoint (22D9). Target temperature the zone or device "
        "is trying to reach."
    ),
    "setpoint_now": (
        "Current and next scheduled setpoint windows (2349). Shows immediate "
        "setpoint and upcoming programme steps."
    ),
    "setpoint_bounds": (
        "Min/max setpoint limits (2360) allowed for a zone or device."
    ),
    "zone_mode": (
        "Zone operating mode (2E04): permanent override, follow schedule, eco, "
        "off, etc."
    ),
    "zone_name": (
        "Human-readable zone label (0004), e.g. room names shown on the controller."
    ),
    "zone_devices": (
        "Lists devices bound to a zone (000C): TRVs, sensors, and their roles."
    ),
    "zone_params": (
        "Zone configuration (000A): limits, offsets, and related parameters."
    ),
    "system_zones": (
        "Summary of which zones exist on the system (0006)."
    ),
    "system_mode": (
        "Global heating/DHW mode (2E04 controller scope): heating off, auto, etc."
    ),
    "system_sync": (
        "Periodic system synchronisation (1F09). Devices align timing with the controller."
    ),
    "system_fault": (
        "Controller fault log entry (0418). Historical faults and restores."
    ),
    "schedule_version": (
        "Version stamp for schedules (0005); changes when programmes are edited."
    ),
    "zone_schedule": (
        "Weekly heating schedule for a zone (0404)."
    ),
    "heat_demand": (
        "Heat demand percentage (3150) from controller or zone toward boiler/relay."
    ),
    "relay_demand": (
        "On/off heat demand to switching relay (0008)."
    ),
    "relay_failsafe": (
        "Relay failsafe / backup behaviour (0009)."
    ),
    "boiler_setpoint": (
        "Flow / boiler target temperature (22D9 boiler context)."
    ),
    "boiler_output": (
        "Boiler flow temperature or output metric (3220)."
    ),
    "boiler_return": (
        "Boiler return temperature (3221)."
    ),
    "dhw_temp": (
        "Hot water cylinder or flow temperature (1260)."
    ),
    "dhw_params": (
        "DHW setpoint and timing parameters (10A0)."
    ),
    "dhw_mode": (
        "Domestic hot water mode (1F41): on, off, auto."
    ),
    "dhw_flow_rate": (
        "DHW flow rate where reported (12A0)."
    ),
    "device_battery": (
        "Wireless device battery level (1060)."
    ),
    "device_info": (
        "Device model / firmware style information (10E0)."
    ),
    "device_id": (
        "Device addressing or identity exchange (0010)."
    ),
    "outdoor_temp": (
        "Outside air temperature from external sensor (1290)."
    ),
    "outdoor_sensor": (
        "Outdoor sensor payload (0002)."
    ),
    "outdoor_humidity": (
        "Outside humidity (12A0 / outdoor context)."
    ),
    "displayed_temp": (
        "Temperature shown on a device display (31D9), may differ from sensor."
    ),
    "window_state": (
        "Open-window detection (12B0) for fast shutoff."
    ),
    "datetime": (
        "Controller date and time broadcast (313F); devices sync clocks."
    ),
    "programme_config": (
        "High-level programme configuration (2301)."
    ),
    "programme_status": (
        "Current programme / holiday state (22F1)."
    ),
    "programme_scheme": (
        "Which schedule scheme applies (22F4 context)."
    ),
    "mixvalve_params": (
        "Mixing valve parameters (0B04)."
    ),
    "max_ch_setpoint": (
        "Maximum central heating flow setpoint (1086)."
    ),
    "ch_pressure": (
        "Central heating circuit pressure (12F0)."
    ),
    "filter_change": (
        "Filter maintenance / change reminder (10D6)."
    ),
    "tpi_params": (
        "TPI (time-proportional) heating control parameters (10E2)."
    ),
    "rf_bind": (
        "RF binding / pairing handshake (1FC0)."
    ),
    "rf_check": (
        "RF link check (0008 in some contexts) or signal quality."
    ),
    "actuator_state": (
        "TRV actuator position or valve state (3EF0)."
    ),
    "actuator_sync": (
        "Actuator synchronisation with controller (3B00)."
    ),
    "actuator_cycle": (
        "Actuator duty or cycle information (3EF1)."
    ),
    "ufc_demand": (
        "Underfloor or UFH demand (3150 variant)."
    ),
    "fan_state": (
        "Fan unit state (31D9 fan)."
    ),
    "fan_mode": (
        "Fan speed or mode (22F7)."
    ),
    "fan_demand": (
        "Ventilation demand (31D9 demand)."
    ),
    "hvac_state": (
        "HVAC mode state (32C0)."
    ),
    "presence_detect": (
        "Occupancy / presence (2E05)."
    ),
    "opentherm_msg": (
        "OpenTherm bridge traffic (3220/3221 related)."
    ),
    "opentherm_sync": (
        "OpenTherm synchronisation (1FD0)."
    ),
    "puzzle_packet": (
        "Gateway signature / diagnostic (7FFF). Used at startup."
    ),
    "language": (
        "Controller language / locale (0005 context)."
    ),
    "co2_level": (
        "CO₂ level where supported (1298)."
    ),
    "indoor_humidity": (
        "Indoor humidity (12B4)."
    ),
    "air_quality": (
        "Air quality index (12B8)."
    ),
    "rf_unknown": (
        "Unclassified short RF frame (0000)."
    ),
}


def description_for_message_type(
    code: Optional[str], code_name: Optional[str]
) -> str:
    """Return a paragraph describing this RAMSES message type for the UI."""
    name = (code_name or "").strip().lower()
    code_u = (code or "").strip().upper()

    if name and name in _DESCRIPTIONS:
        return _DESCRIPTIONS[name]

    if name.startswith("message_"):
        return (
            f"RAMSES payload type “{name}” (code {code_u or '—'}). "
            "See ramses_rf CODES_SCHEMA for full parser details."
        )
    if name.startswith("unknown_"):
        return (
            f"Partially documented RAMSES code {code_u or '—'} ({name}). "
            "Behaviour may be inferred from ramses_rf parsers."
        )
    if name:
        return (
            f"Message type “{name}” (code {code_u or '—'}). "
            "No extended blurb in this exporter; check ramses_rf for payload shape."
        )
    if code_u:
        return (
            f"RAMSES message code {code_u}. Type name not recorded yet; "
            "often seen on first packets before schema labels the code."
        )
    return "Unknown message type (no code or name stored)."
