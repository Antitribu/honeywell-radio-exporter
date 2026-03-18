# Zone-Device Mapping Enhancement - Changelog

## Summary

Extended the `ramses_zone_info` metric to include device-to-zone mappings from RAMSES RF `zone_devices` messages. This enables Grafana dashboards to easily label devices with their zone names and understand device roles within zones.

## Changes Made

### 1. Core Exporter Changes (`honeywell_radio_exporter/ramses_prometheus_exporter.py`)

#### Added Zone-Device Mapping Tracking
- Added `zone_devices_map` dictionary to track zone-to-device relationships
- Structure: `{zone_idx: {device_role: [device_ids]}}`

#### Enhanced `ramses_zone_info` Metric
**Before:**
```python
ramses_zone_info{zone_idx="02", zone_name="Kitchen"} 1.0
```

**After:**
```python
ramses_zone_info{zone_idx="02", zone_name="Kitchen", device_role="zone_actuator", device_id="04:122498"} 1.0
ramses_zone_info{zone_idx="02", zone_name="Kitchen", device_role="zone_sensor", device_id="04:122498"} 1.0
ramses_zone_info{zone_idx="02", zone_name="Kitchen", device_role="rad_actuator", device_id="04:122498"} 1.0
```

#### New Labels
- `device_role`: The role of the device in the zone
  - `zone_actuator`: Zone valve actuator
  - `zone_sensor`: Zone temperature sensor
  - `rad_actuator`: Radiator valve actuator (TRV)
  - `appliance_control`: Boiler/appliance control
  - `hotwater_valve`: Hot water valve
  - `dhw_sensor`: Domestic hot water sensor
  - `heating_valve`: Heating system valve
- `device_id`: RAMSES RF device identifier (e.g., "04:122498")

#### Message Processing
- Added processing for `zone_devices` messages (code 000C)
- Automatically captures and stores device-role-zone relationships
- Updates `zone_info` metric whenever zone names or device mappings change
- Handles empty device lists gracefully

#### Updated `_update_zone_info()` Method
- Now creates separate metric entries for each device-role combination
- Falls back to `device_role="unknown"` and `device_id="unknown"` when device mappings aren't available yet
- Prevents metric clutter by only creating metrics for known zones

### 2. Test Updates (`tests/test_zone_names.py`)

#### Fixed Tests for New Metric Format
- Updated regex patterns to work with additional labels
- Modified `test_zone_indices_format()` to only check `ramses_zone_info` metrics
- Updated expected zones to match sanitized sample data
- Replaced `test_zone_info_ignores_zone_idx_00()` with `test_zone_info_no_duplicate_unknown_entries()`
  - Zone "00" can be valid in some systems
  - New test ensures we don't have excessive unknown entries

#### Test Results
All 7 tests passing:
- ✓ test_zone_info_metrics_in_generated_output
- ✓ test_zone_info_metric_structure  
- ✓ test_zone_info_no_unknown_zones
- ✓ test_zone_info_no_duplicate_unknown_entries
- ✓ test_zone_indices_format
- ✓ test_expected_zones_present
- ✓ test_all_zone_names_are_real

### 3. Documentation (`docs/ZONE_DEVICE_MAPPING.md`)

Created comprehensive documentation covering:
- Metric structure and labels
- Usage examples in Grafana (joins, filters, variables)
- How the system discovers zone-device relationships
- Benefits and use cases
- Example data from sample messages

## Sample Data Results

From the sanitized test data, the system now exports:
- **10 zone_info metric entries** covering **4 zones**
- Each zone has multiple device roles (actuator, sensor, rad_actuator)

**Example zones discovered:**
- Kitchen (02): 04:122498 (zone_actuator, zone_sensor, rad_actuator)
- Master Bedroom (08): 04:122296 (zone_actuator, zone_sensor, rad_actuator)
- Office (0A): 04:122292 (zone_actuator, zone_sensor, rad_actuator)
- Living Room (01): 04:122504 (zone_sensor)

## Grafana Usage Example

### Before (required manual device-to-zone mapping):
```promql
ramses_device_temperature_celsius{device_id="04:122498"}
# No way to show "Kitchen" label without manual config
```

### After (automatic zone labels):
```promql
ramses_device_temperature_celsius
  * on(device_id) group_left(zone_name)
  ramses_zone_info{device_role="zone_sensor"}
# Automatically adds zone_name="Kitchen" label
```

## Benefits

1. **Automatic Discovery**: No manual device-to-zone configuration needed
2. **Multi-Role Support**: Single device can have multiple roles (sensor + actuator)
3. **Grafana-Friendly**: Standard Prometheus label joining patterns
4. **Self-Documenting**: Zone names appear directly in metrics
5. **Dynamic Updates**: Learns relationships from live RF messages
6. **Type Safety**: Device roles clearly labeled for filtering

## Backward Compatibility

⚠️ **Breaking Change**: The `ramses_zone_info` metric now has additional required labels (`device_role` and `device_id`). 

**Impact**: Existing Grafana queries that reference `ramses_zone_info` will need to be updated to include or ignore these new labels.

**Migration**: Update queries like:
```promql
# Old (will break)
ramses_zone_info{zone_idx="02"}

# New (works)
ramses_zone_info{zone_idx="02", device_role="zone_sensor"}
# or use aggregation to ignore device labels
count by (zone_idx, zone_name) (ramses_zone_info)
```

## Files Modified

- `honeywell_radio_exporter/ramses_prometheus_exporter.py`
- `tests/test_zone_names.py`
- `tests/sample_data/generated.txt` (regenerated)

## Files Created

- `docs/ZONE_DEVICE_MAPPING.md`
- `ZONE_DEVICE_MAPPING_CHANGELOG.md` (this file)

## Testing

```bash
# Run zone name tests
pytest tests/test_zone_names.py -v

# Regenerate sample metrics
pytest tests/test_sample_data_metrics.py::test_sample_data_metrics_generation -v
```

## Next Steps

1. Update existing Grafana dashboards to use new zone_info format
2. Create example dashboard queries in documentation
3. Consider adding zone-device mapping validation
4. Add metrics for orphaned devices (devices not in any zone)

