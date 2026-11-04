"""Product naming and backwards compatibility with the former name, Orkestr.

Everything external uses the Axiomera names: ``AXIOMERA_*`` settings, ``X-Axiomera-*`` headers, the
``axiomera_session`` cookie and ``axiomera/*`` n8n webhook paths. Deployments set up before the rename
keep working because the legacy forms are still accepted:

* ``ORKESTR_*`` environment variables (and ``.env`` entries) are used when the ``AXIOMERA_*`` variable
  is absent, and a deprecation warning lists them at startup;
* ``X-Orkestr-*`` request headers are accepted, and the API still *sends* the legacy signature headers
  next to the new ones so n8n executions that started before the upgrade can resume;
* a session cookie named ``orkestr_token`` is still read (and cleared on logout).

See docs/naming-audit.md for the full inventory and the identifiers deliberately left unchanged.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

PREFIX = "AXIOMERA_"
LEGACY_PREFIX = "ORKESTR_"

HEADER_PREFIX = "X-Axiomera-"
LEGACY_HEADER_PREFIX = "X-Orkestr-"

SESSION_COOKIE = "axiomera_session"
LEGACY_SESSION_COOKIE = "orkestr_token"

WEBHOOK_NAMESPACE = "axiomera"

_legacy_env_used: list[str] = []


def apply_legacy_env(env_file: str | os.PathLike = ".env") -> list[str]:
    """Map ORKESTR_* settings onto AXIOMERA_* where the new name is not set. Returns the legacy keys used."""
    found: dict[str, str] = {k: v for k, v in os.environ.items() if k.startswith(LEGACY_PREFIX)}
    path = Path(env_file)
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            if key.startswith(LEGACY_PREFIX) and key not in found:
                found[key] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    used = []
    for key, value in found.items():
        new = PREFIX + key[len(LEGACY_PREFIX):]
        if new not in os.environ and not _defined_in(path, new):
            os.environ[new] = value
            used.append(key)
    _legacy_env_used[:] = sorted(set(_legacy_env_used) | set(used))
    return used


def _defined_in(path: Path, key: str) -> bool:
    if not path.is_file():
        return False
    return any(l.strip().removeprefix("export ").startswith(key + "=") for l in path.read_text(encoding="utf-8", errors="ignore").splitlines())


def warn_legacy_env(log: logging.Logger) -> None:
    if _legacy_env_used:
        log.warning("Deprecated ORKESTR_* settings in use; rename them to AXIOMERA_*: %s", ", ".join(_legacy_env_used))


def header(headers, name: str) -> str | None:
    """Value of X-Axiomera-<name>, falling back to the legacy X-Orkestr-<name>."""
    return headers.get(HEADER_PREFIX + name) or headers.get(LEGACY_HEADER_PREFIX + name)


def signature_headers(ts: str, sig: str) -> dict[str, str]:
    """Headers for signed calls to n8n. The legacy names are sent too, so executions created by
    workflow versions from before the rename still verify when they resume."""
    return {
        HEADER_PREFIX + "Timestamp": ts, HEADER_PREFIX + "Signature": sig,
        LEGACY_HEADER_PREFIX + "Timestamp": ts, LEGACY_HEADER_PREFIX + "Signature": sig,
    }
