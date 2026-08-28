"""
Dedicated HistoryDAO for User Search History & Saved Itineraries / Bookings.
Supports PostgreSQL with SQLite fallback. All tables include mandatory audit fields.
"""

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Optional
from ..config import UserServiceConfig


class HistoryDAO:
    """
    Single-responsibility DAO managing `user_search_history` and `user_saved_itineraries` tables.
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
                CREATE INDEX IF NOT EXISTS idx_hist_dest ON users.user_search_history(destination);

                CREATE TABLE IF NOT EXISTS users.user_saved_itineraries (
                    id VARCHAR(100) PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
                    itinerary_id VARCHAR(100) NOT NULL,
                    destination VARCHAR(100) NOT NULL,
                    title TEXT NOT NULL,
                    total_price NUMERIC(10, 2),
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_saved_user ON users.user_saved_itineraries(user_id);
                CREATE INDEX IF NOT EXISTS idx_saved_itin ON users.user_saved_itineraries(itinerary_id);
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
                CREATE INDEX IF NOT EXISTS idx_hist_dest ON user_search_history(destination);

                CREATE TABLE IF NOT EXISTS user_saved_itineraries (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    itinerary_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    title TEXT NOT NULL,
                    total_price REAL,
                    payload TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_saved_user ON user_saved_itineraries(user_id);
                CREATE INDEX IF NOT EXISTS idx_saved_itin ON user_saved_itineraries(itinerary_id);
                """
                cursor.executescript(ddl)
                conn.commit()
        except Exception as err:
            print(f"[HISTORY DAO NOTICE] DB Init notice: {err}")
        finally:
            conn.close()

    def record_search(
        self,
        user_id: str,
        prompt: str,
        destination: Optional[str] = None,
        origin: Optional[str] = None,
        trip_duration_days: Optional[int] = None,
    ) -> str:
        """Records a user search query into user_search_history."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            hist_id = f"sch_{hashlib.md5(f'{user_id}_{prompt}_{now_iso}'.encode()).hexdigest()[:10]}"

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO user_search_history (id, user_id, prompt, destination, origin, trip_duration_days, created_at, updated_at, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                cursor.execute(sql, (hist_id, user_id, prompt, destination, origin, trip_duration_days, now_iso, now_iso, user_id, user_id))
            else:
                sql = """
                INSERT INTO user_search_history (id, user_id, prompt, destination, origin, trip_duration_days, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(sql, (hist_id, user_id, prompt, destination, origin, trip_duration_days, now_iso, now_iso, user_id, user_id))
                conn.commit()
            print(f"[HISTORY DAO] Logged search for user '{user_id}': '{prompt}'.")
            return hist_id
        finally:
            conn.close()

    def get_user_search_history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves recent search history for a user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT id, prompt, destination, origin, trip_duration_days, created_at FROM user_search_history WHERE user_id = %s ORDER BY created_at DESC LIMIT %s;"
                cursor.execute(sql, (user_id, limit))
            else:
                sql = "SELECT id, prompt, destination, origin, trip_duration_days, created_at FROM user_search_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?;"
                cursor.execute(sql, (user_id, limit))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                if isinstance(row, tuple):
                    result.append({
                        "id": row[0],
                        "prompt": row[1],
                        "destination": row[2],
                        "origin": row[3],
                        "trip_duration_days": row[4],
                        "created_at": str(row[5]) if row[5] else None
                    })
                else:
                    result.append({
                        "id": row["id"],
                        "prompt": row["prompt"],
                        "destination": row["destination"],
                        "origin": row["origin"],
                        "trip_duration_days": row["trip_duration_days"],
                        "created_at": str(row["created_at"]) if row["created_at"] else None
                    })
            return result
        finally:
            conn.close()

    def save_itinerary_booking(
        self,
        user_id: str,
        itinerary_id: str,
        destination: str,
        title: str,
        total_price: float,
        payload: dict[str, Any],
    ) -> str:
        """Saves a booked/liked itinerary for a user in user_saved_itineraries."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            saved_id = f"bkg_{hashlib.md5(f'{user_id}_{itinerary_id}'.encode()).hexdigest()[:10]}"
            payload_str = json.dumps(payload)

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO user_saved_itineraries (id, user_id, itinerary_id, destination, title, total_price, payload, created_at, updated_at, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    total_price = EXCLUDED.total_price,
                    payload = EXCLUDED.payload,
                    updated_at = EXCLUDED.updated_at,
                    updated_by = EXCLUDED.updated_by;
                """
                cursor.execute(sql, (saved_id, user_id, itinerary_id, destination, title, total_price, payload_str, now_iso, now_iso, user_id, user_id))
            else:
                sql = """
                INSERT INTO user_saved_itineraries (id, user_id, itinerary_id, destination, title, total_price, payload, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    total_price = excluded.total_price,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by;
                """
                cursor.execute(sql, (saved_id, user_id, itinerary_id, destination, title, total_price, payload_str, now_iso, now_iso, user_id, user_id))
                conn.commit()
            print(f"[HISTORY DAO] Saved booking '{saved_id}' (Itinerary: {itinerary_id}) for user '{user_id}'.")
            return saved_id
        finally:
            conn.close()

    def get_user_bookings(self, user_id: str) -> list[dict[str, Any]]:
        """Retrieves saved/booked itineraries for a user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT id, itinerary_id, destination, title, total_price, payload, created_at FROM user_saved_itineraries WHERE user_id = %s ORDER BY created_at DESC;"
                cursor.execute(sql, (user_id,))
            else:
                sql = "SELECT id, itinerary_id, destination, title, total_price, payload, created_at FROM user_saved_itineraries WHERE user_id = ? ORDER BY created_at DESC;"
                cursor.execute(sql, (user_id,))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                if isinstance(row, tuple):
                    try:
                        p_obj = json.loads(row[5]) if row[5] else {}
                    except Exception:
                        p_obj = {}
                    result.append({
                        "id": row[0],
                        "itinerary_id": row[1],
                        "destination": row[2],
                        "title": row[3],
                        "total_price": float(row[4]) if row[4] else 0.0,
                        "payload": p_obj,
                        "created_at": str(row[6]) if row[6] else None
                    })
                else:
                    try:
                        p_obj = json.loads(row["payload"]) if row["payload"] else {}
                    except Exception:
                        p_obj = {}
                    result.append({
                        "id": row["id"],
                        "itinerary_id": row["itinerary_id"],
                        "destination": row["destination"],
                        "title": row["title"],
                        "total_price": float(row["total_price"]) if row["total_price"] else 0.0,
                        "payload": p_obj,
                        "created_at": str(row["created_at"]) if row["created_at"] else None
                    })
            return result
        finally:
            conn.close()
