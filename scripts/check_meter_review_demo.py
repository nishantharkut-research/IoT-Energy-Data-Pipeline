"""Exercise the synthetic meter review and capture its actual desktop workspace."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    output = Path("docs/submission/figures/report")
    with sync_playwright() as api:
        browser = api.chromium.launch(
            executable_path="/usr/bin/google-chrome", args=["--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://localhost:5173/#meter-review-demo", wait_until="networkidle")
        page.get_by_role("heading", name="Meter review demo", exact=True).wait_for()
        page.get_by_text("Demo data", exact=True).wait_for()
        page.get_by_role("button", name="09:30", exact=True).click()
        assert page.get_by_test_id("meter-register").text_content() == "001001.0"
        page.get_by_label("Analyst note", exact=True).fill(
            "Late receipt checked against the sample source event."
        )
        page.get_by_role("button", name="Mark reviewed", exact=True).click()
        with page.expect_download() as event:
            page.get_by_role("button", name="Export review", exact=True).click()
        data = json.loads(Path(event.value.path()).read_text())
        assert data["reviewed"] is True and data["scenario"]["id"] == "DEMO-1042"
        assert data["note"].startswith("Late receipt") and data["basis"] == "Demo data"
        page.get_by_role("button", name="DEMO-2087", exact=False).click()
        page.get_by_text("1001.0 kWh × 2 receipts", exact=True).wait_for()
        page.get_by_role("button", name="DEMO-3016", exact=False).click()
        page.get_by_text("Source follow-up required", exact=True).wait_for()
        page.get_by_role("cell", name="Unavailable", exact=True).wait_for()
        assert page.get_by_test_id("meter-register").text_content() == "------"
        page.get_by_role("combobox", name="Filter meter exceptions").click()
        page.get_by_role("option", name="Source gap", exact=True).click()
        assert page.locator(".review-case").count() == 1
        page.get_by_role("combobox", name="Filter meter exceptions").click()
        page.get_by_role("option", name="All exceptions", exact=True).click()
        page.get_by_role("button", name="Reset session", exact=True).click()
        page.get_by_role("button", name="DEMO-1042", exact=False).click()
        page.get_by_role("button", name="10:30", exact=True).click()
        assert not page.get_by_label("Analyst note", exact=True).input_value()
        assert page.get_by_role("button", name="Mark reviewed", exact=True).is_enabled()
        for width in [1024, 1280, 1440]:
            page.set_viewport_size({"width": width, "height": 1100})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.set_viewport_size({"width": 1280, "height": 1500})
        page.screenshot(path=str(output / "10-meter-review-full.png"), full_page=True)
        page.set_viewport_size({"width": 1024, "height": 1500})
        target = page.locator(".meter-device-panel").bounding_box()
        assert target
        page.screenshot(
            path=str(output / "10-meter-review.png"),
            clip={
                "x": target["x"],
                "y": target["y"],
                "width": target["width"],
                "height": target["height"],
            },
        )
        assert not errors, errors
        browser.close()
    print(
        "Meter review: three cases, review state, notes, JSON export, reset "
        "and three desktop widths passed"
    )


if __name__ == "__main__":
    main()
