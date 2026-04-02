from sqlalchemy import Column, ForeignKey, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import ActiveFlagMixin, TimestampMixin, jsonb_column, uuid_pk


class User(Base, TimestampMixin, ActiveFlagMixin):
    __tablename__ = "users"

    user_id = uuid_pk()
    organization_id = Column(
        ForeignKey("organizations.organization_id"),
        nullable=False,
        index=True,
    )
    cost_center_id = Column(ForeignKey("cost_centers.cost_center_id"), nullable=True, index=True)
    role_id = Column(ForeignKey("roles.role_id"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    employee_id = Column(String(100))
    profile_metadata = jsonb_column()
    active_yn = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization = relationship("Organization", back_populates="users")
    cost_center = relationship("CostCenter", back_populates="users")
    role = relationship("Role", back_populates="users")
    policy_assignments = relationship(
        "PolicyAssignment",
        back_populates="assigned_by_user",
        foreign_keys="PolicyAssignment.assigned_by_user_id",
    )
    ai_sessions = relationship("AISession", back_populates="user")
    state_machine_logs = relationship("StateMachineLog", back_populates="user")
    itinerary_headers = relationship("ItineraryHeader", back_populates="created_by_user")
    finalized_orders = relationship(
        "Order",
        back_populates="finalized_by_user",
        foreign_keys="Order.finalized_by_user_id",
    )
    approval_requests = relationship(
        "ApprovalRequest",
        back_populates="requested_by_user",
        foreign_keys="ApprovalRequest.requested_by_user_id",
    )
    approval_workflow_steps = relationship(
        "ApprovalWorkflowLog",
        back_populates="approver_user",
        foreign_keys="ApprovalWorkflowLog.approver_user_id",
    )
    audit_logs = relationship("AuditLog", back_populates="performed_by_user")
    passenger_profiles = relationship("Passenger", back_populates="user")


__all__ = ["User"]
