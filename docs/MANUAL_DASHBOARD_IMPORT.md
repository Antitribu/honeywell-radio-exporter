# Manual Dashboard Import Guide

Your Grafana instance at `https://grafana.example.com` is behind an SSO/authentication proxy
(`auth.example.com`), which means automated API uploads won't work directly. Use this manual import
guide instead.

## 📊 Quick Import (5 minutes)

### Step 1: Access Grafana

1. Open your browser and go to: **https://grafana.example.com**
1. Login through your SSO provider

### Step 2: Navigate to Import

1. Click the **"+"** icon in the left sidebar

1. Select **"Import dashboard"**

   OR directly visit: **https://grafana.example.com/dashboard/import**

### Step 3: Upload Dashboard

1. Click **"Upload JSON file"**
1. Select the file: `docs/grafana-dashboard.json`
1. Click **"Load"**

### Step 4: Configure Datasource

1. In the import dialog, you'll see:

   - Dashboard name: "RAMSES RF System Monitor"
   - Folder: Select where to save (or leave as "General")
   - Prometheus datasource: **Select your Prometheus datasource**

1. Click **"Import"**

### Step 5: Done! 🎉

Your dashboard is now live at: **https://grafana.example.com/d/ramses-rf/ramses-rf-system-monitor**

## 📝 What's in the Dashboard

The dashboard includes 20 panels covering:

### Row 1: Message Statistics (Basic Monitoring)

- Message rate graph
- Active devices counter
- Message processing duration
- Error rate tracking

### Row 2: Device Communications

- Top message types table
- Device communication heatmap
- Message payload size

### Row 3: Temperature & Heat Demand

- **Device Temperatures** - Current temperature for all devices
- **Heat Demand by Zone** - Percentage heat demand (0-100%) per zone

### Row 4: Boiler Health & Communication ⭐

- **Boiler Communication Health** - Time since last boiler response (with thresholds)
- **Boiler Message Rate** - Messages per minute sent/received
- **Boiler Response Rate** - Percentage of successful responses

### Row 5: Boiler Message Details

- **Boiler Message Types** - Pie chart of message distribution
- **Boiler Message History** - Detailed breakdown table

### Row 6: Zone Details

- **Zone Setpoint vs Temperature** - Target vs actual comparison
- **Zone Window Status** - Open/closed state per zone
- **System Sync Status** - Controller sync cycle countdown

### Row 7: Device Activity

- **Device Last Seen** - Time since last message from each device
- **Zone Modes** - Current active mode for each zone

## 🔧 Dashboard Configuration

### Setting Up Alerts (Optional)

After importing, you can add alerts in Grafana:

1. **Edit a Panel** → Click panel title → Edit
1. **Alert tab** → Create alert rule
1. **Example alerts:**
   - Boiler not responding (> 5 minutes)
   - High heat demand with no temperature rise
   - Device offline (> 10 minutes)
   - Low boiler response rate (< 50%)

### Customizing Panels

You can customize any panel:

- **Edit** - Modify queries, thresholds, colors
- **Duplicate** - Create variations
- **Move** - Rearrange layout
- **Delete** - Remove unwanted panels

### Time Range

Default: Last 1 hour, auto-refresh every 10 seconds

To change:

- Click time picker (top right)
- Select different range or custom
- Adjust refresh interval

## 🔄 Updating the Dashboard

When there are updates to the dashboard JSON:

### Method 1: Re-import (Overwrites)

1. Go to: https://grafana.example.com/dashboard/import
1. Upload new `docs/grafana-dashboard.json`
1. Check **"Import (Overwrite)"** option
1. Click Import

### Method 2: Manual Edit

1. Open the dashboard
1. Click ⚙️ (Dashboard settings) → JSON Model
1. Paste new JSON
1. Click "Save changes"

### Method 3: Version Control

1. In Dashboard settings → Versions
1. Save dashboard version before updating
1. You can rollback if needed

## 🐛 Troubleshooting

### "No data" in panels

- **Check datasource:** Ensure Prometheus datasource is selected
- **Check Prometheus:** Verify exporter is running and Prometheus is scraping
- **Check queries:** Edit panel → Queries tab → Test query

### Panels not loading

- **Check time range:** Might be no data for selected period
- **Check metrics:** Go to http://localhost:8000/metrics to verify metrics exist
- **Check Prometheus targets:** Prometheus → Status → Targets

### Boiler metrics empty

- **Check message logs:** grep "BDR|boiler" /tmp/ramses.log
- **Verify boiler devices:** Check if device IDs start with 10: or 13:
- **Wait for messages:** Boilers may only send messages when active

### Colors/thresholds wrong

- Edit panel → Field → Thresholds
- Adjust values to match your system

## 📚 Advanced: Dashboard JSON Structure

The dashboard JSON has this structure:

```json
{
  "dashboard": {
    "title": "RAMSES RF System Monitor",
    "panels": [
      {
        "id": 1,
        "title": "Panel Title",
        "type": "graph",
        "targets": [
          {
            "expr": "prometheus_query",
            "legendFormat": "{{label}}"
          }
        ]
      }
    ]
  }
}
```

You can edit directly if needed, but the import UI is easier.

## 🔐 Why Manual Import?

Your Grafana instance uses SSO authentication (`auth.example.com`), which means:

- API endpoints redirect to login page
- API keys are bypassed by the auth proxy
- Automated uploads don't work
- Manual import through UI is the supported method

This is a common and secure setup for Grafana in enterprise environments.

## 📞 Need Help?

If you encounter issues:

1. Check Grafana logs: `/var/log/grafana/grafana.log` (on server)
1. Check browser console: F12 → Console tab
1. Verify exporter is running: http://localhost:8000/metrics
1. Verify Prometheus is scraping: http://prometheus:9090/targets

## ✅ Verification Checklist

After import, verify:

- [ ] Dashboard loads without errors
- [ ] All panels show data (or "No data" if legitimately empty)
- [ ] Boiler panels show your boiler devices
- [ ] Temperature readings are current
- [ ] Time range selector works
- [ ] Auto-refresh is working (check top-right)
- [ ] You can edit and save changes (if you have permissions)

## 🎯 Expected Results

Once imported with data flowing:

- **2 boilers detected** (13:004003, 13:243590)
- **Multiple zones** with temperatures
- **Heat demand values** (0-100%)
- **Message rates** (messages per minute)
- **System sync** counting down from 156 seconds
- **Device last seen** within last few minutes

Enjoy your comprehensive RAMSES RF monitoring dashboard! 🎉
