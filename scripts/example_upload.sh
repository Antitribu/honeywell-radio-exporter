#!/bin/bash
#
# Example script to upload Grafana dashboard
#
# Usage:
#   1. Create API key in Grafana
#   2. Set GRAFANA_API_KEY environment variable
#   3. Run this script
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================="
echo "Grafana Dashboard Upload Example"
echo "======================================================================="
echo ""

if [ -z "$GRAFANA_URL" ]; then
    echo -e "${RED}Error: GRAFANA_URL environment variable not set${NC}"
    echo ""
    echo "To set it:"
    echo "  export GRAFANA_URL=\"http://your-grafana-url:3000\""
    echo ""
    exit 1
fi


# Check if API key is set
if [ -z "$GRAFANA_API_KEY" ]; then
    echo -e "${RED}Error: GRAFANA_API_KEY environment variable not set${NC}"
    echo ""
    echo "To set it:"
    echo "  export GRAFANA_API_KEY=\"your-api-key-here\""
    echo ""
    echo "To create an API key:"
    echo "  1. Go to ${GRAFANA_URL}"
    echo "  2. Navigate to Configuration → API Keys (or Service Accounts)"
    echo "  3. Create new key with 'Editor' role"
    echo "  4. Copy the key"
    echo ""
    exit 1
fi

# Check if requests library is installed
if ! python3 -c "import requests" 2>/dev/null; then
    echo -e "${YELLOW}Warning: 'requests' library not installed${NC}"
    echo ""
    echo "Installing requests..."
    pip install requests
    echo ""
fi

# Upload dashboard
echo "Uploading dashboard to: ${GRAFANA_URL}"
echo ""

export GRAFANA_URL="${GRAFANA_URL}"

"${SCRIPT_DIR}/upload_grafana_dashboard.py"

echo ""
echo -e "${GREEN}Done!${NC}"

