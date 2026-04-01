from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.models.base import (
    OrderStatus,
    ReservationStatus,
    SnapshotItemType,
    TimestampMixin,
    enum_column,
    jsonb_column,
    money_column,
    uuid_pk,
)


class Order(Base):
    __tablename__ = "orders"

    order_id = uuid_pk()
    organization_id = Column(ForeignKey("organizations.organization_id"), nullable=False, index=True)
    finalized_by_user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    source_snapshot_id = Column(
        ForeignKey("itinerary_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    itinerary_id = Column(ForeignKey("itinerary_headers.itinerary_id"), nullable=True, index=True)
    order_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_order_amount = money_column()
    order_status = enum_column(OrderStatus, nullable=False, default=OrderStatus.PENDING)
    payment_status = Column(String(100))

    organization = relationship("Organization", back_populates="orders")
    finalized_by_user = relationship(
        "User",
        back_populates="finalized_orders",
        foreign_keys=[finalized_by_user_id],
    )
    source_snapshot = relationship("ItinerarySnapshot", back_populates="orders")
    itinerary = relationship("ItineraryHeader", back_populates="orders")
    items = relationship(
        "OrderItem",
        back_populates="order",
        order_by="OrderItem.sequence",
        cascade="all, delete-orphan",
    )
    order_passengers = relationship("OrderPassenger", back_populates="order", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="order")
    approval_requests = relationship("ApprovalRequest", back_populates="target_order")
    audit_logs = relationship("AuditLog", back_populates="related_order")


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = uuid_pk()
    order_id = Column(ForeignKey("orders.order_id"), nullable=False, index=True)
    item_type = enum_column(SnapshotItemType, nullable=False)
    sequence = Column(Integer, nullable=False)
    cloned_segment_data = jsonb_column(nullable=False)
    provider = Column(String(100))
    cost_snapshot = money_column()
    in_policy_yn = Column(Boolean, nullable=False, default=True, server_default="true")

    order = relationship("Order", back_populates="items")
    reservations = relationship("Reservation", back_populates="order_item")


class Passenger(Base):
    __tablename__ = "passengers"

    passenger_id = uuid_pk()
    organization_id = Column(ForeignKey("organizations.organization_id"), nullable=False, index=True)
    user_id = Column(ForeignKey("users.user_id"), nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date)
    passport_number = Column(String(100))
    loyalty_program_info = jsonb_column()

    organization = relationship("Organization", back_populates="passengers")
    user = relationship("User", back_populates="passenger_profiles")
    order_links = relationship("OrderPassenger", back_populates="passenger", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="passenger")


class OrderPassenger(Base):
    __tablename__ = "order_passengers"

    order_id = Column(ForeignKey("orders.order_id"), primary_key=True)
    passenger_id = Column(ForeignKey("passengers.passenger_id"), primary_key=True)

    order = relationship("Order", back_populates="order_passengers")
    passenger = relationship("Passenger", back_populates="order_links")


class Reservation(Base, TimestampMixin):
    __tablename__ = "reservations"

    reservation_id = uuid_pk()
    order_id = Column(ForeignKey("orders.order_id"), nullable=False, index=True)
    order_item_id = Column(ForeignKey("order_items.order_item_id"), nullable=True, index=True)
    passenger_id = Column(ForeignKey("passengers.passenger_id"), nullable=True, index=True)
    supplier_booking_reference = Column(String(255), nullable=False)
    waitlist_status = enum_column(ReservationStatus, nullable=True)
    ticket_number = Column(String(100))
    check_in_date = Column(Date)
    check_out_date = Column(Date)
    amadeus_hotel_code = Column(String(100))
    notes = Column(Text)

    order = relationship("Order", back_populates="reservations")
    order_item = relationship("OrderItem", back_populates="reservations")
    passenger = relationship("Passenger", back_populates="reservations")
