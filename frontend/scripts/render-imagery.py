import sys
from playwright.sync_api import sync_playwright
w, h = int(sys.argv[2]), int(sys.argv[3])
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    p = b.new_page(viewport={"width": w, "height": h})
    for spec in sys.argv[1].split(","):
        name, _, q = spec.partition("?")
        p.goto(f"http://localhost:8811/scene.html?s={name}&w={w}&h={h}&{q}")
        p.wait_for_function("window.__done === true", timeout=180000)
        p.screenshot(path=f"out-{name}{'-'+q.replace('=','').replace('&','') if q else ''}.png"); print("ok", spec)
    b.close()
