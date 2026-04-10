"""
Destination Knowledge Base population script.

Runs on first seed and as a monthly refresh (via APScheduler).
Can also be invoked directly:
    python scripts/build_kb.py

Three passes:
  1. Countries  — SPARQL (Wikidata), aliases enriched via entity API
  2. Cities     — SPARQL (Wikidata, top 600 by sitelinks), same enrichment
  3. Regions    — Curated list via Wikidata entity API

?itemAltLabel is intentionally excluded from SPARQL queries — it causes
504 timeouts on Wikidata's endpoint. Aliases are fetched separately via
the Wikidata entity API in batches of 50 (wbgetentities).
"""

from __future__ import annotations

import logging
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from SPARQLWrapper import JSON, SPARQLWrapper
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

# ── make "scripts/" runnable as a standalone module ──────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.models.destination import Destination
from scripts.curated_regions import CURATED_REGIONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_ALIAS_BATCH_SIZE = 50  # Wikidata API accepts up to 50 IDs per request

# ── SPARQL queries (no ?itemAltLabel — avoids 504 timeouts) ──────────────────

_COUNTRY_SPARQL = """
SELECT DISTINCT ?item ?itemLabel ?sitelinks ?wpTitle
WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q6256 .
  ?article schema:about ?item ;
           schema:isPartOf <https://en.wikipedia.org/> ;
           schema:name ?wpTitle .
  ?item wikibase:sitelinks ?sitelinks .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
ORDER BY DESC(?sitelinks)
LIMIT {limit} OFFSET {offset}
"""

