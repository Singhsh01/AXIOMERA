#!/usr/bin/env python3
"""Send a signed event to an Orkestr n8n webhook (the same way an email bridge or monitoring system would).

Usage:
  python scripts/send_event.py intake  '{"message_id":"m-1","from":"anna.weber@example.com","subject":"Refund","body":"..."}'
  python scripts/send_event.py incident '{"event_id":"alrt-1","title":"API 503s","description":"..."}'
  python scripts/send_event.py deadline-scan '{}'
Env: N8N_URL (default http://localhost:5678), ORKESTR_WEBHOOK_SECRET (default dev-webhook-secret)
"""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request

PATHS = {"intake": "orkestr/intake", "incident": "orkestr/incident", "rfp": "orkestr/rfp-arrived", "deadline-scan": "orkestr/deadline-scan"}


def send(kind: str, payload: dict, secret: str | None = None, tamper: bool = False) -> tuple[int, str]:
    base = os.environ.get("N8N_URL", "http://localhost:5678")
    secret = secret or os.environ.get("ORKESTR_WEBHOOK_SECRET", "dev-webhook-secret")
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    if tamper:
        sig = "0" * 64
    req = urllib.request.Request(f"{base}/webhook/{PATHS[kind]}", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Orkestr-Timestamp": ts, "X-Orkestr-Signature": sig})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


if __name__ == "__main__":
    status, text = send(sys.argv[1], json.loads(sys.argv[2]), tamper="--tamper" in sys.argv)
    print(status, text)
