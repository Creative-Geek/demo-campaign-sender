# app/models.py
"""Database models for the campaign sender."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft | sending | sent | failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    email = Column(String(320), nullable=False)


class SendLog(Base):
    __tablename__ = "send_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    recipient_email = Column(String(320), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending | sent | failed
    error = Column(Text, nullable=True)
    idempotency_key = Column(String(500), nullable=False, unique=True)
    sent_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_send_log_idempotency"),
    )
