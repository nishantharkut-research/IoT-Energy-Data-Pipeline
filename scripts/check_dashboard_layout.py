"""Check rendered dashboard layout, selected runs and open dialogs in Chromium."""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import shutil
import threading
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.capture_operator_dashboard import PAGES

VIEWPORTS = (
    (1920, 1080),
    (1600, 900),
    (1536, 864),
    (1440, 900),
    (1366, 768),
    (1280, 720),
    (1100, 800),
    (1024, 768),
)


@contextmanager
def serve(directory: Path):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=directory
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def settle(page):
    page.evaluate(
        "() => document.fonts.ready.then(() => new Promise("
        "r => requestAnimationFrame(() => requestAnimationFrame(r))))"
    )


def check_metrics(page):
    rows = page.locator(".stats-grid").evaluate_all(
        """els => els.flatMap(grid => {
          const rows = new Map();
          for (const card of grid.children) {
            const row = Math.round(card.getBoundingClientRect().top);
            const top = card.querySelector('strong').getBoundingClientRect().top;
            rows.set(row, [...(rows.get(row) || []), top]);
          }
          return [...rows.values()];
        })"""
    )
    assert all(max(row) - min(row) <= 1 for row in rows), (
        f"Metric baselines differ: {rows}"
    )


def check_watermark_spacing(page):
    gap = page.locator(".watermark-grid").evaluate(
        """grid => {
          const groups = [...grid.children].map(el => {
            const out=[]; const w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
            let n;
            while(n=w.nextNode()) {
              if(!n.textContent.trim()) continue;
              const r=document.createRange();r.selectNodeContents(n);
              out.push(...[...r.getClientRects()].filter(b=>b.width>1 && b.height>1));
            }
            return out;
          });
          let gap=Infinity;
          for(let i=0;i<groups.length;i++) for(let j=i+1;j<groups.length;j++)
            for(const a of groups[i]) for(const b of groups[j])
              if(Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>3)
                gap=Math.min(gap,Math.max(a.left,b.left)-Math.min(a.right,b.right));
          return Number.isFinite(gap)?gap:null;
        }"""
    )
    assert gap is None or gap >= 12, f"Watermark text has only {gap}px separation"


def check_compact_tables(page):
    widths = page.locator(".data-table").evaluate_all(
        """els => els.filter(el => el.tHead.rows[0].cells.length === 2).map(el => ({
          width:el.getBoundingClientRect().width,
          available:el.closest('.mantine-ScrollArea-root').clientWidth}))"""
    )
    assert all(w["width"] <= w["available"] + 1 for w in widths), widths


def check(url: str, output: Path) -> None:
    cases = []
    errors = []
    with sync_playwright() as api:
        browser = api.chromium.launch(
            executable_path=shutil.which("google-chrome") or shutil.which("chromium"),
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 800})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url, wait_until="networkidle")
        for width, height in VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            for slug, title in PAGES:
                page.evaluate("hash => location.hash=hash", slug)
                page.get_by_role("heading", name=title, exact=True).wait_for()
                settle(page)
                assert not page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                ), f"Page overflow: {slug} at {width}"
                if slug in ("fault-comparison", "storage-sql"):
                    page.locator(".recharts-cartesian-axis-tick-value").first.wait_for()
                visible_text = page.locator("body").inner_text().lower()
                assert not any(
                    term in visible_text
                    for term in ("iotbdm", "coursework", "abv-iiitm")
                ), "Academic branding remains visible"
                check_metrics(page)
                if slug == "watermark-review":
                    check_watermark_spacing(page)
                check_compact_tables(page)
                if slug == "fault-comparison":
                    labels = page.locator(
                        ".recharts-cartesian-axis-tick-value"
                    ).all_text_contents()
                    labels = [
                        v
                        for v in labels
                        if v
                        in {"Clean", "Duplicate", "Delayed", "Malformed", "Combined"}
                    ]
                    assert labels == [
                        "Clean",
                        "Duplicate",
                        "Delayed",
                        "Malformed",
                        "Combined",
                    ], f"Missing schedule labels at {width}: {labels}"
                cases.append(
                    {"page": slug, "width": width, "height": height, "passed": True}
                )
        for width in (1440, 1024):
            page.set_viewport_size({"width": width, "height": 720})
            page.goto(f"{url}/#overview", wait_until="networkidle")
            page.get_by_role("button", name="Export evidence", exact=True).click()
            page.get_by_role("menuitem", name="Run register · CSV").wait_for()
            page.keyboard.press("Escape")
            page.get_by_role(
                "button", name="Inspect correctness-combined-r01", exact=True
            ).click()
            page.get_by_role("dialog").wait_for()
            settle(page)
            check_compact_tables(page)
            page.get_by_role("button", name="Done", exact=True).click()
            page.get_by_role("button", name="Data provenance").click()
            page.get_by_role("dialog").wait_for()
            settle(page)
            check_compact_tables(page)
            page.keyboard.press("Escape")
            for slug, title in (
                ("delivery-inspector", "Delivery inspector"),
                ("storage-sql", "Storage & SQL"),
            ):
                page.goto(f"{url}/#{slug}", wait_until="networkidle")
                page.get_by_role("heading", name=title, exact=True).wait_for()
                page.get_by_role(
                    "combobox", name="Recorded experiment", exact=True
                ).click()
                page.get_by_role("option", name="1M · repetition 1", exact=True).click()
                settle(page)
                check_metrics(page)
                assert not page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                )
                check_compact_tables(page)
            cases.append({"width": width, "state": "menus-dialogs-1M", "passed": True})
        browser.close()
    assert not errors, errors
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"page_errors": errors, "checks": cases}, indent=2) + "\n"
    )
    print(f"Passed {len(cases)} rendered layout/state cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument("--serve", type=Path)
    parser.add_argument("--output", type=Path, default=Path("tmp/layout-checks.json"))
    args = parser.parse_args()
    if args.serve:
        with serve(args.serve.resolve()) as url:
            check(url, args.output)
    else:
        check(args.url, args.output)
