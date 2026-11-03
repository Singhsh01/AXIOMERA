from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps

from fastapi import Header, HTTPException

from app.integrations.connectors import ConnectorError
from app.ops.state_machine import InvalidTransition
from app.platform.approvals import ApprovalError
from app.rfp.service import RfpError


@dataclass
class WfCtx:
    workflow: str | None
    node: str | None


def wf_ctx(x_orkestr_workflow: str | None = Header(default=None), x_orkestr_node: str | None = Header(default=None)) -> WfCtx:
    return WfCtx(x_orkestr_workflow, x_orkestr_node)


def map_errors(fn: Callable):
    """Translate domain exceptions into HTTP semantics n8n understands:
    503 = transient (retry), 4xx = permanent (do not retry; route to error handling)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ConnectorError as e:
            raise HTTPException(503 if e.transient else 502, str(e)) from e
        except ApprovalError as e:
            raise HTTPException(e.code, str(e)) from e
        except InvalidTransition as e:
            raise HTTPException(409, str(e)) from e
        except RfpError as e:
            raise HTTPException(e.code, str(e)) from e

    return wrapper


def not_found(obj, workspace_id: str, what: str):
    ws = getattr(obj, "workspace_id", None)
    if obj is None or (ws is not None and ws != workspace_id):
        raise HTTPException(404, f"{what} not found")
    return obj
