"""Static checks on the version-controlled n8n workflows: wiring, auth headers, retries, error workflow."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.platform.workflows import CATALOG, graph

WF_DIR = Path(__file__).resolve().parents[2] / "n8n" / "workflows"
FILES = sorted(WF_DIR.glob("*.json"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_workflow_wiring(path):
    wf = json.loads(path.read_text())
    names = {n["name"] for n in wf["nodes"]}
    assert len(names) == len(wf["nodes"]), "node names must be unique"
    for src, outs in wf["connections"].items():
        assert src in names
        for branch in outs["main"]:
            for c in branch:
                assert c["node"] in names, f"{src} → {c['node']}"
    if not wf["id"].startswith("OrkZ"):
        assert wf["settings"]["errorWorkflow"] == "OrkZ0ErrorHandler"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_api_calls_are_authenticated_and_retried(path):
    wf = json.loads(path.read_text())
    for n in wf["nodes"]:
        if n["type"] != "n8n-nodes-base.httpRequest":
            continue
        hdrs = {h["name"]: h["value"] for h in n["parameters"]["headerParameters"]["parameters"]}
        assert hdrs["X-Orkestr-Service-Token"] == "={{ $env.ORKESTR_SERVICE_TOKEN }}"
        assert hdrs["X-Orkestr-Node"] == n["name"], "node header must match node name for step correlation"
        assert hdrs["X-N8N-Execution-Id"] == "={{ $execution.id }}"
        assert n.get("retryOnFail") and n.get("maxTries", 0) >= 3
        assert n["parameters"]["options"]["timeout"] >= 30000


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_webhooks_verify_signatures(path):
    wf = json.loads(path.read_text())
    hooks = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.webhook"]
    for h in hooks:
        assert h["parameters"]["options"].get("rawBody") is True
        nxt = wf["connections"][h["name"]]["main"][0][0]["node"]
        assert nxt == "Verify Signature"
        code = next(n for n in wf["nodes"] if n["name"] == nxt)["parameters"]["jsCode"]
        assert "createHmac('sha256'" in code and "timingSafeEqual" in code


def test_catalog_matches_files():
    for key, meta in CATALOG.items():
        g = graph(key)
        assert g["nodes"] and (WF_DIR / meta["file"]).exists()
        if meta["path"]:
            wf = json.loads((WF_DIR / meta["file"]).read_text())
            assert any(n["type"] == "n8n-nodes-base.webhook" and n["parameters"]["path"] == meta["path"] for n in wf["nodes"])


def test_required_stages_present():
    def nodes(key):
        return {n["id"] for n in graph(key)["nodes"]}

    assert {"Create Case", "Classify", "Retrieve Evidence", "Propose Resolution", "Execute", "Verify", "Request Approval (Workflow E)"} <= nodes("A")
    assert {"Categorize", "Retrieve Context", "Assign Owner", "Create Jira Task", "Notify Slack", "Monitor SLA", "Escalate", "Close Resolved"} <= nodes("B")
    assert {"Validate & Store", "Extract Text", "Analyze Requirements", "Build Compliance Matrix", "Retrieve Evidence", "Generate Draft", "Request Review", "Export Draft"} <= nodes("C")
    assert {"Hourly Schedule", "Query Active RFPs", "Identify At-Risk Items", "Notify Owners", "Escalate"} <= nodes("D")
    assert {"Send Notification", "Wait for Authorized Decision", "Verify Identity and Scope", "Execute Approved Action", "Record Outcome"} <= nodes("E")