_CITY_SPARQL = """
SELECT DISTINCT ?item ?itemLabel ?sitelinks ?wpTitle ?country
WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q515 .
  ?article schema:about ?item ;
           schema:isPartOf <https://en.wikipedia.org/> ;
           schema:name ?wpTitle .
  ?item wikibase:sitelinks ?sitelinks .
  OPTIONAL {{ ?item wdt:P17 ?country . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
ORDER BY DESC(?sitelinks)
LIMIT {limit} OFFSET {offset}
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {"User-Agent": settings.KB_BUILD_USER_AGENT}


def _extract_qid(uri: str) -> str:
    return uri.split("/")[-1]


def _sparql_fetch_all(query_template: str, limit: int, max_rows: int) -> list[dict]:
    """Paginate a SPARQL query, sleeping between pages. Returns all bindings."""
    sparql = SPARQLWrapper(settings.WIKIDATA_SPARQL_ENDPOINT)
    sparql.addCustomHttpHeader("User-Agent", settings.KB_BUILD_USER_AGENT)
    sparql.setReturnFormat(JSON)

    all_rows: list[dict] = []
    offset = 0

    while len(all_rows) < max_rows:
        sparql.setQuery(query_template.format(limit=limit, offset=offset))
        try:
            results = sparql.query().convert()
        except Exception as exc:
            logger.warning("SPARQL request failed at offset %d: %s", offset, exc)
            break
        
        bindings = results.get("results", {}).get("bindings", [])
        if not bindings:
            break

        all_rows.extend(bindings)
        logger.info("  fetched %d rows (offset=%d)", len(all_rows), offset)

        if len(bindings) < limit:
            break  # last page

        offset += limit
        time.sleep(settings.KB_SPARQL_SLEEP_SECONDS)
        
    return all_rows


def _aggregate_by_qid(rows: list[dict], entity_type: str) -> list[dict]:
    """
    Deduplicate SPARQL rows by Q-ID. Aliases are NOT set here —
    they are filled later by _enrich_with_aliases().
    """
    entities: dict[str, dict] = {}

    for row in rows:
        qid = _extract_qid(row["item"]["value"])
        name = row.get("itemLabel", {}).get("value", "")
        wp_title = row.get("wpTitle", {}).get("value")
        sitelinks = int(row.get("sitelinks", {}).get("value", 0))
        country_uri = row.get("country", {}).get("value")
        country_qid = _extract_qid(country_uri) if country_uri else None

        # Skip auto-generated labels like "Q12345"
        if not name or name.startswith("Q"):
            continue

        if qid not in entities:
            entities[qid] = {
                "wikidata_id":     qid,
                "name":            name,
                "entity_type":     entity_type,
                "country_qid":     country_qid if entity_type != "country" else qid,
                "wikipedia_title": wp_title,
                "sitelink_count":  sitelinks,
                "aliases":         [],
                "description":     None,
            }
        elif sitelinks > entities[qid]["sitelink_count"]:
            entities[qid]["sitelink_count"] = sitelinks

    return list(entities.values())


def _enrich_with_aliases(entities: list[dict]) -> list[dict]:
    """
    Batch-fetch English aliases from the Wikidata entity API (50 per request).
    Updates each entity dict in-place.
    """
    qid_to_entity = {e["wikidata_id"]: e for e in entities}
    qids = list(qid_to_entity.keys())
    total_batches = (len(qids) + _ALIAS_BATCH_SIZE - 1) // _ALIAS_BATCH_SIZE

    for i in range(0, len(qids), _ALIAS_BATCH_SIZE):
        batch = qids[i: i + _ALIAS_BATCH_SIZE]
        batch_num = i // _ALIAS_BATCH_SIZE + 1
        logger.info("  alias batch %d / %d (%d entities)", batch_num, total_batches, len(batch))

        try:
            resp = requests.get(
                settings.WIKIDATA_API_ENDPOINT,
                params={
                    "action":    "wbgetentities",
                    "ids":       "|".join(batch),
                    "languages": "en",
                    "props":     "aliases",
                    "format":    "json",
                },
                headers=_headers(),
                timeout=30,
            )
            resp.raise_for_status()
            raw_entities = resp.json().get("entities", {})
        except Exception as exc:
            logger.warning("Alias batch %d failed: %s", batch_num, exc)
            time.sleep(1)
            continue

        for qid, raw in raw_entities.items():
            entity = qid_to_entity.get(qid)
            if not entity or raw.get("missing") == "":
                continue

            raw_aliases = [
                a["value"] for a in raw.get("aliases", {}).get("en", [])
                if a.get("value")
            ]
            seen: set[str] = set()
            clean: list[str] = []
            name_lower = entity["name"].lower()
            for alias in raw_aliases:
                key = alias.lower().strip()
                if key and key != name_lower and key not in seen:
                    seen.add(key)
                    clean.append(alias.strip())
            entity["aliases"] = clean

        time.sleep(0.5)  # gentle rate limit between batches

    return entities


def _fetch_wikipedia_description(title: str) -> str | None:
    encoded = urllib.parse.quote(title, safe="")
    url = f"{settings.WIKIPEDIA_API_ENDPOINT}/page/summary/{encoded}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        if resp.status_code == 404:
            logger.debug("Wikipedia 404: %s", title)
            return None
        resp.raise_for_status()
        return resp.json().get("extract") or None
    except Exception as exc:
        logger.warning("Wikipedia fetch failed for '%s': %s", title, exc)
        return None


def _enrich_with_descriptions(entities: list[dict]) -> list[dict]:
    total = sum(1 for e in entities if e.get("wikipedia_title"))
    fetched = failed = 0

    for entity in entities:
        title = entity.get("wikipedia_title")
        if not title:
            entity["description"] = None
            continue
        desc = _fetch_wikipedia_description(title)
        if desc:
            fetched += 1
        else:
            failed += 1
        entity["description"] = desc
        time.sleep(settings.KB_WIKIPEDIA_SLEEP_SECONDS)

    logger.info("  Wikipedia descriptions: %d / %d fetched (%d failed)", fetched, total, failed)
    return entities


# ── Pass 3 — curated regions ──────────────────────────────────────────────────

def _build_region_entities() -> list[dict]:
    entities: list[dict] = []
    errors: list[str] = []

    for qid, (canonical_name, country_qid) in CURATED_REGIONS.items():
        try:
            resp = requests.get(
                settings.WIKIDATA_API_ENDPOINT,
                params={
                    "action":    "wbgetentities",
                    "ids":       qid,
                    "languages": "en",
                    "props":     "labels|aliases|sitelinks",
                    "format":    "json",
                },
                headers=_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json().get("entities", {}).get(qid)
        except Exception as exc:
            logger.warning("Wikidata API error for '%s': %s", qid, exc)
            errors.append(qid)
            continue

        if not raw or raw.get("missing") == "":
            logger.warning("Wikidata 404 for Q-ID: %s", qid)
            errors.append(qid)
            continue

        en_label = raw.get("labels", {}).get("en", {}).get("value", canonical_name)

        raw_aliases = [
            a["value"] for a in raw.get("aliases", {}).get("en", [])
            if a.get("value")
        ]
        seen: set[str] = set()
        clean: list[str] = []
        name_lower = en_label.lower()
        for alias in raw_aliases:
            key = alias.lower().strip()
            if key and key != name_lower and key not in seen:
                seen.add(key)
                clean.append(alias.strip())

        wp_title = raw.get("sitelinks", {}).get("enwiki", {}).get("title")
        sitelink_count = len(raw.get("sitelinks", {}))

        entities.append({
            "wikidata_id":     qid,
            "name":            en_label,
            "entity_type":     "region",
            "country_qid":     country_qid,
            "aliases":         clean,
            "wikipedia_title": wp_title,
            "sitelink_count":  sitelink_count,
            "description":     None,
        })
        time.sleep(0.2)

    if errors:
        logger.warning("Curated regions with Wikidata errors (%d): %s", len(errors), errors)

    return entities


# ── upsert ────────────────────────────────────────────────────────────────────

def _upsert_entities(session: Session, entities: list[dict]) -> tuple[int, int]:
    if not entities:
        return 0, 0

    inserted = updated = 0
    for entity in entities:
        stmt = (
            insert(Destination)
            .values(**entity)
            .on_conflict_do_update(
                index_elements=["wikidata_id"],
                set_={
                    "name":           entity["name"],
                    "aliases":        entity["aliases"],
                    "description":    entity["description"],
                    "sitelink_count": entity["sitelink_count"],
                },
            )
        )
        result = session.execute(stmt)
        if result.rowcount and result.rowcount > 1:
            updated += 1
        else:
            inserted += 1

    session.commit()
    return inserted, updated


# ── validation ────────────────────────────────────────────────────────────────

def _validate(session: Session) -> None:
    from sqlalchemy import func, select

    total = session.execute(
        select(func.count()).select_from(Destination)
    ).scalar()
    no_desc = session.execute(
        select(func.count()).select_from(Destination).where(Destination.description.is_(None))
    ).scalar()
    few_aliases = session.execute(
        select(func.count()).select_from(Destination).where(
            func.array_length(Destination.aliases, 1) < 2
        )
    ).scalar()
    by_type = session.execute(
        select(Destination.entity_type, func.count())
        .group_by(Destination.entity_type)
    ).fetchall()

    logger.info("── Validation ───────────────────────────────────")
    for entity_type, count in by_type:
        logger.info("  %-10s %d", entity_type, count)
    logger.info("  Total:                           %d", total)
    logger.info("  No description:                  %d", no_desc)
    logger.info("  < 2 aliases:                     %d", few_aliases)
    logger.info("─────────────────────────────────────────────────")


# ── main ──────────────────────────────────────────────────────────────────────

def build_kb() -> None:
    engine = create_engine(settings.DATABASE_URL)
    page = settings.KB_SPARQL_PAGE_SIZE

    with Session(engine) as session:
        # Pass 1 — Countries
        logger.info("Pass 1 — Countries (SPARQL) ...")
        rows = _sparql_fetch_all(_COUNTRY_SPARQL, limit=page, max_rows=300)
        print("rows", len(rows))
        countries = _aggregate_by_qid(rows, "country")
        logger.info("  Aggregated %d unique countries — enriching aliases ...", len(countries))
        countries = _enrich_with_aliases(countries)
        countries = _enrich_with_descriptions(countries)
        ins, upd = _upsert_entities(session, countries)
        logger.info("✓ Pass 1 complete: %d inserted, %d updated", ins, upd)

        # Pass 2 — Cities
        logger.info("Pass 2 — Cities (SPARQL, top 600) ...")
        rows = _sparql_fetch_all(_CITY_SPARQL, limit=page, max_rows=600)
        cities = _aggregate_by_qid(rows, "city")
        logger.info("  Aggregated %d unique cities — enriching aliases ...", len(cities))
        cities = _enrich_with_aliases(cities)
        cities = _enrich_with_descriptions(cities)
        ins, upd = _upsert_entities(session, cities)
        logger.info("✓ Pass 2 complete: %d inserted, %d updated", ins, upd)

        # Pass 3 — Curated regions
        logger.info("Pass 3 — Regions (curated list) ...")
        regions = _build_region_entities()
        logger.info("  Fetched %d regions — enriching descriptions ...", len(regions))
        regions = _enrich_with_descriptions(regions)
        ins, upd = _upsert_entities(session, regions)
        logger.info("✓ Pass 3 complete: %d inserted, %d updated", ins, upd)

        _validate(session)


if __name__ == "__main__":
    build_kb()
