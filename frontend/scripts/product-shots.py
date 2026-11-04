"""Captures the product screenshots used on the landing page (public/screens/<name>-<theme>.webp).

    python scripts/product-shots.py --web http://localhost:3000
"""
import argparse, io
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "public" / "screens"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--web", default="http://localhost:3000"); W = ap.parse_args().web
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for theme in ["light", "dark"]:
            ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            ctx.add_init_script(f"try{{localStorage.setItem('axiomera-theme','{theme}')}}catch(e){{}}")
            p = ctx.new_page()
            p.goto(f"{W}/login"); p.get_by_label("Email").fill("approver@axiomera.dev"); p.get_by_label("Password").fill("axiomera-demo")
            p.get_by_role("button", name="Sign in").click(); p.wait_for_url("**/app"); p.wait_for_timeout(4000)
            shots = {"command-center": None, "observability": f"{W}/app/observability"}
            for name, url in shots.items():
                if url: p.goto(url); p.wait_for_timeout(3500)
                Image.open(io.BytesIO(p.screenshot())).save(OUT / f"{name}-{theme}.webp", quality=84)
            p.goto(f"{W}/app/rfps"); p.locator("a[href^='/app/rfps/']").first.click(); p.wait_for_timeout(3500)
            p.locator("tbody tr").nth(6).click(); p.wait_for_timeout(2000)
            p.mouse.wheel(0, 330); p.wait_for_timeout(800)
            Image.open(io.BytesIO(p.screenshot())).save(OUT / f"rfp-workspace-{theme}.webp", quality=84)
            ctx.close()
        b.close()


if __name__ == "__main__":
    main()
