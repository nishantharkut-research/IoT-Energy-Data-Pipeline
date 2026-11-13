"""Capture readable desktop workspaces for the project report."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.capture_operator_dashboard import PAGES


def capture(url: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as api:
        browser = api.chromium.launch(
            executable_path=shutil.which("google-chrome") or shutil.which("chromium"),
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1024, "height": 1200})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for number, (slug, title) in enumerate(PAGES, 1):
            page.goto(f"{url}/#{slug}", wait_until="networkidle")
            page.get_by_role("heading", name=title, exact=True).wait_for()
            page.evaluate("window.scrollTo(0,0)")
            page.wait_for_timeout(250)
            workspace = page.locator(".workspace").bounding_box()
            assert workspace is not None
            if slug == "delivery-inspector":
                target = page.locator(".pipeline-board")
            elif slug == "watermark-review":
                target = page.locator(".panel").nth(2)
            elif slug == "storage-sql":
                target = page.locator(".two-columns").first
            elif slug == "india-use-case":
                target = page.locator(".panel").nth(1)
            else:
                target = page.locator(".panel").first
            box = target.bounding_box()
            assert box is not None
            height = min(box["y"] + box["height"] + 8 - workspace["y"], 850)
            page.screenshot(
                path=str(output / f"{number:02d}-{slug}.png"),
                clip={
                    "x": workspace["x"],
                    "y": workspace["y"],
                    "width": workspace["width"],
                    "height": height,
                },
                animations="disabled",
            )
        assert not errors, errors
        browser.close()
    print("Captured nine desktop workspaces from the running application")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/submission/figures/report")
    )
    args = parser.parse_args()
    capture(args.url, args.output)
