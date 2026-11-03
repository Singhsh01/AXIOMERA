"""Captures the frames for the business use-case video from a real run of the refund journey."""
import json, time, uuid, sys
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

WEB, API, PW = "http://localhost:3000", "http://localhost:8000", "orkestr-demo"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "frames"); OUT.mkdir(parents=True, exist_ok=True)
CAP = """(([step, text, top]) => {
  document.getElementById('qa-cap')?.remove();
  const d = document.createElement('div'); d.id = 'qa-cap';
  d.style.cssText = 'position:fixed;left:0;right:0;margin:0 auto;width:fit-content;' + (top ? 'top:12px;' : 'bottom:28px;') + 'z-index:99999;display:flex;align-items:center;gap:14px;' +
    'padding:14px 22px 14px 14px;border-radius:16px;background:rgba(20,26,51,0.92);color:#fff;font:500 19px "IBM Plex Sans",sans-serif;' +
    'box-shadow:0 18px 50px -12px rgba(20,26,51,.45);max-width:1120px;letter-spacing:-0.005em;backdrop-filter:blur(8px)';
  const b = document.createElement('span');
  b.style.cssText = 'flex:none;display:grid;place-items:center;min-width:34px;height:34px;padding:0 10px;border-radius:10px;background:linear-gradient(180deg,#7D6EEA,#4B3BC4);font:600 16px "IBM Plex Sans",sans-serif';
  b.textContent = step; d.append(b, document.createTextNode(text)); document.body.append(d);
})"""

def login(page, who):
    page.goto(f"{WEB}/login"); page.get_by_label("Email").fill(f"{who}@orkestr.dev"); page.get_by_label("Password").fill(PW)
    page.get_by_role("button", name="Sign in").click(); page.wait_for_url("**/app"); page.wait_for_timeout(2500)

def snap(page, name, step, text, top=False):
    page.evaluate(CAP, [step, text, top]); page.wait_for_timeout(250)
    page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=92)

http = httpx.Client(base_url=API, timeout=30)
tok = lambda who: {"Authorization": "Bearer " + http.post("/api/v1/auth/login", json={"email": f"{who}@orkestr.dev", "password": PW}).json()["token"]}

with sync_playwright() as pw:
    b = pw.chromium.launch()
    new = lambda: b.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2).new_page()
    land = new(); land.goto(WEB); land.wait_for_timeout(2500)
    snap(land, "s1", "▶", "A customer emails asking for a €149 refund. Here is what ORKESTR does with it.")

    ops = new(); login(ops, "ops")
    ops.goto(f"{WEB}/app/cases"); ops.get_by_role("button", name="New request").click()
    subject = "Refund for order ORD-10421"
    ops.get_by_label("Subject").fill(subject); ops.wait_for_timeout(400)
    snap(ops, "s2", "1", "The email reaches a signed n8n webhook and becomes a tracked case")
    before = {a["id"] for a in http.get("/api/v1/approvals?status=pending", headers=tok("approver")).json()}
    ops.get_by_role("button", name="Submit request").click(); ops.wait_for_timeout(1500); ops.get_by_role("button", name="Close").click()
    h = tok("approver"); mine = []
    for _ in range(40):
        mine = [a for a in http.get("/api/v1/approvals?status=pending", headers=h).json() if a["id"] not in before and subject in json.dumps(a)]
        if len(mine) >= 2: break
        time.sleep(1.5)
    case_id = mine[0]["case"]["id"]
    ops.goto(f"{WEB}/app/cases/{case_id}"); ops.wait_for_timeout(3000)
    snap(ops, "s3", "2", "AI agents classify it, check the order against policy and propose the refund, with sources")

    ap = new(); login(ap, "approver")
    refund = next(a for a in mine if a["action_type"] == "issue_refund")
    ap.goto(f"{WEB}/app/approvals?focus={refund['id']}"); ap.wait_for_timeout(2500)
    ap.get_by_label("Decision note").fill("Order and amount verified")
    snap(ap, "s4", "3", "Policy routes it to an approver; nobody can approve their own request", top=True)
    for a in sorted(mine, key=lambda a: a["action_type"] != "issue_refund"):
        ap.goto(f"{WEB}/app/approvals?focus={a['id']}"); ap.wait_for_timeout(1500)
        ap.get_by_role("button", name="Approve", exact=True).click(); ap.wait_for_timeout(1500)
    for _ in range(40):
        if http.get(f"/api/v1/cases/{case_id}", headers=h).json()["status"] in ("resolved", "closed"): break
        time.sleep(2)
    ops.goto(f"{WEB}/app/cases/{case_id}"); ops.wait_for_timeout(2500)
    ops.get_by_role("tab", name="Actions & approvals").click(); ops.wait_for_timeout(1500)
    snap(ops, "s5", "4", "Approved, executed and verified; every step is written to a tamper-evident audit chain")

    ops.goto(f"{WEB}/app"); ops.wait_for_timeout(3500)
    snap(ops, "s6", "✓", "Every workflow run, approval and sign-in on record in one live command center")
    b.close()
print("case", case_id)
