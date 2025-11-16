# Grafana Dashboard Updates - Zone Repeating Sections

## Summary

Updated the RAMSES RF System Monitor dashboard to include **repeating zone sections** that automatically create individual panels for each zone, displaying temperature, setpoint, and heat demand data.

## What's New

### 1. Enhanced Zone Variable
- **Multi-select enabled**: Can select individual zones or "All"
- **Include All option**: When "All" is selected, creates one section per zone
- **Default**: "All" selected by default to show all zones
- **Behavior**: The variable drives the row repeating - each selected zone gets its own section

### 2. Repeating Zone Row (ID: 100)
A new collapsible row that **repeats for each zone** discovered in the system:
- **Title**: "Zone: $zone" (dynamically shows zone name)
- **Behavior**: Creates one row per zone automatically
- **Data Source**: Populated from `ramses_zone_info` metric

### 3. Temperature & Setpoint Graph (ID: 101)
Inside each zone section, shows:
- **Blue solid line**: Actual temperature from zone sensor
- **Red dashed line**: Target setpoint temperature
- **Type**: Modern timeseries panel
- **Features**:
  - Smooth line interpolation
  - Legend table showing last, mean, min, max values
  - Celsius units with proper formatting

**Query Details:**
```promql
# Actual Temperature
avg(ramses_device_temperature_celsius 
  * on(device_id) group_left(zone_name) 
  ramses_zone_info{zone_name="$zone", device_role="zone_sensor"})

# Setpoint
avg(ramses_device_setpoint_celsius{zone_idx!=""} 
  * on(zone_idx) group_left(zone_name) 
  ramses_zone_info{zone_name="$zone"})
```

### 4. Heat Demand Graph (ID: 102)
Shows zone heat demand as a percentage:
- **Color gradient**: Blue (0%) → Green (20%) → Yellow (50%) → Orange (75%) → Red (90%)
- **Range**: 0-100%
- **Type**: Modern timeseries panel with opacity gradient
- **Features**:
  - Smooth line with 20% fill opacity
  - Threshold-based coloring
  - Legend showing last, mean, max values

**Query:**
```promql
# Heat Demand
avg(ramses_heat_demand{zone_idx!="FC"} 
  * on(zone_idx) group_left(zone_name) 
  ramses_zone_info{zone_name="$zone"}) * 100
```

## Layout

The repeating sections appear at the top of the dashboard (after system overview):

```
┌─────────────────────────────────────────────────────────┐
│ System Overview Panels (Message Rate, Active Devices)  │
├─────────────────────────────────────────────────────────┤
│ ▼ Zone: Kitchen                                         │
│ ┌──────────────────────┬──────────────────────┐        │
│ │ Temp & Setpoint      │ Heat Demand          │        │
│ │ (12 cols)            │ (12 cols)            │        │
│ └──────────────────────┴──────────────────────┘        │
├─────────────────────────────────────────────────────────┤
│ ▼ Zone: Living Room                                     │
│ ┌──────────────────────┬──────────────────────┐        │
│ │ Temp & Setpoint      │ Heat Demand          │        │
│ │ (12 cols)            │ (12 cols)            │        │
│ └──────────────────────┴──────────────────────┘        │
├─────────────────────────────────────────────────────────┤
│ ▼ Zone: Master Bedroom                                  │
│ ┌──────────────────────┬──────────────────────┐        │
│ │ Temp & Setpoint      │ Heat Demand          │        │
│ │ (12 cols)            │ (12 cols)            │        │
│ └──────────────────────┴──────────────────────┘        │
├─────────────────────────────────────────────────────────┤
│ ▼ Zone: Office                                          │
│ ┌──────────────────────┬──────────────────────┐        │
│ │ Temp & Setpoint      │ Heat Demand          │        │
│ │ (12 cols)            │ (12 cols)            │        │
│ └──────────────────────┴──────────────────────┘        │
├─────────────────────────────────────────────────────────┤
│ Temperature Related (existing panels)                   │
│ Boiler Metrics (existing panels)                        │
│ ...                                                      │
└─────────────────────────────────────────────────────────┘
```

