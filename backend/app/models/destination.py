from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.db.base_class import Base


class Destination(Base):
    __tablename__ = "destinations"

    # ── Core identity ──────────────────────────────────────────────────────────
    wikidata_id       = Column(String, primary_key=True)          # e.g. "Q884"
    name              = Column(String, nullable=False)            # e.g. "South Korea"
    entity_type       = Column(String, nullable=False)            # "country" | "city" | "region"
    country_qid       = Column(String, nullable=True)             # parent country Q-ID (null for countries)
    aliases           = Column(ARRAY(String), default=[])         # ["Korea", "ROK", ...]
    description       = Column(Text, nullable=True)               # Wikipedia summary
    wikipedia_title   = Column(String, nullable=True)             # "South_Korea"
    sitelink_count    = Column(Integer, default=0)                # popularity proxy

    # ── Pass 4: Extended Wikidata ──────────────────────────────────────────────
    lat               = Column(Float, nullable=True)              # geographic latitude
    lon               = Column(Float, nullable=True)              # geographic longitude
    timezone          = Column(String, nullable=True)             # e.g. "Asia/Seoul"
    currency          = Column(String, nullable=True)             # e.g. "South Korean won"
    official_language = Column(String, nullable=True)             # e.g. "Korean"
    iso_code          = Column(String, nullable=True)             # ISO 3166-1 alpha-2 (countries)
    top_attractions   = Column(JSONB, nullable=True)              # [{name, qid, category}, ...]
    attraction_categories = Column(ARRAY(String), nullable=True)  # ["museum", "temple", ...]

    # ── Pass 5: Wikivoyage ─────────────────────────────────────────────────────
    wikivoyage_sections = Column(JSONB, nullable=True)
    # Keys: get_in, get_around, see, do, eat_overview, drink_overview,
    #       sleep_overview, stay_safe, respect, local_laws, practical_notes

    # ── Pass 6: Open-Meteo climate ─────────────────────────────────────────────
    climate           = Column(JSONB, nullable=True)
    # Keys: monthly_avg_temp (12 floats), monthly_avg_precipitation (12 floats),
    #       monthly_avg_humidity (12 floats), monthly_uv_index (12 floats),
    #       best_months ([1-12]), worst_months ([1-12]), rainy_season ([1-12]),
    #       avg_sea_temp (12 floats | null)

    # ── Pass 7: REST Countries ─────────────────────────────────────────────────
    rest_countries    = Column(JSONB, nullable=True)
    # Keys: currency_name, currency_code, languages, calling_code, capital,
    #       region, subregion, flag_emoji, population, borders

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
