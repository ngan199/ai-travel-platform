"""extend_destination_kb_fields

Revision ID: a1b2c3d4e5f6
Revises: f9681288e351
Create Date: 2026-04-17 00:00:00.000000

Adds enrichment columns to the destinations table:
  - Pass 4 (Extended Wikidata): lat, lon, timezone, currency, official_language,
                                iso_code, top_attractions, attraction_categories
  - Pass 5 (Wikivoyage):        wikivoyage_sections
  - Pass 6 (Open-Meteo):        climate
  - Pass 7 (REST Countries):    rest_countries
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f9681288e351'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pass 4 — Extended Wikidata
    op.add_column('destinations', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('destinations', sa.Column('lon', sa.Float(), nullable=True))
    op.add_column('destinations', sa.Column('timezone', sa.String(), nullable=True))
    op.add_column('destinations', sa.Column('currency', sa.String(), nullable=True))
    op.add_column('destinations', sa.Column('official_language', sa.String(), nullable=True))
    op.add_column('destinations', sa.Column('iso_code', sa.String(), nullable=True))
    op.add_column('destinations', sa.Column('top_attractions', postgresql.JSONB(), nullable=True))
    op.add_column('destinations', sa.Column('attraction_categories',
                                            postgresql.ARRAY(sa.String()), nullable=True))

    # Pass 5 — Wikivoyage
    op.add_column('destinations', sa.Column('wikivoyage_sections', postgresql.JSONB(), nullable=True))

    # Pass 6 — Open-Meteo
    op.add_column('destinations', sa.Column('climate', postgresql.JSONB(), nullable=True))

    # Pass 7 — REST Countries
    op.add_column('destinations', sa.Column('rest_countries', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('destinations', 'rest_countries')
    op.drop_column('destinations', 'climate')
    op.drop_column('destinations', 'wikivoyage_sections')
    op.drop_column('destinations', 'attraction_categories')
    op.drop_column('destinations', 'top_attractions')
    op.drop_column('destinations', 'iso_code')
    op.drop_column('destinations', 'official_language')
    op.drop_column('destinations', 'currency')
    op.drop_column('destinations', 'timezone')
    op.drop_column('destinations', 'lon')
    op.drop_column('destinations', 'lat')
