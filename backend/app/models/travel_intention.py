from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base
from app.models.base import uuid_pk


class TravelIntention(Base):
    """
    Confirmed trip intention written at the end of Step 3.
    Maps to the existing `travel_intentions` table.
    """
    __tablename__ = "travel_intentions"

    intention_id    = uuid_pk()
    session_id      = Column(String(255), nullable=False, index=True)
    user_id         = Column(UUID(as_uuid=True), nullable=True, index=True)

    destination_raw = Column(String(255), nullable=False)  # surface form from slot state
    destination_qid = Column(String(50),  nullable=True)   # Wikidata QID if resolved

    duration        = Column(String(100), nullable=False)
    group_size      = Column(String(100), nullable=False)
    budget          = Column(String(100), nullable=False)  # luxury | mid-range | budget
    travel_style    = Column(String(100), nullable=True)   # beach | culture | adventure | food | nature

    created_at      = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
