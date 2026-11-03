"""Regenerates the README / docs screenshots (docs/images/*.webp) from a running stack.

    python scripts/screenshots.py --web http://localhost:3000
"""
import argparse, io
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"


def save(page, name, full=False):
    Image.open(io.BytesIO(page.screenshot(full_page=full))).save(OUT / f"{name}.webp", quality=86)
    print("wrote", name)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--web", default="http://localhost:3000"); a = ap.parse_args(); W = a.web
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        pg.goto(W); pg.wait_for_timeout(2500); save(pg, "landing")
        pg.goto(f"{W}/login"); pg.get_by_label("Email").fill("approver@orkestr.dev"); pg.get_by_label("Password").fill("orkestr-demo")
        pg.get_by_role("button", name="Sign in").click(); pg.wait_for_url("**/app"); pg.wait_for_timeout(4000); save(pg, "command")
        for name, url, wait in [("approvals", "/app/approvals", 2500), ("workflow-a", "/app/workflows/A", 3500), ("agents", "/app/agents", 3000),
                                ("observability", "/app/observability", 3500), ("integrations", "/app/integrations", 2500),
                                ("settings", "/app/settings", 4000), ("knowledge", "/app/knowledge", 2500)]:
            pg.goto(W + url); pg.wait_for_timeout(wait); save(pg, name)
        pg.goto(f"{W}/app/workflows/B"); pg.wait_for_timeout(3000)
        retried = pg.get_by_role("button", name="retried").first   # a run in which n8n retried Jira
        if retried.count():
            retried.click(); pg.wait_for_timeout(1500)
        save(pg, "workflow-b")
        pg.goto(f"{W}/app/cases"); pg.wait_for_timeout(1500); pg.get_by_role("tab", name="All").click(); pg.wait_for_timeout(1500)
        pg.get_by_role("link", name="Refund for order ORD-10421").last.click(); pg.wait_for_timeout(3000); save(pg, "case")
        pg.get_by_role("tab", name="Actions & approvals").click(); pg.wait_for_timeout(1200); save(pg, "case-actions")
        pg.goto(f"{W}/app/rfps"); pg.wait_for_timeout(2000)
        pg.locator("a[href^='/app/rfps/']").first.click(); pg.wait_for_timeout(3500)
        pg.locator("tbody tr").nth(7).click(); pg.wait_for_timeout(2500); save(pg, "rfp")
        pg.get_by_role("tab", name="Proposal").click(); pg.wait_for_timeout(2500); save(pg, "proposal")
        m = b.new_context(viewport={"width": 390, "height": 844}, storage_state=pg.context.storage_state()).new_page()
        m.goto(f"{W}/app"); m.wait_for_timeout(3500); save(m, "mobile-app")
        b.close()


if __name__ == "__main__":
    main()
