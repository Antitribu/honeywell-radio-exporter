# Caching Implementation Summary

## Overview

Added persistent caching of zone and device names to `/tmp/ramses_rf_cache.json` to maintain accurate metrics across exporter restarts.

## Changes Made

### 1. Core Exporter Module (`ramses_prometheus_exporter.py`)

#### Added Imports
```python
import json
from datetime import datetime
```

#### New Instance Variables (in `__init__`)
```python
self.cache_file = Path("/tmp/ramses_rf_cache.json")
self.zone_name_cache: Dict[str, Dict[str, Any]] = {}
self.device_name_cache: Dict[str, Dict[str, Any]] = {}
```

#### New Methods

**Cache Management:**
- `_load_cache()` - Loads cache from disk on startup
- `_save_cache()` - Saves cache to disk (atomic write)
- `_update_zone_name_cache(zone_idx, zone_name)` - Updates zone cache with validation
- `_update_device_name_cache(device_id, device_name)` - Updates device cache with validation

**Modified Methods:**
- `_get_zone_name()` - Now checks cache before gateway
- `_get_device_name()` - Now checks cache before gateway
- `_update_device_info()` - Calls cache update when device name found
- `_capture_message_metrics()` - Calls cache update when zone name captured

## How It Works

### Cache Structure

```json
{
  "zones": {
    "zone_idx": {
      "name": "Zone Name",
      "first_seen": 1234567890.123,
      "last_seen": 1234567890.456
    }
  },
  "devices": {
    "device_id": {
      "name": "Device Name",
      "first_seen": 1234567890.123,
      "last_seen": 1234567890.456
    }
  },
  "last_updated": "2024-11-17T12:00:00"
}
```

### Lifecycle

1. **Startup**:
   - Load cache from `/tmp/ramses_rf_cache.json`
   - If file exists: populate `zone_name_cache` and `device_name_cache`
   - If file doesn't exist: start with empty cache
   - Log cache loading results

2. **Message Processing**:
   - When `zone_name` message (code 0004) arrives:
     - Extract zone_idx and zone_name
     - Call `_update_zone_name_cache()` 
     - Validates and saves if new or changed
   - When device messages arrive:
     - Extract device_id and device_name from gateway
     - Call `_update_device_name_cache()`
     - Validates and saves if new or changed

3. **Name Lookups**:
   - `_get_zone_name()`: Check cache first, then gateway
   - `_get_device_name()`: Check cache first, then gateway
   - Ensures cached names are used even if gateway not available

### Validation Logic

**New Discovery:**
- Add to cache with `first_seen` and `last_seen` timestamps
- Save cache file immediately
- Log: `"Discovered new zone/device: X = 'Name'"`

**Name Change:**
- Update cache with new name
- Update `last_seen` timestamp
- Save cache file immediately
- Log warning: `"Zone/Device X name changed from 'Old' to 'New' (updating cache)"`

**Confirmation:**
- Update `last_seen` timestamp only (no save)
- Reduces I/O for unchanged entries

### Atomic Writes

Cache saves use atomic file operations to prevent corruption:
```python
temp_file = self.cache_file.with_suffix(".tmp")
with open(temp_file, "w") as f:
    json.dump(cache_data, f, indent=2)
temp_file.replace(self.cache_file)  # Atomic rename
```

## Benefits

### Immediate Metrics After Restart
**Before:**
```
ramses_zone_info{zone_idx="02", zone_name="unknown", ...} 1.0
```

**After:**
```
ramses_zone_info{zone_idx="02", zone_name="Kitchen", ...} 1.0
```

### Data Integrity
- Validates incoming names against cache
- Detects and logs name changes
- Auto-corrects with most recent information

### Performance
- **Fast lookups**: Cache checked before gateway API
- **Reduced I/O**: Only saves on changes, not on every message
- **Atomic writes**: Prevents file corruption

## Testing

### Unit Test Requirements
- Test cache load with valid file
- Test cache load with missing file
- Test cache load with corrupted file
- Test cache save
- Test zone name update (new, changed, unchanged)
- Test device name update (new, changed, unchanged)
- Test atomic write behavior

### Integration Test
```bash
# 1. Start exporter
cd /home/simon/src/development/honeywell-radio-exporter
source venv/bin/activate
python -m honeywell_radio_exporter

# 2. Verify cache creation
cat /tmp/ramses_rf_cache.json

# 3. Check logs
# Should see: "Loaded cache from..." or "No cache file found..."

# 4. Restart and verify immediate name availability
# Metrics should show correct zone/device names immediately
```

## Files Modified

1. **`honeywell_radio_exporter/ramses_prometheus_exporter.py`**
   - Added cache loading/saving functionality
   - Modified name lookup methods to use cache
   - Added cache validation and update logic

## Files Created

1. **`docs/CACHE_DOCUMENTATION.md`** - Complete user documentation
2. **`CACHING_IMPLEMENTATION.md`** - This file (developer documentation)

## Configuration

### Cache File Location
Currently hardcoded: `/tmp/ramses_rf_cache.json`

### Future Enhancement
Make configurable via:
- Environment variable: `RAMSES_CACHE_FILE`
- Command-line argument: `--cache-file`

## Logging

**INFO Level:**
- Cache load results
- New zone/device discoveries
- Zone/device name changes

**DEBUG Level:**
- Cache save operations

**WARNING Level:**
- Name changes (potential config issues)

**ERROR Level:**
- Cache load/save failures

## Example Logs

```
2024-11-17 12:00:00 - INFO - No cache file found at /tmp/ramses_rf_cache.json, starting with empty cache
2024-11-17 12:00:15 - INFO - Discovered new zone: 01 = 'Living Room'
2024-11-17 12:00:15 - DEBUG - Saved cache to /tmp/ramses_rf_cache.json: 1 zones, 0 devices
2024-11-17 12:00:20 - INFO - Discovered new zone: 02 = 'Kitchen'
2024-11-17 12:00:30 - INFO - Discovered new device: 04:122498 = 'TRV_Kitchen'
2024-11-17 12:05:00 - WARNING - Zone 02 name changed from 'Kitchn' to 'Kitchen' (updating cache)
```

## Compatibility

- **Backward Compatible**: If cache file doesn't exist, works as before
- **No Breaking Changes**: Existing functionality unchanged
- **Optional Feature**: Can delete cache file to reset if needed

## Performance Impact

- **Minimal**: Cache lookups are O(1) dictionary operations
- **Improved Startup**: Names available immediately vs waiting for discovery
- **Reduced Gateway Load**: Cache reduces API calls to gateway object

## Security Considerations

- Cache file in `/tmp` - readable by all users on system
- Contains only zone/device IDs and names (no sensitive data)
- File permissions follow system defaults for `/tmp`

## Maintenance

### View Cache
```bash
cat /tmp/ramses_rf_cache.json | python3 -m json.tool
```

### Clear Cache
```bash
rm /tmp/ramses_rf_cache.json
# Restart exporter to rebuild
```

### Backup Cache
```bash
cp /tmp/ramses_rf_cache.json ~/ramses_cache_backup.json
```

## Next Steps

1. Add unit tests for caching functionality
2. Consider making cache location configurable
3. Add cache metrics (size, age, hit rate)
4. Add cache expiry for stale entries
5. Consider caching zone-device mappings

