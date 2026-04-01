from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.base import (
    PlanningState,
    SessionStatus,
    SnapshotItemType,
    TimestampMixin,
    enum_column,
    jsonb_column,
    money_column,
    uuid_pk,
)


class AISession(Base):
    __tablename__ = "ai_sessions"

    session_id = uuid_pk()
    user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    organization_id = Column(ForeignKey("organizations.organization_id"), nullable=False, index=True)
    session_status = enum_column(SessionStatus, nullable=False, default=SessionStatus.ACTIVE)
    current_state = enum_column(PlanningState, nullable=False, default=PlanningState.PLANNING)
    current_state_machine_log_id = Column(
        ForeignKey("state_machine_logs.log_id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="ai_sessions")
    organization = relationship("Organization", back_populates="ai_sessions")
    state_machine_logs = relationship(
        "StateMachineLog",
        back_populates="session",
        foreign_keys="StateMachineLog.session_id",
    )
    current_state_machine_log = relationship(
        "StateMachineLog",
        foreign_keys=[current_state_machine_log_id],
        post_update=True,
    )
    generated_snapshots = relationship("ItinerarySnapshot", back_populates="generated_by_session")


class StateMachineLog(Base):
    __tablename__ = "state_machine_logs"

    log_id = uuid_pk()
    user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    session_id = Column(ForeignKey("ai_sessions.session_id"), nullable=False, index=True)
    state_name = enum_column(PlanningState, nullable=False)
    state_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ai_prompt_snapshot = jsonb_column()
    ai_response_snapshot = jsonb_column()
    transition_parameters = jsonb_column()

    user = relationship("User", back_populates="state_machine_logs")
    session = relationship(
        "AISession",
        back_populates="state_machine_logs",
        foreign_keys=[session_id],
    )


class ItineraryHeader(Base, TimestampMixin):
    __tablename__ = "itinerary_headers"

    itinerary_id = uuid_pk()
    itinerary_name = Column(String(255), nullable=False)
    created_by_user_id = Column(ForeignKey("users.user_id"), nullable=True, index=True)
    current_state = Column(String(100), nullable=False, default="Draft")

    created_by_user = relationship("User", back_populates="itinerary_headers")
    snapshots = relationship(
        "ItinerarySnapshot",
        back_populates="itinerary",
        order_by="ItinerarySnapshot.version_number",
    )
    approval_requests = relationship("ApprovalRequest", back_populates="source_itinerary")
    orders = relationship("Order", back_populates="itinerary")


class ItinerarySnapshot(Base):
    __tablename__ = "itinerary_snapshots"

    snapshot_id = uuid_pk()
    itinerary_id = Column(ForeignKey("itinerary_headers.itinerary_id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    generated_by_session_id = Column(ForeignKey("ai_sessions.session_id"), nullable=True, index=True)
    snapshot_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_cost = money_column()
    policy_compliance_status = Column(String(100))
    snapshot_metadata = jsonb_column()

    itinerary = relationship("ItineraryHeader", back_populates="snapshots")
    generated_by_session = relationship("AISession", back_populates="generated_snapshots")
    items = relationship(
        "SnapshotItem",
        back_populates="snapshot",
        order_by="SnapshotItem.sequence",
        cascade="all, delete-orphan",
    )
    orders = relationship("Order", back_populates="source_snapshot")


class SnapshotItem(Base):
    __tablename__ = "snapshot_items"

    snapshot_item_id = uuid_pk()
    snapshot_id = Column(ForeignKey("itinerary_snapshots.snapshot_id"), nullable=False, index=True)
    item_type = enum_column(SnapshotItemType, nullable=False)
    sequence = Column(Integer, nullable=False)
    segment_data = jsonb_column(nullable=False)
    provider = Column(String(100))
    cost_snapshot = money_column()
    in_policy_yn = Column(Boolean, nullable=False, default=True, server_default="true")

    snapshot = relationship("ItinerarySnapshot", back_populates="items")
