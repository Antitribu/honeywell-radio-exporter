# Zone and Device Name Caching

## Overview

The RAMSES RF Prometheus Exporter now includes persistent caching of zone and device names to maintain accurate metrics across restarts. This ensures that discovered zone and device names are preserved and immediately available when the exporter restarts.

## Cache File Location

**Path**: `/tmp/ramses_rf_cache.json`

This file is automatically created and maintained by the exporter.

## What is Cached

The cache stores two types of information:

### 1. Zone Names
- **Zone Index** → **Zone Name** mapping
- Example: `"02"` → `"Kitchen"`
- Includes timestamps for first and last seen

### 2. Device Names
- **Device ID** → **Device Name/Alias** mapping
- Example: `"04:122498"` → `"TRV_Kitchen"`
- Includes timestamps for first and last seen

## Cache File Format

```json
{
  "zones": {
    "01": {
      "name": "Living Room",
      "first_seen": 1731840000.123,
      "last_seen": 1731926400.456
    },
    "02": {
      "name": "Kitchen",
      "first_seen": 1731840100.789,
      "last_seen": 1731926401.234
    }
  },
  "devices": {
    "04:122498": {
      "name": "TRV_Kitchen",
      "first_seen": 1731840000.111,
      "last_seen": 1731926400.222
    },
    "04:122504": {
      "name": "TRV_LivingRoom",
      "first_seen": 1731840050.333,
      "last_seen": 1731926401.444
    }
  },
  "last_updated": "2024-11-17T12:00:01.555666"
}
```

## How It Works

### On Startup (Cache Load)

1. **Exporter starts** → Looks for `/tmp/ramses_rf_cache.json`
2. **Cache exists** → Loads zone and device names into memory
   - Logs: `"Loaded cache from /tmp/ramses_rf_cache.json: X zones, Y devices"`
3. **Cache doesn't exist** → Starts with empty cache
   - Logs: `"No cache file found at /tmp/ramses_rf_cache.json, starting with empty cache"`

### During Operation (Cache Updates)

The cache is automatically validated and updated when messages arrive:

#### Zone Name Discovery
- **Trigger**: `zone_name` messages (code 0004)
- **Validation**: 
  - New zone discovered → Added to cache + saved
  - Zone name changed → Updated in cache + saved + warning logged
  - Zone name unchanged → Only last_seen timestamp updated (no disk write)

#### Device Name Discovery
- **Trigger**: Any message from a device with a configured name/alias
- **Validation**:
  - New device discovered → Added to cache + saved
  - Device name changed → Updated in cache + saved + warning logged
  - Device name unchanged → Only last_seen timestamp updated (no disk write)

### Cache Validation

The exporter validates cache entries against incoming messages:

1. **New Information Wins**: When a message contains a name that differs from the cache:
   - Cache is updated with the new value
   - Warning is logged: `"Zone X name changed from 'OldName' to 'NewName' (updating cache)"`
   - Cache file is immediately saved

2. **Timestamps Track Currency**:
   - `first_seen`: When the zone/device was first discovered
   - `last_seen`: Last time a message confirmed this name
   - Helps identify stale entries

## Benefits

### 1. Immediate Metrics on Restart
Without caching, the exporter would show:
```
ramses_zone_info{zone_idx="02", zone_name="unknown", ...} 1.0
```

With caching, it immediately shows:
```
ramses_zone_info{zone_idx="02", zone_name="Kitchen", ...} 1.0
```

### 2. Accurate Historical Data
- Grafana queries work correctly even after restarts
- No gaps in zone/device labeling
- Consistent metric labels over time

### 3. Fast Discovery Recovery
- Previously discovered zones/devices are immediately available
- No waiting period for zone_name messages to repopulate
- Metrics are accurate from the first message received

### 4. Validation and Self-Healing
- Detects and logs when names change
- Automatically updates to latest information
- Maintains data integrity

## Performance Optimization

### Atomic Writes
Cache saves use atomic file replacement:
```python
temp_file.write(cache_data)  # Write to .tmp file
temp_file.replace(cache_file)  # Atomic rename
```

This prevents corruption if the process is interrupted during save.

### Reduced I/O
- **Only saves on changes**: New discoveries or name changes trigger saves
- **Timestamp updates don't save**: last_seen updates are in-memory only
- **Debouncing**: Multiple changes in quick succession don't cause excessive writes

## Logging

### Info Level
- **Startup**: Cache load results
- **Discovery**: New zones/devices found
- **Changes**: Zone/device name changes

### Debug Level
- Cache save operations (with counts)

