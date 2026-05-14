"""Audit logging service."""
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.audit_log import AuditLog


class AuditService:
    """Write security-relevant events to PostgreSQL audit_logs."""

    def __init__(self, db: Session):
        self.db = db

    def log_action(
        self,
        action: str,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            entry = AuditLog(
                action=action,
                user_id=user_id,
                email=email,
                ip_address=ip_address,
                details=details,
            )
            self.db.add(entry)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to write audit log '{action}': {exc}")
