from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OtpCode(Base):
    __tablename__ = "otp_codes"
    __table_args__ = (Index("idx_otp_email_created", "email", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String)
    role: Mapped[str | None] = mapped_column(String)
    support_level: Mapped[str | None] = mapped_column(String)
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String)
    first_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String)
    custom_fields: Mapped[dict | None] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Tag(Base):
    __tablename__ = "tags"

    tag_id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TagTypeMapping(Base):
    __tablename__ = "tag_type_mappings"

    tag_id: Mapped[str] = mapped_column(String, ForeignKey("tags.tag_id"), primary_key=True)
    type_label: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','PENDING','CLOSED','REJECTED','BLOCKED')", name="ck_ticket_status"
        ),
        Index("idx_tickets_status", "status"),
        Index("idx_tickets_type", "derived_type"),
        Index("idx_tickets_last_event", "last_event_at"),
        Index("idx_tickets_assigned", "assigned_agent_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    num: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    team: Mapped[str | None] = mapped_column(String)
    assigned_agent_id: Mapped[str | None] = mapped_column(String, ForeignKey("agents.id"))
    assigned_to_email: Mapped[str | None] = mapped_column(String)
    customer_id: Mapped[str | None] = mapped_column(String, ForeignKey("customers.id"))
    tags_cache: Mapped[list | None] = mapped_column(JSON)
    tag_ids_cache: Mapped[list | None] = mapped_column(JSON)
    derived_type: Mapped[str | None] = mapped_column(String)
    overwatch_status: Mapped[str | None] = mapped_column(String)
    ticket_custom_fields: Mapped[dict | None] = mapped_column(JSON)
    thread_total_events: Mapped[int | None] = mapped_column(Integer)
    thread_messages: Mapped[int | None] = mapped_column(Integer)
    thread_notes: Mapped[int | None] = mapped_column(Integer)
    thread_system_events: Mapped[int | None] = mapped_column(Integer)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at_trinity: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at_trinity: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    first_assigned_to_agent_at: Mapped[datetime | None] = mapped_column(DateTime)
    trinity_url: Mapped[str | None] = mapped_column(String)
    added_to_tracker_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sync_error: Mapped[str | None] = mapped_column(Text)


class TicketTag(Base):
    __tablename__ = "ticket_tags"

    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(String, ForeignKey("tags.tag_id"), primary_key=True)


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (
        CheckConstraint("type IN ('message','audit','note','ai_draft')", name="ck_event_type"),
        CheckConstraint("visibility IN ('public','internal') OR visibility IS NULL", name="ck_event_visibility"),
        CheckConstraint("direction IN ('inbound','outbound') OR direction IS NULL", name="ck_event_direction"),
        UniqueConstraint("ticket_id", "seq", name="uq_ticket_seq"),
        Index("idx_events_ticket_seq", "ticket_id", "seq"),
        Index("idx_events_type_action", "type", "action"),
        Index("idx_events_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id"), nullable=False)
    ticket_num: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    visibility: Mapped[str | None] = mapped_column(String)
    direction: Mapped[str | None] = mapped_column(String)
    action: Mapped[str | None] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String)
    author_email: Mapped[str | None] = mapped_column(String)
    attachments: Mapped[list | None] = mapped_column(JSON)
    mentions: Mapped[list | None] = mapped_column(JSON)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class StatusTransition(Base):
    __tablename__ = "status_transitions"
    __table_args__ = (
        Index("idx_st_date", "event_date"),
        Index("idx_st_close_date", "is_close", "event_date"),
        Index("idx_st_reopen_date", "is_reopen", "event_date"),
        Index("idx_st_ticket", "ticket_id", "seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id"), nullable=False)
    ticket_num: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("ticket_events.id"), unique=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    old_status: Mapped[str | None] = mapped_column(String)
    new_status: Mapped[str | None] = mapped_column(String)
    is_close: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_reopen: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_customer_triggered_reopen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    agent_email: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CsatEvent(Base):
    __tablename__ = "csat_events"
    __table_args__ = (
        CheckConstraint("action IN ('csat_sent','csat_cancelled')", name="ck_csat_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id"), nullable=False)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("ticket_events.id"), unique=True, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    close_cycle_index: Mapped[int | None] = mapped_column(Integer)
    csat_survey_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TicketDuplicate(Base):
    __tablename__ = "ticket_duplicates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id"), nullable=False)
    duplicate_of_num: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_from_event_id: Mapped[str] = mapped_column(String, ForeignKey("ticket_events.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AssignmentEvent(Base):
    __tablename__ = "assignment_events"
    __table_args__ = (
        CheckConstraint("action IN ('assigned','unassigned')", name="ck_assignment_action"),
        Index("idx_ae_ticket_seq", "ticket_id", "seq"),
        Index("idx_ae_taken_date", "is_taken_from_tracked_agent", "event_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id"), nullable=False)
    ticket_num: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("ticket_events.id"), unique=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    old_assignee: Mapped[str | None] = mapped_column(String)
    new_assignee: Mapped[str | None] = mapped_column(String)
    is_gain_for_tracked_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_taken_from_tracked_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_system_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(String)
    performed_by_email: Mapped[str | None] = mapped_column(String)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LocalNote(Base):
    __tablename__ = "local_notes"
    __table_args__ = (Index("idx_local_notes_ticket", "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id"), nullable=False)
    agent_email: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class SyncState(Base):
    __tablename__ = "sync_state"

    scope: Mapped[str] = mapped_column(String, primary_key=True)
    last_full_backfill_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_incremental_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_incremental_sync_status: Mapped[str | None] = mapped_column(String)
    last_incremental_sync_error: Mapped[str | None] = mapped_column(Text)
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint(
            "run_type IN ('manual','scheduled','add_ticket','backfill')", name="ck_sync_run_type"
        ),
        CheckConstraint(
            "status IN ('running','success','partial_failure','error')", name="ck_sync_run_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, nullable=False)
    tickets_checked: Mapped[int] = mapped_column(Integer, default=0)
    tickets_updated: Mapped[int] = mapped_column(Integer, default=0)
    events_ingested: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
