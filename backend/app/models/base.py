import enum
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Enum, MetaData, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB, UUID


class SessionStatus(str, enum.Enum):
    ACTIVE = "Active"
    COMPLETE = "Complete"
    PAUSED = "Paused"


class PlanningState(str, enum.Enum):
    PLANNING = "Planning"
    POLICY_CHECK = "Policy_Check"
    READY_TO_BOOK = "Ready_to_Book"


class AssignmentTargetType(str, enum.Enum):
    USER = "User"
    COST_CENTER = "Cost_Center"


class SnapshotItemType(str, enum.Enum):
    FLIGHT = "Flight"
    HOTEL = "Hotel"


class OrderStatus(str, enum.Enum):
    APPROVED = "Approved"
    BOOKED = "Booked"
    PENDING = "Pending"
    FINALIZED = "Finalized"
    TICKETED = "Ticketed"
    CANCELLED = "Cancelled"
    FAILED = "FAILED"


class ReservationStatus(str, enum.Enum):
    WAITLISTED = "Waitlisted"
    CANCELLED = "Cancelled"
    CONFIRMED = "Confirmed"
    FAILED = "Failed"


class ApprovalRequestType(str, enum.Enum):
    PRE_BOOKING = "Pre_Booking"
    POST_BOOKING = "Post_Booking"
    BLEISURE = "Bleisure"


class ApprovalRequestStatus(str, enum.Enum):
    SUBMITTED = "Submitted"
    IN_REVIEW = "In_Review"
    APPROVED = "Approved"
    DENIED = "Denied"
    CANCELLED = "Cancelled"


class ApprovalDecision(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    DENIED = "Denied"
    SKIPPED = "Skipped"


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ActiveFlagMixin:
    active_yn = Column(Boolean, nullable=False, default=True, server_default="true")


def enum_column(enum_cls, *, nullable: bool = False, default=None):
    kwargs = {"nullable": nullable}
    if default is not None:
        kwargs["default"] = default
    return Column(
        Enum(
            enum_cls,
            name=f"{enum_cls.__name__.lower()}_enum",
            values_callable=lambda enum_values: [item.value for item in enum_values],
        ),
        **kwargs,
    )


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid4)


def jsonb_column(nullable: bool = True):
    return Column(JSONB, nullable=nullable)


def money_column(nullable: bool = True):
    return Column(Numeric(12, 2), nullable=nullable)
