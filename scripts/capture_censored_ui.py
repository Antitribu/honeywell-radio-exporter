#!/usr/bin/env python3
"""
Capture censored UI screenshots of the exporter.

Why: the UI contains user-defined room/zone names and device names.
We blur only the name-bearing columns so screenshots can be published.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def main() -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Run:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    base_url = "http://localhost:8000/ui/"

    zones_output = docs_dir / "ui_zones_censored.png"
    devices_output = docs_dir / "ui_devices_censored.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        await page.goto(base_url, wait_until="domcontentloaded")
        # UI keeps some connections open (SSE), so don't use networkidle.
        await page.wait_for_timeout(2000)

        # -----------------------
        # Devices table screenshot
        # -----------------------
        # Device table columns (per current UI):
        #   1 ID, 2 Class, 3 Name, 4 Zone, ...
        # Blur only name-bearing cells.
        await page.add_style_tag(
            content="""
            table tr > td:nth-child(3),
            table tr > th:nth-child(3),
            table tr > td:nth-child(4),
            table tr > th:nth-child(4) {
                background: rgba(0, 0, 0, 0.95) !important;
                color: transparent !important;
                filter: blur(10px) !important;
            }
            """
        )

        await page.locator("h1:has-text('Devices')").first.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(devices_output), full_page=False)

        # --------------------
        # Zones table screenshot
        # --------------------
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Zones table columns (per current UI):
        #   1 Zone ID, 2 Name, ...
        await page.add_style_tag(
            content="""
            table tr > td:nth-child(2),
            table tr > th:nth-child(2) {
                background: rgba(0, 0, 0, 0.95) !important;
                color: transparent !important;
                filter: blur(10px) !important;
            }
            """
        )

        await page.locator("h2:has-text('Zones')").first.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(zones_output), full_page=False)

        await browser.close()

    ok = zones_output.exists() and devices_output.exists()
    if not ok:
        print("Screenshot generation failed; expected outputs missing.")
        return 1

    print("Saved:")
    print(f"  {devices_output}")
    print(f"  {zones_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

