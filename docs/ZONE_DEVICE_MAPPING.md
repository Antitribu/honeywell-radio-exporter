# Zone-Device Mapping with ramses_zone_info

## Overview

The `ramses_zone_info` metric now includes comprehensive zone-to-device mappings extracted from RAMSES RF `zone_devices` messages. This allows Grafana dashboards to easily label devices with their zone names and understand device roles.

## Metric Structure

```
ramses_zone_info{zone_idx="02", zone_name="Kitchen", device_role="zone_actuator", device_id="04:122498"} 1.0
```

### Labels

- **zone_idx**: Zone index (e.g., "00", "01", "02", "08", "0A")
- **zone_name**: Human-readable zone name (e.g., "Kitchen", "Living Room", "Master Bedroom")
- **device_role**: Role of the device in the zone:
  - `zone_actuator`: Zone valve actuator
  - `zone_sensor`: Zone temperature sensor
  - `rad_actuator`: Radiator valve actuator (TRV)
  - `appliance_control`: Boiler/appliance control
  - `hotwater_valve`: Hot water valve
  - `dhw_sensor`: Domestic hot water sensor
  - `heating_valve`: Heating system valve
- **device_id**: RAMSES RF device identifier (e.g., "04:122498")

## Usage in Grafana

### Example 1: Join Zone Names to Device Metrics

Label device temperature readings with zone names:

```promql
ramses_device_temperature_celsius
  * on(device_id) group_left(zone_name, zone_idx)
  ramses_zone_info{device_role="zone_sensor"}
```

This query joins temperature readings with zone information, adding `zone_name` and `zone_idx` labels to each temperature metric.

### Example 2: Show Zone Actuator States

Display which zone actuators are active with their zone names:

```promql
ramses_heat_demand
  * on(device_id) group_left(zone_name)
  ramses_zone_info{device_role="zone_actuator"}
```

### Example 3: Filter by Device Role

Get only radiator valve actuators (TRVs) with their zones:

```promql
ramses_zone_info{device_role="rad_actuator"}
```

### Example 4: Panel Variable for Zone Selection

Create a dashboard variable to select zones:

**Variable name:** `zone`  
**Type:** Query  
**Query:**
```promql
label_values(ramses_zone_info, zone_name)
```

Then use it in your queries:
```promql
ramses_device_temperature_celsius
  * on(device_id) group_left(zone_name)
  ramses_zone_info{zone_name="$zone", device_role="zone_sensor"}
```

### Example 5: Table View of All Zones and Devices

Display a complete mapping table:

```promql
ramses_zone_info
```

Format as **Table** in Grafana and show columns:
- zone_idx
- zone_name
- device_role
- device_id

## How It Works

The exporter monitors RAMSES RF messages:

1. **Zone Names**: Extracted from `zone_name` messages (code 0004)
2. **Device Mappings**: Extracted from `zone_devices` messages (code 000C)
3. **Combined Metric**: When both are available, creates `ramses_zone_info` entries combining zone information with device roles

## Example Data

From the sample data, here are some zone-device mappings:

```
Kitchen (02):
  - 04:122498: zone_actuator, zone_sensor, rad_actuator

Master Bedroom (08):
  - 04:122296: zone_actuator, zone_sensor, rad_actuator

Office (0A):
  - 04:122292: zone_actuator, zone_sensor, rad_actuator

Living Room (01):
  - 04:122504: zone_sensor
```

## Benefits

1. **Simplified Queries**: No need to manually map device IDs to zones
2. **Dynamic Discovery**: Automatically learns zone-device relationships from RF messages
3. **Multi-Role Support**: Same device can have multiple roles (e.g., both sensor and actuator)
4. **Grafana-Friendly**: Uses standard Prometheus labels for easy joining and filtering
5. **Self-Documenting**: Zone names appear directly in metrics, making dashboards more readable

## Notes

- The metric value is always `1.0` - it's an info-style metric used for label joining
- A zone may have multiple devices with different roles
- A device may appear in multiple zones (though this is rare in typical RAMSES setups)
- If zone name is not yet discovered, the zone won't appear in metrics (prevents clutter)
- Empty device lists (no devices for a role) are tracked internally but don't create metric entries

