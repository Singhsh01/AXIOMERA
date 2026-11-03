from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Notification


def notify(db: Session, workspace_id: str, title: str, body: str = "", *, severity: str = "info",
           link: str | None = None, user_id: str | None = None, channel: str = "in_app") -> Notification:
    n = Notification(workspace_id=workspace_id, title=title[:300], body=body, severity=severity, link=link,
                     user_id=user_id, channel=channel)
    db.add(n)
    db.flush()
    return n