### Warning Level
- Name changes (potential configuration issues)
- Cache load/save errors

### Example Logs

```
INFO - Loaded cache from /tmp/ramses_rf_cache.json: 4 zones, 10 devices
INFO - Cached zones: ['01', '02', '08', '0A']
INFO - Cached devices: ['04:122498', '04:122504', '04:122296', ...]
INFO - Discovered new zone: 03 = 'Hallway'
WARNING - Zone 02 name changed from 'Kitchn' to 'Kitchen' (updating cache)
INFO - Discovered new device: 04:122820 = 'TRV_Bedroom3'
DEBUG - Saved cache to /tmp/ramses_rf_cache.json: 5 zones, 11 devices
```

## Maintenance

### Viewing the Cache

```bash
# Pretty-print the cache file
cat /tmp/ramses_rf_cache.json | python3 -m json.tool

# Check cache size
du -h /tmp/ramses_rf_cache.json

# Monitor cache updates in real-time
watch -n 5 "cat /tmp/ramses_rf_cache.json | python3 -m json.tool"
```

### Clearing the Cache

If you need to reset the cache (e.g., after major configuration changes):

```bash
# Stop the exporter
systemctl stop ramses-prometheus-exporter

# Remove cache file
rm /tmp/ramses_rf_cache.json

# Start the exporter (will rebuild cache from messages)
systemctl start ramses-prometheus-exporter
```

The exporter will automatically rebuild the cache as it receives zone_name and device messages.

### Backup/Restore

```bash
# Backup cache
cp /tmp/ramses_rf_cache.json ~/ramses_cache_backup.json

# Restore cache (exporter must be stopped)
systemctl stop ramses-prometheus-exporter
cp ~/ramses_cache_backup.json /tmp/ramses_rf_cache.json
systemctl start ramses-prometheus-exporter
```

## Troubleshooting

### Cache Not Loading

**Symptom**: Logs show "No cache file found" but file exists

**Solution**: Check file permissions
```bash
ls -l /tmp/ramses_rf_cache.json
# Should be readable by the exporter process user
```

### Cache Not Saving

**Symptom**: Changes aren't persisted across restarts

**Solution**: Check write permissions to `/tmp`
```bash
# Verify /tmp is writable
touch /tmp/test_write && rm /tmp/test_write

# Check exporter logs for save errors
journalctl -u ramses-prometheus-exporter | grep -i cache
```

### Stale Names in Cache

**Symptom**: Old zone/device names persist despite configuration changes

**Solution**: The cache will auto-update when new messages arrive with different names. Or manually clear the cache (see above).

### Cache File Corruption

**Symptom**: "Failed to load cache: JSON decode error"

**Solution**: The exporter will automatically start with empty cache and rebuild. If persistent:
```bash
# Remove corrupted cache
rm /tmp/ramses_rf_cache.json

# Restart exporter
systemctl restart ramses-prometheus-exporter
```

## Configuration

The cache file location is currently hardcoded to `/tmp/ramses_rf_cache.json`. This can be customized by modifying the exporter initialization:

```python
# In ramses_prometheus_exporter.py __init__
self.cache_file = Path("/custom/path/ramses_rf_cache.json")
```

Future enhancement: Make this configurable via environment variable or command-line argument.

## Integration with Metrics

The cache integrates seamlessly with metric generation:

1. **Metric queries check cache first** via `_get_zone_name()` and `_get_device_name()`
2. **Fallback to gateway** if not in cache
3. **Cache auto-updates** when new information is discovered
4. **Metrics stay accurate** even without gateway connection (uses cached names)

This means:
- Zone info metrics show correct names immediately after restart
- Device info metrics populate quickly
- Grafana dashboards work correctly without waiting for rediscovery

## Testing

To test the caching functionality:

```bash
# 1. Start exporter and let it discover zones/devices
systemctl start ramses-prometheus-exporter

# 2. Verify cache is created
cat /tmp/ramses_rf_cache.json

# 3. Restart exporter
systemctl restart ramses-prometheus-exporter

# 4. Check logs - should see "Loaded cache" message
journalctl -u ramses-prometheus-exporter -n 50 | grep cache

# 5. Verify metrics show correct names immediately
curl http://localhost:8000/metrics | grep ramses_zone_info
```

## Future Enhancements

Potential improvements to the caching system:

1. **Configurable cache location** via environment variable
2. **Cache expiry** for entries not seen in X days
3. **Cache statistics** exposed as Prometheus metrics
4. **Multi-file caching** for zone devices mapping
5. **Cache validation on startup** against gateway (if available)
6. **Export/import commands** for cache management

