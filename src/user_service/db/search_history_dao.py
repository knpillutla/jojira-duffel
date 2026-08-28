"""
Dedicated SearchHistoryDAO for managing `users.user_search_history` table.
Single Responsibility: Encapsulates recording, listing, and querying user search history prompts.
"""

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Optional
from ..config import UserServiceConfig


class SearchHistoryDAO:
    """
    Single-responsibility DAO for `users.user_search_history` database table.
    """

    def __init__(self, config: Optional[UserServiceConfig] = None):
        self.config = config or UserServiceConfig()
        self.db_engine = "postgresql" if self.config.postgres_enabled else "sqlite"
        self._init_db()

    def _get_connection(self):
        if self.config.postgres_enabled:
            try:
                import psycopg2
                if self.config.postgres_url:
                    return psycopg2.connect(self.config.postgres_url, connect_timeout=2)
                return psycopg2.connect(
                    host=self.config.postgres_host,
                    port=self.config.postgres_port,
                    dbname=self.config.postgres_db,
                    user=self.config.postgres_user,
                    password=self.config.postgres_password,
                    connect_timeout=2,
                )
            except Exception as pg_err:
                err_msg = f"[POSTGRES ERROR] Failed to connect to PostgreSQL database ({self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_db}): {pg_err}. Exiting application."
                print(f"\n{'=' * 80}\n{err_msg}\n{'=' * 80}\n")
                import sys
                sys.exit(1)

        conn = sqlite3.connect("jojira_user_service.db")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                ddl = """
                CREATE SCHEMA IF NOT EXISTS users;

                CREATE TABLE IF NOT EXISTS users.user_search_history (
                    id VARCHAR(100) PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
                    prompt TEXT NOT NULL,
                    destination VARCHAR(100),
                    origin VARCHAR(10),
                    trip_duration_days INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_hist_user ON users.user_search_history(user_id);
                """
                cursor.execute(ddl)
                conn.commit()
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS user_search_history (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    prompt TEXT NOT NULL,
                    destination TEXT,
                    origin TEXT,
                    trip_duration_days INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_hist_user ON user_search_history(user_id);
                """
                cursor.executescript(ddl)
                conn.commit()
            cols = [
                ("bundles_json", "JSONB", "TEXT"),
                ("itinerary_json", "JSONB", "TEXT"),
                ("itinerary_id", "VARCHAR(100)", "TEXT"),
                ("is_test", "BOOLEAN DEFAULT FALSE", "INTEGER DEFAULT 0"),
            ]

            for col_name, pg_t, sq_t in cols:
                try:
                    c_type = pg_t if self.db_engine == "postgresql" else sq_t
                    tbl = "users.user_search_history" if self.db_engine == "postgresql" else "user_search_history"
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {c_type};")
                    conn.commit()
                except Exception:
                    conn.rollback()

        except Exception as err:
            print(f"[SEARCH HISTORY DAO NOTICE] DB Init notice: {err}")
        finally:
            conn.close()

    def record_search(
        self,
        user_id: str,
        prompt: str,
        destination: Optional[str] = None,
        origin: Optional[str] = None,
        trip_duration_days: Optional[int] = None,
        bundles: Optional[list[dict[str, Any]]] = None,
        itinerary: Optional[dict[str, Any]] = None,
        itinerary_id: Optional[str] = None,
    ) -> str:
        """Records a new search query along with its generated package bundles and draft itinerary."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            hist_id = f"sch_{hashlib.md5(f'{user_id}_{prompt}_{now_iso}'.encode()).hexdigest()[:10]}"
            bundles_json_str = json.dumps(bundles or [])
            itin_json_str = json.dumps(itinerary or {})

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO users.user_search_history (id, user_id, prompt, destination, origin, trip_duration_days, bundles_json, itinerary_json, itinerary_id, created_at, updated_at, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                cursor.execute(sql, (hist_id, user_id, prompt, destination, origin, trip_duration_days, bundles_json_str, itin_json_str, itinerary_id, now_iso, now_iso, user_id, user_id))
            else:
                sql = """
                INSERT INTO user_search_history (id, user_id, prompt, destination, origin, trip_duration_days, bundles_json, itinerary_json, itinerary_id, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(sql, (hist_id, user_id, prompt, destination, origin, trip_duration_days, bundles_json_str, itin_json_str, itinerary_id, now_iso, now_iso, user_id, user_id))
                conn.commit()

            print(f"[SEARCH HISTORY DAO] Logged search for user '{user_id}': '{prompt}'.")
            return hist_id
        finally:
            conn.close()

    def get_user_search_history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves past search history list for a user ordered by recent first."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT id, prompt, destination, origin, trip_duration_days, itinerary_id, created_at
                FROM users.user_search_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """
                cursor.execute(sql, (user_id, limit))
            else:
                sql = """
                SELECT id, prompt, destination, origin, trip_duration_days, itinerary_id, created_at
                FROM user_search_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?;
                """
                cursor.execute(sql, (user_id, limit))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                if isinstance(row, tuple):
                    results.append({
                        "id": row[0],
                        "prompt": row[1],
                        "destination": row[2],
                        "origin": row[3],
                        "trip_duration_days": row[4],
                        "itinerary_id": row[5],
                        "created_at": str(row[6]) if row[6] else None,
                    })
                else:
                    results.append({
                        "id": row["id"],
                        "prompt": row["prompt"],
                        "destination": row["destination"],
                        "origin": row["origin"],
                        "trip_duration_days": row["trip_duration_days"],
                        "itinerary_id": row["itinerary_id"],
                        "created_at": str(row["created_at"]) if row["created_at"] else None,
                    })
            return results
        finally:
            conn.close()

    def get_search_entry_details(self, user_id: str, search_id: str) -> Optional[dict[str, Any]]:
        """Retrieves a specific search history entry with full generated bundle options & draft itinerary."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT id, prompt, destination, origin, trip_duration_days, bundles_json, itinerary_json, itinerary_id, created_at
                FROM users.user_search_history
                WHERE user_id = %s AND id = %s
                LIMIT 1;
                """
                cursor.execute(sql, (user_id, search_id))
            else:
                sql = """
                SELECT id, prompt, destination, origin, trip_duration_days, bundles_json, itinerary_json, itinerary_id, created_at
                FROM user_search_history
                WHERE user_id = ? AND id = ?
                LIMIT 1;
                """
                cursor.execute(sql, (user_id, search_id))

            row = cursor.fetchone()
            if not row:
                return None

            if isinstance(row, tuple):
                b_raw, i_raw = row[5], row[6]
                return {
                    "id": row[0],
                    "user_id": user_id,
                    "prompt": row[1],
                    "destination": row[2],
                    "origin": row[3],
                    "trip_duration_days": row[4],
                    "bundle_options": json.loads(b_raw) if b_raw and isinstance(b_raw, str) else (b_raw or []),
                    "itinerary_draft": json.loads(i_raw) if i_raw and isinstance(i_raw, str) else (i_raw or {}),
                    "itinerary_id": row[7],
                    "created_at": str(row[8]) if row[8] else None,
                }

            b_raw, i_raw = row["bundles_json"], row["itinerary_json"]
            return {
                "id": row["id"],
                "user_id": user_id,
                "prompt": row["prompt"],
                "destination": row["destination"],
                "origin": row["origin"],
                "trip_duration_days": row["trip_duration_days"],
                "bundle_options": json.loads(b_raw) if b_raw and isinstance(b_raw, str) else (b_raw or []),
                "itinerary_draft": json.loads(i_raw) if i_raw and isinstance(i_raw, str) else (i_raw or {}),
                "itinerary_id": row["itinerary_id"],
                "created_at": str(row["created_at"]) if row["created_at"] else None,
            }
        finally:
            conn.close()

