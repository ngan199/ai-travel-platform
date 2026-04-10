from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY

from app.db.base_class import Base


class Destination(Base):
    __tablename__ = "destinations"

    wikidata_id     = Column(String, primary_key=True)           # e.g. "Q884"
    name            = Column(String, nullable=False)             # e.g. "South Korea"
    entity_type     = Column(String, nullable=False)             # "country" | "city" | "region"
    country_qid     = Column(String, nullable=True)              # parent country Q-ID (null for countries)
    aliases         = Column(ARRAY(String), default=[])          # ["Korea", "ROK", "Republic of Korea"]
    description     = Column(Text, nullable=True)                # 1-3 sentence Wikipedia summary
    wikipedia_title = Column(String, nullable=True)              # "South_Korea"
    sitelink_count  = Column(Integer, default=0)                 # Wikipedia popularity proxy
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
