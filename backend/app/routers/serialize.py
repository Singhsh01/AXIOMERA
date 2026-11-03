from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import inspect


def to_dict(obj: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    if obj is None:
        return None  # type: ignore[return-value]
    out = {}
    for col in inspect(obj).mapper.column_attrs:
        if exclude and col.key in exclude:
            continue
        v = getattr(obj, col.key)
        out[col.key] = v.isoformat() if isinstance(v, datetime) else v
    return out
