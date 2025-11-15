#!/usr/bin/env python3
"""
Upload Grafana Dashboard

Uploads the RAMSES RF System Monitor dashboard to a Grafana instance.

Usage:
    export GRAFANA_API_KEY="your-api-key-here"
    ./scripts/upload_grafana_dashboard.py

Or with command line arguments:
    ./scripts/upload_grafana_dashboard.py --url https://grafana.example.com --api-key <key>

Requirements:
    pip install requests
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install it with: pip install requests")
    sys.exit(1)


class GrafanaDashboardUploader:
    """Handles uploading dashboards to Grafana."""

    def __init__(
        self, grafana_url: str, api_key: str = None, username: str = None, password: str = None
    ):
        """
        Initialize the uploader.

        Args:
            grafana_url: Base URL of Grafana instance (e.g., https://grafana.example.com)
            api_key: Grafana API key (preferred)
            username: Username for basic auth (alternative to API key)
            password: Password for basic auth (alternative to API key)
        """
        self.grafana_url = grafana_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password

        # Prepare authentication headers
        self.headers = {"Content-Type": "application/json"}
        self.auth = None

        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        elif username and password:
            self.auth = (username, password)
        else:
            raise ValueError("Either API key or username/password must be provided")

    def test_connection(self) -> bool:
        """Test connection to Grafana instance."""
        try:
            response = requests.get(
                f"{self.grafana_url}/api/health", headers=self.headers, auth=self.auth, timeout=10
            )
            if response.status_code == 200:
                print(f"✅ Successfully connected to Grafana at {self.grafana_url}")
                return True
            else:
                print(f"⚠️  Grafana responded with status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to Grafana: {e}")
            return False

    def get_datasources(self) -> list:
        """Get list of available datasources."""
        try:
            response = requests.get(
                f"{self.grafana_url}/api/datasources",
                headers=self.headers,
                auth=self.auth,
                timeout=10,
            )
            response.raise_for_status()

            # Check if response is JSON
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                print(f"⚠️  Unexpected content type: {content_type}")
                print(f"⚠️  Response preview: {response.text[:200]}")
                return []

            return response.json()
        except json.JSONDecodeError as e:
            print(f"⚠️  Could not parse datasources response as JSON: {e}")
            print(f"⚠️  Response status: {response.status_code}")
            print(f"⚠️  Response preview: {response.text[:200]}")
            return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Could not fetch datasources: {e}")
            return []

    def upload_dashboard(
        self, dashboard_path: Path, datasource_uid: str = None, folder_id: int = 0
    ) -> bool:
        """
        Upload dashboard to Grafana.

        Args:
            dashboard_path: Path to dashboard JSON file
            datasource_uid: UID of the Prometheus datasource (optional)
            folder_id: Folder ID to upload to (0 = General, default)

        Returns:
            True if successful, False otherwise
        """
        # Read dashboard file
        try:
            with open(dashboard_path, "r") as f:
                dashboard_data = json.load(f)
        except FileNotFoundError:
            print(f"❌ Dashboard file not found: {dashboard_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in dashboard file: {e}")
            return False

        # Extract dashboard from wrapper if present
        if "dashboard" in dashboard_data:
            dashboard = dashboard_data["dashboard"]
        else:
            dashboard = dashboard_data

        # Remove id to allow Grafana to assign a new one
        dashboard["id"] = None

        # Update datasource if provided
        if datasource_uid:
            print(f"📝 Setting datasource UID to: {datasource_uid}")
            self._update_datasource_uids(dashboard, datasource_uid)

        # Prepare payload for Grafana API
        payload = {
            "dashboard": dashboard,
            "folderId": folder_id,
            "overwrite": True,
            "message": "Uploaded via upload_grafana_dashboard.py script",
        }

        # Upload to Grafana
        try:
            response = requests.post(
                f"{self.grafana_url}/api/dashboards/db",
                headers=self.headers,
                auth=self.auth,
                json=payload,
                timeout=30,
            )

            # Check content type before parsing
            content_type = response.headers.get("Content-Type", "")

            if response.status_code == 200:
                if "application/json" not in content_type:
                    print(f"\n❌ Unexpected response content type: {content_type}")
                    print(f"Response preview: {response.text[:500]}")
                    return False

                try:
                    result = response.json()
                except json.JSONDecodeError as e:
                    print(f"\n❌ Could not parse response as JSON: {e}")
                    print(f"Response preview: {response.text[:500]}")
                    return False

                dashboard_url = f"{self.grafana_url}{result.get('url', '')}"
                print(f"\n✅ Dashboard uploaded successfully!")
                print(f"📊 Dashboard URL: {dashboard_url}")
                print(f"🆔 Dashboard UID: {result.get('uid', 'N/A')}")
                print(f"🆔 Dashboard ID: {result.get('id', 'N/A')}")
                return True
            else:
                print(f"\n❌ Failed to upload dashboard")
                print(f"Status: {response.status_code}")
                print(f"Content-Type: {content_type}")
                print(f"Response: {response.text[:500]}")
                return False

        except json.JSONDecodeError as e:
            print(f"❌ Error parsing response: {e}")
            print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
            print(f"Response preview: {response.text[:500] if 'response' in locals() else 'N/A'}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Error uploading dashboard: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response preview: {e.response.text[:500]}")
            return False

    def _update_datasource_uids(self, dashboard: Dict[str, Any], datasource_uid: str):
        """Recursively update datasource UIDs in dashboard panels."""
        if isinstance(dashboard, dict):
            # Update datasource at panel level
            if "datasource" in dashboard:
                if isinstance(dashboard["datasource"], dict):
                    dashboard["datasource"]["uid"] = datasource_uid
                else:
                    dashboard["datasource"] = {"uid": datasource_uid, "type": "prometheus"}

            # Update targets datasource
            if "targets" in dashboard:
                for target in dashboard["targets"]:
                    if isinstance(target, dict):
                        target["datasource"] = {"uid": datasource_uid, "type": "prometheus"}

            # Recurse into nested structures
            for value in dashboard.values():
                if isinstance(value, (dict, list)):
                    self._update_datasource_uids(value, datasource_uid)

        elif isinstance(dashboard, list):
            for item in dashboard:
                if isinstance(item, (dict, list)):
                    self._update_datasource_uids(item, datasource_uid)


def find_prometheus_datasource(datasources: list) -> str:
    """Find Prometheus datasource UID from list of datasources."""
    prometheus_sources = [ds for ds in datasources if ds.get("type") == "prometheus"]

    if not prometheus_sources:
        return None

    # Prefer default datasource
    for ds in prometheus_sources:
        if ds.get("isDefault"):
            return ds.get("uid")

    # Return first Prometheus datasource
    return prometheus_sources[0].get("uid")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Upload RAMSES RF dashboard to Grafana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variables (recommended):
  export GRAFANA_URL="https://grafana.example.com"
  export GRAFANA_API_KEY="your-api-key"
  ./scripts/upload_grafana_dashboard.py

  # Using command line arguments:
  ./scripts/upload_grafana_dashboard.py --url https://grafana.example.com --api-key glsa_xxxxx

  # Using basic auth:
  ./scripts/upload_grafana_dashboard.py --url https://grafana.example.com --username admin --password admin

  # Specify custom datasource:
  ./scripts/upload_grafana_dashboard.py --datasource-uid abc123xyz

Grafana API Key Creation:
  1. Go to Configuration → API Keys (or Service Accounts in newer versions)
  2. Create new API key with 'Editor' role
  3. Copy the key and use it with --api-key or GRAFANA_API_KEY
        """,
    )

    parser.add_argument(
        "--url",
        default=os.getenv("GRAFANA_URL", "http://grafana.my-monitoring.k8s.camarilla.local:3000"),
        help="Grafana URL (default: http://grafana.my-monitoring.k8s.camarilla.local:3000 or GRAFANA_URL env var)",
    )

    parser.add_argument(
        "--api-key",
        default=os.getenv("GRAFANA_API_KEY"),
        help="Grafana API key (or use GRAFANA_API_KEY env var)",
    )

    parser.add_argument(
        "--username",
        default=os.getenv("GRAFANA_USERNAME"),
        help="Grafana username for basic auth (or use GRAFANA_USERNAME env var)",
    )

    parser.add_argument(
        "--password",
        default=os.getenv("GRAFANA_PASSWORD"),
        help="Grafana password for basic auth (or use GRAFANA_PASSWORD env var)",
    )

    parser.add_argument(
        "--dashboard",
        type=Path,
        default=Path(__file__).parent.parent / "docs" / "grafana-dashboard.json",
        help="Path to dashboard JSON file",
    )

    parser.add_argument(
        "--datasource-uid", help="UID of Prometheus datasource (auto-detected if not specified)"
    )

    parser.add_argument(
        "--folder-id",
        type=int,
        default=0,
        help="Folder ID to upload to (0 = General folder, default)",
    )

    parser.add_argument(
        "--skip-connection-test", action="store_true", help="Skip connection test before upload"
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    # Validate authentication
    if not args.api_key and not (args.username and args.password):
        print("❌ Error: Authentication required!")
        print("   Provide either:")
        print("   - API key via --api-key or GRAFANA_API_KEY environment variable")
        print(
            "   - Username and password via --username/--password or GRAFANA_USERNAME/GRAFANA_PASSWORD"
        )
        print("\nRun with --help for more information")
        sys.exit(1)

    # Validate dashboard file
    if not args.dashboard.exists():
        print(f"❌ Error: Dashboard file not found: {args.dashboard}")
        sys.exit(1)

    print("=" * 70)
    print("GRAFANA DASHBOARD UPLOADER")
    print("=" * 70)
    print(f"Grafana URL: {args.url}")
    print(f"Dashboard:   {args.dashboard}")
    print(f"Auth method: {'API Key' if args.api_key else 'Basic Auth'}")
    if args.debug:
        print(f"Debug mode:  ENABLED")
        if args.api_key:
            print(f"API Key:     {args.api_key[:10]}...{args.api_key[-4:]}")
    print("=" * 70)

    # Initialize uploader
    try:
        uploader = GrafanaDashboardUploader(
            grafana_url=args.url,
            api_key=args.api_key,
            username=args.username,
            password=args.password,
        )
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Test connection
    if not args.skip_connection_test:
        print("\n🔍 Testing connection to Grafana...")
        if not uploader.test_connection():
            print("\n⚠️  Connection test failed. Continue anyway? (y/N): ", end="")
            if input().lower() != "y":
                sys.exit(1)

    # Get datasources if UID not specified
    datasource_uid = args.datasource_uid
    if not datasource_uid:
        print("\n🔍 Detecting Prometheus datasource...")
        datasources = uploader.get_datasources()
        if datasources:
            datasource_uid = find_prometheus_datasource(datasources)
            if datasource_uid:
                print(f"✅ Found Prometheus datasource: {datasource_uid}")
            else:
                print("⚠️  No Prometheus datasource found")
                print("   Dashboard will be uploaded without datasource configuration")
        else:
            print("⚠️  Could not fetch datasources")

    # Upload dashboard
    print("\n📤 Uploading dashboard...")
    success = uploader.upload_dashboard(
        dashboard_path=args.dashboard, datasource_uid=datasource_uid, folder_id=args.folder_id
    )

    if success:
        print("\n" + "=" * 70)
        print("🎉 Upload completed successfully!")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("❌ Upload failed")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
