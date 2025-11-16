# Metric Refactoring Summary

## Overview

This document describes the major refactoring of the Prometheus metrics structure for the RAMSES RF exporter. The old approach using separate `ramses_zone_info` and `ramses_device_info` metrics for joining has been replaced with direct labels on all metrics.

## Changes Made

### 1. Removed Old Info Metrics

**Removed:**
- `ramses_zone_info` - Previously used as a lookup table for zone names and device mappings
- `ramses_device_info` - Previously used as a lookup table for device names

### 2. Added Direct Labels to All Metrics

All device and zone metrics now include `device_name` and `zone_name` labels directly:

**Updated Metrics:**
- `ramses_device_temperature_celsius` - Added: `device_name`, `zone_name`
- `ramses_device_last_seen_timestamp` - Added: `device_name`, `zone_name`
- `ramses_device_setpoint_celsius` - Added: `device_name`, `zone_name`
- `ramses_zone_window_open` - Added: `device_name`, `zone_name`
- `ramses_zone_mode_info` - Added: `device_name`, `zone_name`
- `ramses_heat_demand` - Added: `device_name`, `zone_name`
- `ramses_system_sync_remaining_seconds` - Added: `device_name`, `zone_name`
- `ramses_system_sync_last_timestamp` - Added: `device_name`, `zone_name`

### 3. Label Values

- When device or zone names are known (from cache or messages), they are used directly
- When names are unknown, the label value is set to `"unknown"`
- Zone names are discovered from `zone_name` messages (code 0004)
- Device names are discovered from `device_name` messages (code 0005)

### 4. Caching

The caching mechanism for zone and device names is maintained and continues to work:
- Cache file: `/tmp/ramses_rf_cache.json`
- Loads on startup
- Updates when new names are discovered
- Saves atomically to prevent corruption

### 5. Grafana Dashboard Updates

All Grafana queries have been simplified to use direct labels instead of joins:

**Before:**
```promql
avg(ramses_device_temperature_celsius * on(device_id) group_left(zone_name) ramses_zone_info{zone_name="$zone", device_role="zone_sensor"})
```

**After:**
```promql
avg(ramses_device_temperature_celsius{zone_name=~"$zone"})
```

**Updated Queries:**
- Temperature & Setpoint graphs
- Heat Demand graphs
- Zone Window Status
- Zone Modes
- Device Temperatures
- Device Last Seen
- All repeating zone sections

### 6. Zone Variable Source

The Grafana dashboard's `zone` templating variable now sources from metrics directly:

**Before:**
```promql
label_values(ramses_zone_info, zone_name)
```

**After:**
```promql
label_values(ramses_device_temperature_celsius, zone_name)
```

## Benefits

### Performance
- **Eliminated joins**: Queries are now direct label filters, which are much faster
- **Reduced metric count**: Removed two entire metric families (zone_info and device_info)
- **Lower cardinality**: Fewer label combinations overall

### Simplicity
- **Simpler queries**: No need for complex PromQL joins with `* on() group_left()`
- **Easier to understand**: Labels are directly on metrics where they're used
- **Better UX**: Grafana queries are more intuitive

### Flexibility
- **Unknown handling**: Metrics with "unknown" labels are created immediately, allowing visibility of all devices
- **Gradual discovery**: As names are learned, they're updated in subsequent scrapes
- **Cache persistence**: Names persist across restarts via cache file

## Migration Notes

### For Existing Dashboards

Any existing Grafana dashboards using the old metrics will need to be updated:

1. Replace `ramses_zone_info` joins with direct `zone_name` label filters
2. Replace `ramses_device_info` joins with direct `device_name` label filters
3. Update templating variable queries to use actual metrics instead of info metrics
4. Test "All" selection in zone variables to ensure proper iteration

### For Queries and Alerts

Update any PromQL queries or alerts that reference:
- `ramses_zone_info` → Use `zone_name` label on actual metrics
- `ramses_device_info` → Use `device_name` label on actual metrics

Example migration:
```promql
# Old
ramses_device_setpoint_celsius * on(zone_idx) group_left(zone_name) ramses_zone_info

# New
ramses_device_setpoint_celsius
```

## Testing

All tests have been updated and pass:
- `tests/test_zone_names.py` - Validates zone_name labels in metrics
- `tests/test_device_names.py` - Validates device_name labels in metrics
- `tests/test_metrics_validation.py` - Validates metric structure
- `tests/test_sample_data_metrics.py` - Generates sample output

## Implementation Details

### Code Changes

**In `ramses_prometheus_exporter.py`:**
1. Updated metric definitions to include new labels
2. Added `_get_zone_for_device()` helper method
3. Updated all metric `.labels()` calls to include `device_name` and `zone_name`
4. Removed `_update_zone_info()` and `_update_device_info()` methods
5. Maintained cache functionality for name lookups

**In Grafana dashboard:**
1. Updated `zone` variable query
2. Simplified all panel queries
3. Removed all `* on() group_left()` joins
4. Updated legend formats to use new labels

## Date

Implemented: November 16, 2025

