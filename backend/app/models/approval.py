from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.base import (
    ApprovalDecision,
    ApprovalRequestStatus,
    ApprovalRequestType,
    jsonb_column,
    enum_column,
    uuid_pk,
)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    request_id = uuid_pk()
    organization_id = Column(ForeignKey("organizations.organization_id"), nullable=False, index=True)
    source_itinerary_id = Column(
        ForeignKey("itinerary_headers.itinerary_id"),
        nullable=True,
        index=True,
    )
    target_order_id = Column(ForeignKey("orders.order_id"), nullable=True, index=True)
    request_type = enum_column(ApprovalRequestType, nullable=False)
    requested_by_user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    request_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    request_status = enum_column(
        ApprovalRequestStatus,
        nullable=False,
        default=ApprovalRequestStatus.SUBMITTED,
    )
    decision_reason = Column(Text)

    organization = relationship("Organization", back_populates="approval_requests")
    source_itinerary = relationship("ItineraryHeader", back_populates="approval_requests")
    target_order = relationship("Order", back_populates="approval_requests")
    requested_by_user = relationship(
        "User",
        back_populates="approval_requests",
        foreign_keys=[requested_by_user_id],
    )
    workflow_logs = relationship(
        "ApprovalWorkflowLog",
        back_populates="request",
        order_by="ApprovalWorkflowLog.step_sequence",
        cascade="all, delete-orphan",
    )
    audit_logs = relationship("AuditLog", back_populates="related_approval_request")


class ApprovalWorkflowLog(Base):
    __tablename__ = "approval_workflow_logs"

    log_id = uuid_pk()
    request_id = Column(ForeignKey("approval_requests.request_id"), nullable=False, index=True)
    step_sequence = Column(Integer, nullable=False)
    approver_user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    approver_role_id = Column(ForeignKey("roles.role_id"), nullable=True, index=True)
    status = enum_column(ApprovalDecision, nullable=False, default=ApprovalDecision.PENDING)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approver_comment = Column(Text)
    approval_level = Column(String(100))

    request = relationship("ApprovalRequest", back_populates="workflow_logs")
    approver_user = relationship(
        "User",
        back_populates="approval_workflow_steps",
        foreign_keys=[approver_user_id],
    )
    approver_role = relationship("Role", back_populates="approval_logs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_log_id = uuid_pk()
    organization_id = Column(ForeignKey("organizations.organization_id"), nullable=False, index=True)
    related_approval_request_id = Column(
        ForeignKey("approval_requests.request_id"),
        nullable=True,
        index=True,
    )
    related_order_id = Column(ForeignKey("orders.order_id"), nullable=True, index=True)
    performed_by_user_id = Column(ForeignKey("users.user_id"), nullable=True, index=True)
    action_name = Column(String(255), nullable=False)
    old_values_snapshot = jsonb_column()
    new_values_snapshot = jsonb_column()
    ai_context_prompt_snapshot = jsonb_column()
    compliance_notes = Column(Text)

    organization = relationship("Organization", back_populates="audit_logs")
    related_approval_request = relationship("ApprovalRequest", back_populates="audit_logs")
    related_order = relationship("Order", back_populates="audit_logs")
    performed_by_user = relationship("User", back_populates="audit_logs")
