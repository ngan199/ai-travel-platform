"""
Neo4j driver singleton for the travel knowledge graph.

Usage:
    from app.db.neo4j_client import get_neo4j_driver, close_neo4j_driver

    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run("MATCH (c:City) RETURN c.name LIMIT 5")
        for record in result:
            print(record["c.name"])

Lifecycle:
    - Call get_neo4j_driver() anywhere in the app — returns the same instance.
    - Call close_neo4j_driver() on app shutdown (wired into FastAPI lifespan).
"""

from __future__ import annotations

import logging

from neo4j import GraphDatabase, Driver

from app.core.config import settings

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def get_neo4j_driver() -> Driver:
    """Return the shared Neo4j driver, creating it on first call."""
    global _driver
    if _driver is None:
        if not settings.NEO4J_PASSWORD:
            raise RuntimeError(
                "NEO4J_PASSWORD is not set. "
                "Add it to your .env file before using the graph KB."
            )
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            # Connection pool — one pool shared across all requests
            max_connection_pool_size=50,
            connection_timeout=30,
        )
        # Verify connectivity immediately so misconfiguration fails fast
        _driver.verify_connectivity()
        logger.info("Neo4j driver connected → %s", settings.NEO4J_URI)
    return _driver


def close_neo4j_driver() -> None:
    """Close the driver and release all connections. Call on app shutdown."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed.")
