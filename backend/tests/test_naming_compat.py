"""The product was renamed from Orkestr to Axiomera. These tests pin the backwards compatibility that
keeps existing deployments, sessions and in-flight n8n executions working (see docs/naming-audit.md)."""
from __future__ import annotations

import os

from app.core import naming


def test_legacy_env_names_are_used_when_new_ones_are_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("AXIOMERA_JIRA_PROJECT_KEY", raising=False)
    monkeypatch.setenv("ORKESTR_JIRA_PROJECT_KEY", "LEGACY")
    env_file = tmp_path / ".env"
    env_file.write_text("ORKESTR_HUBSPOT_TOKEN=from-file  # comment\nAXIOMERA_SLACK_WEBHOOK_URL=new\nORKESTR_SLACK_WEBHOOK_URL=old\n")
    monkeypatch.delenv("AXIOMERA_HUBSPOT_TOKEN", raising=False)
    used = naming.apply_legacy_env(env_file)
    assert os.environ["AXIOMERA_JIRA_PROJECT_KEY"] == "LEGACY"
    assert os.environ["AXIOMERA_HUBSPOT_TOKEN"] == "from-file"
    assert "ORKESTR_SLACK_WEBHOOK_URL" not in used           # the new name wins when both are present
    assert {"ORKESTR_JIRA_PROJECT_KEY", "ORKESTR_HUBSPOT_TOKEN"} <= set(used)
    monkeypatch.delenv("AXIOMERA_HUBSPOT_TOKEN", raising=False)


def test_new_env_name_wins_over_legacy(monkeypatch):
    monkeypatch.setenv("AXIOMERA_JIRA_EMAIL", "new@example.com")
    monkeypatch.setenv("ORKESTR_JIRA_EMAIL", "old@example.com")
    naming.apply_legacy_env("/nonexistent/.env")
    assert os.environ["AXIOMERA_JIRA_EMAIL"] == "new@example.com"


def test_legacy_service_token_header_is_accepted(client):
    legacy = {"X-Orkestr-Service-Token": "dev-service-token", "X-N8N-Execution-Id": "legacy-exec", "X-Orkestr-Workflow": "A", "X-Orkestr-Node": "Classify"}
    assert client.get("/api/v1/workflows", headers=legacy).status_code == 200
    assert client.get("/api/v1/workflows", headers={"X-Orkestr-Service-Token": "wrong"}).status_code == 401
    assert client.get("/api/v1/workflows", headers={"X-Axiomera-Service-Token": "dev-service-token"}).status_code == 200


def test_session_cookie_new_and_legacy(client):
    r = client.post("/api/v1/auth/login", json={"email": "viewer@axiomera.dev", "password": "axiomera-demo"})
    assert naming.SESSION_COOKIE in r.cookies
    token = r.json()["token"]
    client.cookies.clear()
    client.cookies.set(naming.LEGACY_SESSION_COOKIE, token)
    assert client.get("/api/v1/auth/me").status_code == 200       # a pre-rename session keeps working
    client.cookies.clear()


def test_signed_calls_to_n8n_carry_new_and_legacy_headers():
    h = naming.signature_headers("1700000000", "abc")
    assert h["X-Axiomera-Signature"] == h["X-Orkestr-Signature"] == "abc"
    assert h["X-Axiomera-Timestamp"] == h["X-Orkestr-Timestamp"] == "1700000000"


def test_webhook_paths_use_the_new_namespace():
    from app.platform.workflows import CATALOG
    paths = [m["path"] for m in CATALOG.values() if m.get("path")]
    assert len(paths) == 5 and all(p.startswith("axiomera/") for p in paths)
