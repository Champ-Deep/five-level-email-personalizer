from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase): ...


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("email", "brand", name="uq_leads_email_brand"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), default="lead_magnet")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_email: Mapped[str | None] = mapped_column(String(320), index=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total: Mapped[int] = mapped_column(default=0)
    done: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # When the user uploaded an Excel file, we stash the filename here and
    # the bytes in Redis (key `job:{id}:source_excel`, 7-day TTL). Keeping
    # binary blobs out of Postgres is a deliberate choice.
    source_filename: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_email: Mapped[str | None] = mapped_column(String(320), index=True)
    brand: Mapped[str | None] = mapped_column(String(80), index=True, default=None)
    scopes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    rate_limit_per_day: Mapped[int] = mapped_column(default=1000)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("idem_key", "api_key_id", name="uq_idem_key_api_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idem_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status_code: Mapped[int] = mapped_column(default=200)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSONB, default=list)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(80), index=True)
    active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/delivered/failed
    attempts: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_status: Mapped[int | None] = mapped_column()
    response_body: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntegrationCredential(Base):
    """Stored credentials for a third-party connector (Instantly, ChampMail,
    ChampIQ webhook target, etc.). Sensitive values inside `config` are
    Fernet-encrypted at rest using a key derived from JWT_SECRET.
    """
    __tablename__ = "integration_credentials"
    __table_args__ = (UniqueConstraint("owner_email", "provider", "label", name="uq_integration_owner_provider_label"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # "instantly" | "champmail" | "champiq"
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    config_encrypted: Mapped[str] = mapped_column(String(4000), nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PersonalizationRun(Base):
    """Every successful /v1/personalize call by an authenticated caller.

    Anonymous (no user/api-key) calls are NOT persisted.
    Powers the /v1/history UI: browse / replay / track outcomes.
    """
    __tablename__ = "personalization_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Owner is either a user_id (for JWT auth) or an api_key_id (for API key auth).
    # We store both as strings on `owner_sub` (mirrors TokenSubject.sub) for one-field indexing.
    owner_sub: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    owner_kind: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "api_key"
    brand: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    prospect_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    prospect_title: Mapped[str] = mapped_column(String(200), nullable=False)
    prospect_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sender_company: Mapped[str | None] = mapped_column(String(200))
    sender_name: Mapped[str | None] = mapped_column(String(200))
    tone_preset: Mapped[str | None] = mapped_column(String(40))
    style_rules: Mapped[str | None] = mapped_column(String(2000))
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    picked_slot: Mapped[str | None] = mapped_column(String(8))  # nullable; user can update later
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SavedSender(Base):
    """A user-saved sender/offer preset. Quick-pick instead of re-typing
    "Deep at LakeB2B / data intelligence …" every personalization run.
    """
    __tablename__ = "saved_senders"
    __table_args__ = (UniqueConstraint("owner_email", "label", name="uq_saved_sender_owner_label"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    offer: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_model: Mapped[str] = mapped_column(String(120), nullable=False)
    baseline_model: Mapped[str] = mapped_column(String(120), nullable=False)
    mean_score: Mapped[float | None] = mapped_column()
    baseline_mean: Mapped[float | None] = mapped_column()
    percent_of_baseline: Mapped[float | None] = mapped_column()
    per_level: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
