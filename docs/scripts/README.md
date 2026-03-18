# Scripts

This directory contains utility scripts for the Honeywell Radio Exporter project.

## upload_grafana_dashboard.py

Uploads the RAMSES RF System Monitor dashboard to your Grafana instance.

### Prerequisites

```bash
pip install requests
```

### Usage

#### Method 1: Environment Variables (Recommended)

```bash
# Set your Grafana credentials
export GRAFANA_URL="https://grafana.example.com"
export GRAFANA_API_KEY="your-api-key-here"

# Run the script
./scripts/upload_grafana_dashboard.py
```

#### Method 2: Command Line Arguments

```bash
# Using API key
./scripts/upload_grafana_dashboard.py \
  --url https://grafana.example.com \
  --api-key glsa_xxxxxxxxxxxxx

# Using username/password
./scripts/upload_grafana_dashboard.py \
  --url https://grafana.example.com \
  --username admin \
  --password admin
```

#### Method 3: Custom Datasource

```bash
# Specify a specific Prometheus datasource UID
./scripts/upload_grafana_dashboard.py \
  --datasource-uid abc123xyz
```

### Creating a Grafana API Key

1. **For Grafana 9.0+** (Service Accounts):

   - Go to **Administration** → **Service Accounts**
   - Click **Add service account**
   - Name: `dashboard-uploader`
   - Role: `Editor`
   - Click **Add**
   - Click **Add service account token**
   - Copy the token (starts with `glsa_`)

1. **For Grafana < 9.0** (API Keys):

   - Go to **Configuration** → **API Keys**
   - Click **Add API key**
   - Name: `dashboard-uploader`
   - Role: `Editor`
   - Click **Add**
   - Copy the key

### Options

```
--url URL                  Grafana URL (default: https://grafana.example.com)
--api-key KEY              Grafana API key (preferred)
--username USER            Username for basic auth
--password PASS            Password for basic auth
--dashboard PATH           Path to dashboard JSON file
--datasource-uid UID       Prometheus datasource UID (auto-detected)
--folder-id ID             Folder ID to upload to (0 = General)
--skip-connection-test     Skip connection test before upload
--help                     Show help message
```

### Examples

**Basic upload:**

```bash
export GRAFANA_API_KEY="glsa_xxxxx"
./scripts/upload_grafana_dashboard.py
```

**Upload to specific folder:**

```bash
./scripts/upload_grafana_dashboard.py --folder-id 5
```

**Upload with custom dashboard file:**

```bash
./scripts/upload_grafana_dashboard.py \
  --dashboard /path/to/custom-dashboard.json
```

**Troubleshooting - skip connection test:**

```bash
./scripts/upload_grafana_dashboard.py --skip-connection-test
```

### Output

On success, you'll see:

```
======================================================================
GRAFANA DASHBOARD UPLOADER
======================================================================
Grafana URL: https://grafana.example.com
Dashboard:   docs/grafana-dashboard.json
Auth method: API Key
======================================================================

🔍 Testing connection to Grafana...
✅ Successfully connected to Grafana at https://grafana.example.com

🔍 Detecting Prometheus datasource...
✅ Found Prometheus datasource: PBFA97CFB590B2093

📤 Uploading dashboard...
📝 Setting datasource UID to: PBFA97CFB590B2093

✅ Dashboard uploaded successfully!
📊 Dashboard URL: https://grafana.example.com/d/ramses-rf/ramses-rf-system-monitor
🆔 Dashboard UID: ramses-rf
🆔 Dashboard ID: 42

======================================================================
🎉 Upload completed successfully!
======================================================================
```

### Security Notes

- **Never commit API keys to git** - always use environment variables
- Use service accounts with minimal required permissions (Editor role)
- Consider using Grafana's provisioning for production deployments
- API keys can be revoked at any time from Grafana UI

### Troubleshooting

**Connection Failed:**

- Check that Grafana URL is correct and accessible
- Verify firewall/network allows access to Grafana
- Try with `--skip-connection-test` if health endpoint is disabled

**Authentication Failed:**

- Verify API key is correct and not expired
- Check that API key has Editor or Admin role
- Try basic auth with username/password instead

**No Prometheus Datasource Found:**

- Dashboard will upload but queries won't work until datasource is configured
- Manually specify datasource UID with `--datasource-uid`
- Configure Prometheus datasource in Grafana first

**Dashboard Already Exists:**

- Script uses `overwrite: True` by default
- Existing dashboard will be updated
- Dashboard UID is preserved if it exists

### Advanced Usage

**Automated Deployment:**

```bash
#!/bin/bash
# deploy_dashboard.sh

set -e

echo "Deploying Grafana dashboard..."

# Load secrets from file
source .env

# Upload dashboard
./scripts/upload_grafana_dashboard.py

echo "Deployment complete!"
```

**Multiple Environments:**

```bash
# Development
export GRAFANA_URL="https://grafana-dev.example.com"
export GRAFANA_API_KEY="${GRAFANA_API_KEY_DEV}"
./scripts/upload_grafana_dashboard.py

# Production
export GRAFANA_URL="https://grafana.example.com"
export GRAFANA_API_KEY="${GRAFANA_API_KEY_PROD}"
./scripts/upload_grafana_dashboard.py
```

**CI/CD Integration:**

```yaml
# .github/workflows/deploy-dashboard.yml
name: Deploy Dashboard

on:
  push:
    branches: [main]
    paths:
      - 'docs/grafana-dashboard.json'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.x'
      
      - name: Install dependencies
        run: pip install requests
      
      - name: Upload dashboard
        env:
          GRAFANA_URL: https://grafana.example.com
          GRAFANA_API_KEY: ${{ secrets.GRAFANA_API_KEY }}
        run: ./scripts/upload_grafana_dashboard.py
```