## Benefits

1. **Automatic Discovery**: As new zones are added to the system, they automatically appear in the dashboard
2. **Per-Zone Views**: Each zone gets its own dedicated section with relevant metrics
3. **Easy Comparison**: Can quickly compare temperature vs setpoint to identify zones that need attention
4. **Heat Demand Visibility**: See which zones are actively calling for heat
5. **Collapsible Rows**: Can collapse zones you're not interested in to focus on specific areas

## How the Zone-Device Mapping Works

The queries leverage the enhanced `ramses_zone_info` metric that now includes device mappings:

```
ramses_zone_info{
  zone_idx="02",
  zone_name="Kitchen",
  device_role="zone_sensor",
  device_id="04:122498"
} = 1.0
```

This allows Prometheus queries to:
1. Filter devices by zone name
2. Filter by device role (zone_sensor, zone_actuator, etc.)
3. Join zone names to device metrics automatically

## Example Use Cases

### Identify Cold Zones
Look for zones where actual temperature is significantly below setpoint (large gap between lines).

### Monitor Heating Efficiency
Check if zones with high heat demand are warming up appropriately.

### Detect Sensor Issues
If temperature line is flat or shows unusual values, may indicate sensor problems.

### Energy Management
Zones with consistently high heat demand may need insulation improvements.

## Technical Details

### Panel IDs
- **100**: Repeating row container
- **101**: Temperature & Setpoint graph (repeats per zone)
- **102**: Heat Demand graph (repeats per zone)

### Grid Position
- Rows start at y=24 (after system overview panels)
- Each zone section takes 9 vertical grid units (1 for row + 8 for panels)
- Panels are split 50/50 (12 cols each)

### Queries Use Zone-Device Join
Both panels use the new `ramses_zone_info` metric to automatically associate:
- Device IDs with zone names
- Device roles with specific functions
- Multiple devices per zone (aggregated with `avg()`)

## Dashboard URL

After upload, the dashboard is available at:
```
http://grafana.my-monitoring.k8s.camarilla.local:3000/d/3c80a45f-f29e-4e0f-8902-2998c3fa8dd7/ramses-rf-system-monitor
```

**Dashboard UID**: `3c80a45f-f29e-4e0f-8902-2998c3fa8dd7`  
**Dashboard ID**: `88`

## Files Modified

- `docs/grafana-dashboard.json` - Updated dashboard configuration
- `docs/DASHBOARD_UPDATES.md` - This documentation file

## Next Steps

1. Monitor the dashboard to ensure all zones appear correctly
2. Adjust time ranges and refresh intervals as needed
3. Consider adding alerts based on temperature/setpoint deltas
4. Add additional zone-specific metrics if needed (window status, mode, etc.)

## How Row Repeating Works

When you select the zone variable:
- **"All" selected**: Dashboard creates one section for each zone (Kitchen, Living Room, Master Bedroom, Office)
- **Multiple zones selected**: Creates sections only for the selected zones
- **Single zone selected**: Shows only one section for that zone

Grafana's row repeating feature automatically:
1. Reads all values from the `zone` variable
2. Creates one row instance per value
3. Scopes the `$zone` variable within each row to that specific value
4. Renders the panels inside each row with the scoped variable

## Notes

- The zone variable supports multi-select, allowing you to view specific zones or all zones
- When "All" is selected, you'll see: "Zone: Kitchen", "Zone: Living Room", etc. (one per zone)
- Zones without device mappings won't show temperature data (only if they have zone_sensor devices)
- The `zone_idx="FC"` is excluded from heat demand (system/appliance control zone)
- Empty zones (no devices) will still show a row but graphs will be empty
- You can collapse rows you're not interested in to focus on specific zones

