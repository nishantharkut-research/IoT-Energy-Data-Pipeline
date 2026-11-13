"""Capture the running React dashboard and exercise its saved-evidence workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGES = [
    ("overview", "Overview"),
    ("source-audit", "Source audit"),
    ("delivery-inspector", "Delivery inspector"),
    ("fault-comparison", "Fault comparison"),
    ("verification", "Verification"),
    ("watermark-review", "Watermark review"),
    ("recovery", "Recovery"),
    ("storage-sql", "Storage & SQL"),
    ("india-use-case", "India use case"),
]


def capture(url: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    errors: list[str] = []
    with sync_playwright() as api:
        browser = api.chromium.launch(
            executable_path=shutil.which("google-chrome") or shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))
        for i, (slug, heading) in enumerate(PAGES, 1):
            page.goto(f"{url}/#{slug}", wait_until="networkidle")
            page.get_by_role("heading", name=heading, exact=True).wait_for()
            page.wait_for_timeout(300)
            stem = f"{i:02d}-{slug}"
            page.screenshot(path=str(output / f"{stem}.png"), full_page=True)
            page.screenshot(path=str(output / f"report-{stem}.png"))
            overflow = page.evaluate(
                "document.documentElement.scrollWidth > innerWidth"
            )
            assert not overflow, f"Page overflow: {slug}"
            checks.append({"page": slug, "viewport": "1280x900", "overflow": overflow})
        # Raw and resampled source counters must actually change.
        page.goto(f"{url}/#source-audit", wait_until="networkidle")
        page.get_by_role("radiogroup").get_by_text("Raw source", exact=True).click()
        page.get_by_text("50,903,710 physical data rows", exact=True).wait_for()
        page.get_by_text("100.000%", exact=True).wait_for()
        page.get_by_text("Publisher-resampled source", exact=True).click()
        page.get_by_text("63,273,828 physical data rows", exact=True).wait_for()
        checks.append({"interaction": "source-variant-switch", "passed": True})
        # Register search and pagination, followed by an actual selected-run export.
        page.goto(f"{url}/#overview", wait_until="networkidle")
        search = page.get_by_role("textbox", name="Search completed runs")
        search.fill("restrictive")
        page.get_by_text("Showing 1–1 of 1 runs", exact=True).wait_for()
        page.get_by_role(
            "button", name="Inspect watermark-restrictive-r01", exact=True
        ).click()
        page.get_by_role("dialog").wait_for()
        with page.expect_download() as downloaded:
            page.get_by_role("button", name="Export run JSON", exact=True).click()
        payload = json.loads(Path(downloaded.value.path()).read_text())
        assert payload["run"]["run_id"] == "watermark-restrictive-r01"
        assert payload["runtime_reverified"] is False
        page.screenshot(path=str(output / "run-inspector-dialog.png"))
        page.get_by_role("button", name="Done", exact=True).click()
        search.fill("")
        page.get_by_text("Showing 1–5 of 15 runs", exact=True).wait_for()
        page.get_by_role("button", name="2", exact=True).click()
        page.get_by_text("Showing 6–10 of 15 runs", exact=True).wait_for()
        checks.append({"interaction": "search-pagination-run-export", "passed": True})
        # Original result download must preserve exact original evidence bytes.
        page.get_by_role("button", name="Export evidence", exact=True).click()
        with page.expect_download() as downloaded:
            page.get_by_text("Full saved results · JSON", exact=True).click()
        digest = hashlib.sha256(Path(downloaded.value.path()).read_bytes()).hexdigest()
        assert (
            digest == "1e18dbfeae8e708ab31e60b468afb9bbe04dc788176af532e2bf66885326dfcc"
        )
        checks.append({"interaction": "exact-results-download", "sha256": digest})
        page.get_by_role("button", name="Export evidence", exact=True).click()
        with page.expect_download() as downloaded:
            page.get_by_text("Run register · CSV", exact=True).click()
        csv = Path(downloaded.value.path()).read_text()
        assert len(csv.strip().splitlines()) == 16
        checks.append({"interaction": "csv-export", "rows": 15})
        page.get_by_role("button", name="Data provenance").click()
        page.get_by_role("dialog").get_by_text(
            "Evidence provenance", exact=True
        ).wait_for()
        assert (
            page.get_by_role("dialog")
            .get_by_role("button", name="Copy full SHA-256")
            .count()
            == 4
        )
        page.keyboard.press("Escape")
        page.goto(f"{url}/#delivery-inspector", wait_until="networkidle")
        page.get_by_role("tab", name="Accounting", exact=True).click()
        page.get_by_text(
            "Repeated delivery of an existing source event", exact=True
        ).wait_for()
        page.get_by_role("tab", name="Run contract", exact=True).click()
        page.get_by_text("Offsets per trigger", exact=True).wait_for()
        checks.append({"interaction": "provenance-and-delivery-tabs", "passed": True})
        page.goto(f"{url}/#watermark-review", wait_until="networkidle")
        page.get_by_text("Retaining · 24 hours", exact=True).click()
        page.get_by_text("Candidate retains all 144", exact=True).wait_for()
        page.get_by_text("Restrictive · 1 minute", exact=True).click()
        page.get_by_text("Review late-valid disposition", exact=True).wait_for()
        checks.append({"interaction": "watermark-policy-switch", "passed": True})
        # Responsive layouts should contain the page, with tables scrolling locally.
        for width in (1440, 1100, 1024):
            page.set_viewport_size({"width": width, "height": 1000})
            for slug, heading in PAGES:
                page.goto(f"{url}/#{slug}", wait_until="networkidle")
                page.get_by_role("heading", name=heading, exact=True).wait_for()
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                )
                assert not overflow, f"Overflow at {width}: {slug}"
            checks.append(
                {"viewport_width": width, "pages_checked": 9, "overflow": False}
            )
        # Mutated evidence must stop the viewer before any affirmative results appear.
        tampered = browser.new_page()
        tampered.route(
            "**/evidence/final-results.json",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"fabricated"}',
            ),
        )
        tampered.goto(url, wait_until="networkidle")
        tampered.get_by_role(
            "heading", name="Evidence could not be displayed"
        ).wait_for()
        assert not tampered.get_by_text("Completed experiments", exact=True).count()
        checks.append({"interaction": "tampered-evidence-rejected", "passed": True})
        browser.close()
    assert not errors, errors
    (output / "browser-checks.json").write_text(
        json.dumps(
            {
                "page_errors": errors,
                "capture": "actual running React app",
                "checks": checks,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/submission/figures/dashboard")
    )
    args = parser.parse_args()
    capture(args.url, args.output)
