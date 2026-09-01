"""
Unit tests for DatabaseCleaner DAO.
"""

import os
import sqlite3
import pytest
from duffel.config import DuffelConfig
from duffel.db.db_cleaner import DatabaseCleaner


def test_database_cleaner_sqlite(tmp_path):
    test_db = str(tmp_path / "test_cleaner.db")
    os.environ["SQLITE_DB_PATH"] = test_db

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE generated_itineraries (id TEXT PRIMARY KEY, payload TEXT);")
    cur.execute("INSERT INTO generated_itineraries (id, payload) VALUES ('itin_1', '{}');")
    cur.execute("CREATE TABLE itinerary_modules (id TEXT PRIMARY KEY, content TEXT);")
    cur.execute("INSERT INTO itinerary_modules (id, content) VALUES ('mod_1', '{}');")
    conn.commit()
    conn.close()

    config = DuffelConfig(environment="local")
    config.postgres_enabled = False

    cleaner = DatabaseCleaner(config=config)
    cleared = cleaner.clear_itinerary_and_cache_tables()

    assert any("generated_itineraries" in t for t in cleared)
    assert any("itinerary_modules" in t for t in cleared)

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM generated_itineraries;")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM itinerary_modules;")
    assert cur.fetchone()[0] == 0
    conn.close()
