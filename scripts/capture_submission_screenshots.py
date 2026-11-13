"""Capture the actual saved-results dashboard and check basic presentation states."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

from dashboard.submission import PAGES


def capture(url: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    with sync_playwright() as browser_api:
        browser = browser_api.chromium.launch(
            executable_path=shutil.which("google-chrome") or shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 2000}, device_scale_factor=1
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle")
        for number, name in enumerate(PAGES, 1):
            page.get_by_text(name, exact=True).first.click()
            page.get_by_role("heading", name=name, exact=True).wait_for()
            page.wait_for_timeout(900)
            if page.locator('[data-testid="stException"]').count():
                raise RuntimeError(f"Streamlit exception on {name}")
            main = page.locator('[data-testid="stMainBlockContainer"]')
            box = main.bounding_box()
            if not box:
                raise RuntimeError("Main content not found")
            padding = main.evaluate(
                """el => {
                    const s = getComputedStyle(el);
                    return {top: parseFloat(s.paddingTop),
                            left: parseFloat(s.paddingLeft),
                            right: parseFloat(s.paddingRight),
                            bottom: parseFloat(s.paddingBottom)};
                }"""
            )
            page.screenshot(
                path=str(
                    output
                    / (
                        f"{number:02d}-"
                        f"{name.lower().replace(' & ', '-').replace(' ', '-')}.png"
                    )
                ),
                clip={
                    "x": box["x"] + padding["left"],
                    "y": max(0, box["y"] + padding["top"]),
                    "width": box["width"] - padding["left"] - padding["right"],
                    "height": box["height"] - padding["top"] - padding["bottom"],
                },
                animations="disabled",
            )
            report_box = {
                "x": box["x"] + padding["left"],
                "y": max(0, box["y"] + padding["top"]),
                "width": box["width"] - padding["left"] - padding["right"],
                "height": box["height"] - padding["top"] - padding["bottom"],
            }
            if name in ("Overview", "Independent verification", "Recovery"):
                endpoint = page.locator(".evidence-table").first.bounding_box()
            elif name in ("Source quality", "Delivery accounting", "Fault handling"):
                endpoint = page.locator(
                    '[data-testid="stPlotlyChart"]'
                ).first.bounding_box()
            else:
                endpoint = None
            if endpoint:
                report_box["height"] = (
                    endpoint["y"] + endpoint["height"] + 8 - report_box["y"]
                )
            if name == "Delivery accounting":
                equation = (
                    page.locator('[data-testid="stMarkdownContainer"]')
                    .filter(has_text="parsed-valid =")
                    .last.bounding_box()
                )
                if equation:
                    report_box["height"] = (
                        equation["y"] + equation["height"] + 10 - report_box["y"]
                    )
            if name == "Storage & SQL":
                query_table = page.locator(".evidence-table").first.bounding_box()
                if query_table:
                    report_box["y"] = query_table["y"]
                    report_box["height"] = query_table["height"] + 8
            if name == "Watermark & consumption":
                table = page.locator(".evidence-table").first.bounding_box()
                warning = page.locator('[data-testid="stAlert"]').first.bounding_box()
                if table and warning:
                    report_box["y"] = table["y"]
                    report_box["height"] = (
                        warning["y"] + warning["height"] - table["y"] + 8
                    )
            filename = (
                f"{number:02d}-{name.lower().replace(' & ', '-').replace(' ', '-')}.png"
            )
            page.screenshot(
                path=str(output / ("report-" + filename)),
                clip=report_box,
                animations="disabled",
            )
            overflow = page.evaluate(
                "document.documentElement.scrollWidth > innerWidth"
            )
            checks.append(
                {
                    "view": name,
                    "horizontal_overflow": overflow,
                    "streamlit_exception": False,
                    "capture": "actual running app",
                }
            )
            if overflow:
                raise RuntimeError(f"Horizontal page overflow on {name}")
        page.set_viewport_size({"width": 1280, "height": 900})
        page.get_by_text("Overview", exact=True).first.click()
        page.get_by_role("heading", name="Overview", exact=True).wait_for()
        page.wait_for_timeout(500)
        page.screenshot(path=str(output / "overview-desktop.png"), full_page=True)
        checks.append(
            {
                "viewport": "1280x900",
                "horizontal_overflow": page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                ),
            }
        )
        page.set_viewport_size({"width": 720, "height": 1000})
        page.wait_for_timeout(500)
        checks.append(
            {
                "viewport": "720x1000",
                "horizontal_overflow": page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                ),
            }
        )
        if errors or any(row.get("horizontal_overflow") for row in checks):
            raise RuntimeError(f"Browser checks failed: {errors}, {checks}")
        browser.close()
    (output / "browser-checks.json").write_text(
        json.dumps({"page_errors": errors, "checks": checks}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8501")
    parser.add_argument("--output", type=Path, default=Path("docs/submission/figures"))
    args = parser.parse_args()
    capture(args.url, args.output)
