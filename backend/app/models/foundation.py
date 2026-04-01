from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import (
    ActiveFlagMixin,
    AssignmentTargetType,
    TimestampMixin,
    enum_column,
    jsonb_column,
    money_column,
    uuid_pk,
)


class Organization(Base, TimestampMixin, ActiveFlagMixin):
    __tablename__ = "organizations"

    organization_id = uuid_pk()
    organization_name = Column(String(255), nullable=False, index=True)
    primary_contact_email = Column(String(255), nullable=False)
    tax_id = Column(String(100))

    users = relationship("User", back_populates="organization")
    cost_centers = relationship("CostCenter", back_populates="organization")
    policy_configs = relationship("PolicyConfig", back_populates="organization")
    passengers = relationship("Passenger", back_populates="organization")
    orders = relationship("Order", back_populates="organization")
    approval_requests = relationship("ApprovalRequest", back_populates="organization")
    audit_logs = relationship("AuditLog", back_populates="organization")
    ai_sessions = relationship("AISession", back_populates="organization")


class Role(Base, ActiveFlagMixin):
    __tablename__ = "roles"

    role_id = uuid_pk()
    role_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    users = relationship("User", back_populates="role")
    approval_logs = relationship("ApprovalWorkflowLog", back_populates="approver_role")


class CostCenter(Base, TimestampMixin, ActiveFlagMixin):
    __tablename__ = "cost_centers"

    cost_center_id = uuid_pk()
    organization_id = Column(
        ForeignKey("organizations.organization_id"),
        nullable=False,
        index=True,
    )
    cost_center_name = Column(String(255), nullable=False)
    cost_center_code = Column(String(100), nullable=False)
    budget_limit = money_column()

    organization = relationship("Organization", back_populates="cost_centers")
    users = relationship("User", back_populates="cost_center")
    policy_assignments = relationship("PolicyAssignment", back_populates="cost_center")


class PolicyConfig(Base, ActiveFlagMixin):
    __tablename__ = "policy_configs"

    policy_id = uuid_pk()
    organization_id = Column(
        ForeignKey("organizations.organization_id"),
        nullable=False,
        index=True,
    )
    policy_name = Column(String(255), nullable=False)
    policy_description = Column(Text)
    rules = jsonb_column(nullable=False)
    rule_version = Column(String(50), nullable=False)
    effective_from = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="policy_configs")
    assignments = relationship("PolicyAssignment", back_populates="policy")


class PolicyAssignment(Base):
    __tablename__ = "policy_assignments"

    assignment_id = uuid_pk()
    policy_id = Column(ForeignKey("policy_configs.policy_id"), nullable=False, index=True)
    user_id = Column(ForeignKey("users.user_id"), nullable=True, index=True)
    cost_center_id = Column(ForeignKey("cost_centers.cost_center_id"), nullable=True, index=True)
    assigned_to_type = enum_column(AssignmentTargetType, nullable=False)
    assignment_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    assigned_by_user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    notes = Column(Text)

    policy = relationship("PolicyConfig", back_populates="assignments")
    user = relationship("User", foreign_keys=[user_id])
    cost_center = relationship("CostCenter", back_populates="policy_assignments")
    assigned_by_user = relationship(
        "User",
        back_populates="policy_assignments",
        foreign_keys=[assigned_by_user_id],
    )
