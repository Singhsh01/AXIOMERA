"""Structured logging, Prometheus metrics and optional OpenTelemetry tracing."""
from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar

from prometheus_client import CollectorRegistry, Counter, Histogram

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

REGISTRY = CollectorRegistry(auto_describe=True)
HTTP_REQUESTS = Counter("axiomera_http_requests_total", "HTTP requests", ["method", "route", "status"], registry=REGISTRY)
HTTP_LATENCY = Histogram("axiomera_http_request_seconds", "HTTP latency", ["route"], registry=REGISTRY)
WORKFLOW_STEPS = Counter("axiomera_workflow_steps_total", "Workflow steps reported", ["workflow", "status"], registry=REGISTRY)
AGENT_RUNS = Counter("axiomera_agent_runs_total", "Agent runs", ["agent", "status"], registry=REGISTRY)
AGENT_LATENCY = Histogram("axiomera_agent_run_seconds", "Agent run latency", ["agent"], registry=REGISTRY)
LLM_TOKENS = Counter("axiomera_llm_tokens_total", "LLM tokens", ["provider", "direction"], registry=REGISTRY)
TOOL_CALLS = Counter("axiomera_tool_calls_total", "Tool calls", ["tool", "status"], registry=REGISTRY)
APPROVALS = Counter("axiomera_approvals_total", "Approval decisions", ["action_type", "decision"], registry=REGISTRY)
DUPLICATES = Counter("axiomera_duplicate_events_total", "Duplicate inbound events suppressed", ["source"], registry=REGISTRY)
INTEGRATION_CALLS = Counter("axiomera_integration_calls_total", "Integration calls", ["connector", "mode", "status"], registry=REGISTRY)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        cid = correlation_id_var.get()
        if cid:
            payload["correlation_id"] = cid
        for key in ("event", "entity", "workflow", "agent", "n8n_execution_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel("WARNING")


def setup_tracing(app, endpoint: str | None) -> bool:
    """Enable OpenTelemetry if the SDK is installed. Exports via OTLP when an endpoint is set,
    otherwise spans are only created (useful for local correlation without a collector)."""
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:  # pragma: no cover
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": "axiomera-api"}))
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
        except ImportError:  # pragma: no cover
            logging.getLogger(__name__).warning("OTLP exporter not installed; spans not exported")
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    return True


def tracer():
    try:
        from opentelemetry import trace

        return trace.get_tracer("axiomera")
    except ImportError:  # pragma: no cover
        return None
