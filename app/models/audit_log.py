"""Audit log database model."""
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, JSON

from app.database.connection import Base


class AuditLog(Base):
    """Stores who did what and when for security-sensitive actions."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
