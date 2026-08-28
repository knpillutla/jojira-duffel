"""
Dedicated UserPreferencesDAO for managing `users.user_preferences` table.
Single Responsibility: Encapsulates travel preferences, home airport, seat choice, and custom JSON preference documents.
"""

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Optional
from ..config import UserServiceConfig


class UserPreferencesDAO:
    """
    Single-responsibility DAO for `users.user_preferences` database table.
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

                CREATE TABLE IF NOT EXISTS users.user_preferences (
                    user_id VARCHAR(100) PRIMARY KEY REFERENCES users.users(id) ON DELETE CASCADE,
                    home_airport VARCHAR(10),
                    preferred_style VARCHAR(50) DEFAULT 'balanced',
                    preferred_budget VARCHAR(50) DEFAULT 'moderate',
                    seat_preference VARCHAR(50),
                    interests TEXT,
                    preferences_json JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );
                """
                cursor.execute(ddl)
                conn.commit()
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    home_airport TEXT,
                    preferred_style TEXT DEFAULT 'balanced',
                    preferred_budget TEXT DEFAULT 'moderate',
                    seat_preference TEXT,
                    interests TEXT,
                    preferences_json TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );
                """
                cursor.executescript(ddl)
                conn.commit()

            try:
                if self.db_engine == "postgresql":
                    cursor.execute("ALTER TABLE users.user_preferences ADD COLUMN IF NOT EXISTS preferences_json JSONB;")
                else:
                    cursor.execute("ALTER TABLE user_preferences ADD COLUMN preferences_json TEXT;")
                conn.commit()
            except Exception:
                pass
        except Exception as err:
            print(f"[PREFERENCES DAO NOTICE] DB Init notice: {err}")
        finally:
            conn.close()

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        """Retrieves user travel preferences by user_id."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT home_airport, preferred_style, preferred_budget, seat_preference, interests, preferences_json FROM users.user_preferences WHERE user_id = %s;"
                cursor.execute(sql, (user_id,))
            else:
                sql = "SELECT home_airport, preferred_style, preferred_budget, seat_preference, interests, preferences_json FROM user_preferences WHERE user_id = ?;"
                cursor.execute(sql, (user_id,))

            row = cursor.fetchone()
            if not row:
                return {
                    "home_airport": "ATL",
                    "preferred_style": "balanced",
                    "preferred_budget": "moderate",
                    "seat_preference": None,
                    "interests": [],
                    "custom_preferences": {}
                }

            if isinstance(row, tuple):
                interests_raw, pref_json_raw = row[4], row[5]
            else:
                interests_raw, pref_json_raw = row["interests"], row["preferences_json"]

            try:
                interests_list = json.loads(interests_raw) if interests_raw else []
            except Exception:
                interests_list = []

            try:
                custom_pref_dict = json.loads(pref_json_raw) if pref_json_raw else {}
            except Exception:
                custom_pref_dict = {}

            return {
                "home_airport": (row[0] if isinstance(row, tuple) else row["home_airport"]) or "ATL",
                "preferred_style": (row[1] if isinstance(row, tuple) else row["preferred_style"]) or "balanced",
                "preferred_budget": (row[2] if isinstance(row, tuple) else row["preferred_budget"]) or "moderate",
                "seat_preference": row[3] if isinstance(row, tuple) else row["seat_preference"],
                "interests": interests_list,
                "custom_preferences": custom_pref_dict
            }
        finally:
            conn.close()

    def update_preferences(
        self,
        user_id: str,
        home_airport: Optional[str] = None,
        preferred_style: Optional[str] = None,
        preferred_budget: Optional[str] = None,
        seat_preference: Optional[str] = None,
        interests: Optional[list[str]] = None,
        custom_preferences: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Upserts user travel preferences in `user_preferences` table."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            interests_json = json.dumps(interests) if interests is not None else None
            custom_pref_str = json.dumps(custom_preferences) if custom_preferences is not None else None

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO users.user_preferences (user_id, home_airport, preferred_style, preferred_budget, seat_preference, interests, preferences_json, created_at, updated_at, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    home_airport = COALESCE(EXCLUDED.home_airport, user_preferences.home_airport),
                    preferred_style = COALESCE(EXCLUDED.preferred_style, user_preferences.preferred_style),
                    preferred_budget = COALESCE(EXCLUDED.preferred_budget, user_preferences.preferred_budget),
                    seat_preference = COALESCE(EXCLUDED.seat_preference, user_preferences.seat_preference),
                    interests = COALESCE(EXCLUDED.interests, user_preferences.interests),
                    preferences_json = COALESCE(EXCLUDED.preferences_json, user_preferences.preferences_json),
                    updated_at = EXCLUDED.updated_at,
                    updated_by = EXCLUDED.updated_by;
                """
                cursor.execute(sql, (user_id, home_airport, preferred_style, preferred_budget, seat_preference, interests_json, custom_pref_str, now_iso, now_iso, user_id, user_id))
            else:
                sql = """
                INSERT INTO user_preferences (user_id, home_airport, preferred_style, preferred_budget, seat_preference, interests, preferences_json, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    home_airport = COALESCE(excluded.home_airport, user_preferences.home_airport),
                    preferred_style = COALESCE(excluded.preferred_style, user_preferences.preferred_style),
                    preferred_budget = COALESCE(excluded.preferred_budget, user_preferences.preferred_budget),
                    seat_preference = COALESCE(excluded.seat_preference, user_preferences.seat_preference),
                    interests = COALESCE(excluded.interests, user_preferences.interests),
                    preferences_json = COALESCE(excluded.preferences_json, user_preferences.preferences_json),
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by;
                """
                cursor.execute(sql, (user_id, home_airport, preferred_style, preferred_budget, seat_preference, interests_json, custom_pref_str, now_iso, now_iso, user_id, user_id))
                conn.commit()
            print(f"[PREFERENCES DAO] Updated preferences for user '{user_id}'.")
            return True
        except Exception as err:
            print(f"[PREFERENCES DAO WARN] Update preferences failed: {err}")
            return False
        finally:
            conn.close()
