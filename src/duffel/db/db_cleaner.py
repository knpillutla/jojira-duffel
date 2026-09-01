"""
Dedicated Database Cleaner DAO module for clearing and flushing cache and itinerary tables.
Follows single responsibility, modularity, and strict line size limits.
"""

import os
import sqlite3
from typing import Any, Optional

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class DatabaseCleaner:
    """Handles clearing and flushing database tables across PostgreSQL and SQLite."""

    TARGET_TABLES_PG = [
        ("planner", "itinerary_modules"),
        ("public", "itinerary_modules"),
        ("planner", "generated_itineraries"),
        ("public", "generated_itineraries"),
        ("public", "itinerary_templates"),
        ("public", "llm_call_logs"),
        ("public", "ai_search_history"),
        ("users", "user_trip_plans"),
        ("public", "user_trip_plans"),
        ("users", "user_saved_itineraries"),
        ("public", "user_saved_itineraries"),
        ("users", "user_booked_itineraries"),
        ("public", "user_booked_itineraries"),
        ("users", "user_search_history"),
        ("public", "user_search_history"),
    ]

    TARGET_TABLES_SQLITE = [
        "itinerary_modules",
        "generated_itineraries",
        "itinerary_templates",
        "llm_call_logs",
        "ai_search_history",
        "user_trip_plans",
        "user_saved_itineraries",
        "user_booked_itineraries",
        "user_search_history",
    ]

    def __init__(self, config: Optional[Any] = None):
        self.config = config
        self.db_engine = "sqlite"
        self.postgres_url = ""

        if config and getattr(config, "postgres_enabled", False):
            self.db_engine = "postgresql"
            self.postgres_url = getattr(config, "postgres_url", "") or os.getenv("POSTGRES_URL", "")
            if not self.postgres_url:
                user = getattr(config, "postgres_user", "postgres")
                pwd = getattr(config, "postgres_password", "postgres")
                host = getattr(config, "postgres_host", "127.0.0.1")
                port = getattr(config, "postgres_port", 5432)
                db = getattr(config, "postgres_db", "jojira_duffel")
                self.postgres_url = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

        self.sqlite_db_path = os.getenv("SQLITE_DB_PATH", "jojira_duffel.db")

    def _get_pg_connection(self):
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2 is not installed. Cannot connect to PostgreSQL.")
        return psycopg2.connect(self.postgres_url, connect_timeout=3)

    def _table_exists_pg(self, cursor, schema_name: str, table_name: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s LIMIT 1;",
            (schema_name, table_name),
        )
        return cursor.fetchone() is not None

    def clear_itinerary_and_cache_tables(self) -> list[str]:
        """Clears all itinerary and cached database tables, returning the list of cleared tables."""
        cleared = []
        if self.db_engine == "postgresql":
            conn = self._get_pg_connection()
            try:
                cur = conn.cursor()
                for schema, tbl in self.TARGET_TABLES_PG:
                    try:
                        if self._table_exists_pg(cur, schema, tbl):
                            full_name = f'"{schema}"."{tbl}"' if schema != "public" else f'"{tbl}"'
                            cur.execute(f"TRUNCATE TABLE {full_name} RESTART IDENTITY CASCADE;")
                            conn.commit()
                            cleared.append(f"{schema}.{tbl}")
                    except Exception as tbl_err:
                        conn.rollback()
                        print(f"[!] Warning truncating {schema}.{tbl}: {tbl_err}")
            finally:
                conn.close()
        else:
            db_paths = [self.sqlite_db_path, "jojira_user_service.db"]
            for path in set(db_paths):
                if os.path.exists(path):
                    conn = sqlite3.connect(path)
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        existing_tables = {row[0] for row in cur.fetchall()}
                        for tbl in self.TARGET_TABLES_SQLITE:
                            if tbl in existing_tables:
                                cur.execute(f"DELETE FROM {tbl};")
                                cleared.append(f"{path}:{tbl}")
                        conn.commit()
                    finally:
                        conn.close()

        return cleared
