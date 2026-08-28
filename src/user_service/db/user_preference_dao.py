"""
Dedicated Single-Responsibility DAO for User Preferences (`users.user_preferences`).
Manages loading, creating, and updating travel preferences for users.
"""

from typing import Any, Optional
from datetime import datetime, timezone
import json
import os
import sqlite3

from ..config import UserServiceConfig

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class UserPreferenceDAO:
    """Dedicated DAO for managing user preferences in `users.user_preferences` table."""

    def __init__(self, config: Optional[UserServiceConfig] = None):
        self.config = config or UserServiceConfig()
        self.db_engine = "postgresql" if self.config.postgres_enabled and HAS_PSYCOPG2 else "sqlite_fallback"
        self._sqlite_file = os.path.join(os.path.dirname(__file__), "..", "user_service.db")

        self.host = self.config.postgres_host
        self.port = self.config.postgres_port
        self.database = self.config.postgres_db
        self.user = self.config.postgres_user
        self.password = self.config.postgres_password

        self._pg_conn = None
        if self.db_engine == "postgresql":
            try:
                if self.config.postgres_url:
                    self._pg_conn = psycopg2.connect(self.config.postgres_url, connect_timeout=2)
                else:
                    self._pg_conn = psycopg2.connect(
                        host=self.host,
                        port=self.port,
                        dbname=self.database,
                        user=self.user,
                        password=self.password,
                        connect_timeout=2
                    )
                self._pg_conn.autocommit = True
            except Exception as err:
                err_msg = f"[POSTGRES ERROR] Failed to connect to PostgreSQL database ({self.host}:{self.port}/{self.database}): {err}. Exiting application."
                print(f"\n{'=' * 80}\n{err_msg}\n{'=' * 80}\n")
                import sys
                sys.exit(1)

        self._init_db()

    def _get_connection(self):
        if self.db_engine == "postgresql" and self._pg_conn:
            try:
                if self._pg_conn.closed == 0:
                    return self._pg_conn
            except Exception:
                pass
        conn = sqlite3.connect(self._sqlite_file)
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
                    home_airport VARCHAR(10) DEFAULT 'ATL',
                    preferred_style VARCHAR(50) DEFAULT 'balanced',
                    preferred_budget VARCHAR(50) DEFAULT 'moderate',
                    seat_preference VARCHAR(50),
                    hotel_type VARCHAR(100),
                    hotel_rating VARCHAR(50),
                    hotel_user_rating VARCHAR(50),
                    ui_layout VARCHAR(50) DEFAULT 'grid',
                    airline VARCHAR(100),
                    airline_class VARCHAR(50) DEFAULT 'economy',
                    interests TEXT,
                    preferences_json JSONB,
                    is_test BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );
                """
                cursor.execute(ddl)
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    home_airport TEXT DEFAULT 'ATL',
                    preferred_style TEXT DEFAULT 'balanced',
                    preferred_budget TEXT DEFAULT 'moderate',
                    seat_preference TEXT,
                    hotel_type TEXT,
                    hotel_rating TEXT,
                    hotel_user_rating TEXT,
                    ui_layout TEXT DEFAULT 'grid',
                    airline TEXT,
                    airline_class TEXT DEFAULT 'economy',
                    interests TEXT,
                    preferences_json TEXT,
                    is_test INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );
                """
                cursor.executescript(ddl)
                conn.commit()

            # Auto-migrations for preference columns
            cols = [
                ("home_airport", "VARCHAR(10)", "TEXT"),
                ("preferred_style", "VARCHAR(50)", "TEXT"),
                ("preferred_budget", "VARCHAR(50)", "TEXT"),
                ("seat_preference", "VARCHAR(50)", "TEXT"),
                ("hotel_type", "VARCHAR(100)", "TEXT"),
                ("hotel_rating", "VARCHAR(50)", "TEXT"),
                ("hotel_user_rating", "VARCHAR(50)", "TEXT"),
                ("ui_layout", "VARCHAR(50)", "TEXT"),
                ("airline", "VARCHAR(100)", "TEXT"),
                ("airline_class", "VARCHAR(50)", "TEXT"),
                ("interests", "TEXT", "TEXT"),
                ("preferences_json", "JSONB", "TEXT"),
                ("is_test", "BOOLEAN DEFAULT FALSE", "INTEGER DEFAULT 0"),
                ("created_at", "TIMESTAMP WITH TIME ZONE", "TEXT"),
                ("updated_at", "TIMESTAMP WITH TIME ZONE", "TEXT"),
                ("created_by", "VARCHAR(100)", "TEXT"),
                ("updated_by", "VARCHAR(100)", "TEXT"),
            ]
            for col_name, pg_t, sq_t in cols:
                try:
                    c_type = pg_t if self.db_engine == "postgresql" else sq_t
                    tbl = "users.user_preferences" if self.db_engine == "postgresql" else "user_preferences"
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {c_type};")
                    if self.db_engine != "postgresql":
                        conn.commit()
                except Exception:
                    pass
        except Exception as err:
            print(f"[USER PREFERENCE DAO NOTICE] DB Init notice: {err}")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        """Retrieves user preference row from `users.user_preferences` table."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT user_id, home_airport, preferred_style, preferred_budget, seat_preference,
                       hotel_type, hotel_rating, hotel_user_rating, ui_layout, airline, airline_class,
                       interests, preferences_json, is_test, created_at, created_by, updated_at, updated_by
                FROM users.user_preferences
                WHERE user_id = %s
                LIMIT 1;
                """
                cursor.execute(sql, (user_id,))
            else:
                sql = """
                SELECT user_id, home_airport, preferred_style, preferred_budget, seat_preference,
                       hotel_type, hotel_rating, hotel_user_rating, ui_layout, airline, airline_class,
                       interests, preferences_json, is_test, created_at, created_by, updated_at, updated_by
                FROM user_preferences
                WHERE user_id = ?
                LIMIT 1;
                """
                cursor.execute(sql, (user_id,))

            row = cursor.fetchone()
            if not row:
                return {
                    "user_id": user_id,
                    "home_airport": "ATL",
                    "preferred_style": "balanced",
                    "preferred_budget": "moderate",
                    "seat_preference": "window",
                    "hotel_type": "resort",
                    "hotel_rating": "4-star",
                    "hotel_user_rating": "8.5+",
                    "ui_layout": "grid",
                    "airline": "Delta",
                    "airline_class": "economy",
                    "interests": ["romantic", "nature"],
                    "is_test": False,
                    "created_at": None,
                    "created_by": user_id,
                    "updated_at": None,
                    "updated_by": user_id,
                }

            if isinstance(row, tuple):
                interests_raw = row[11]
                interests_list = json.loads(interests_raw) if interests_raw and isinstance(interests_raw, str) else (interests_raw or ["romantic", "nature"])
                return {
                    "user_id": row[0],
                    "home_airport": row[1] or "ATL",
                    "preferred_style": row[2] or "balanced",
                    "preferred_budget": row[3] or "moderate",
                    "seat_preference": row[4],
                    "hotel_type": row[5] or "resort",
                    "hotel_rating": row[6] or "4-star",
                    "hotel_user_rating": row[7] or "8.5+",
                    "ui_layout": row[8] or "grid",
                    "airline": row[9] or "Delta",
                    "airline_class": row[10] or "economy",
                    "interests": interests_list if isinstance(interests_list, list) else ["romantic", "nature"],
                    "is_test": bool(row[13]),
                    "created_at": str(row[14]) if row[14] else None,
                    "created_by": row[15] or user_id,
                    "updated_at": str(row[16]) if row[16] else None,
                    "updated_by": row[17] or user_id,
                }

            interests_raw = row["interests"]
            interests_list = json.loads(interests_raw) if interests_raw and isinstance(interests_raw, str) else (interests_raw or ["romantic", "nature"])
            return {
                "user_id": row["user_id"],
                "home_airport": row["home_airport"] or "ATL",
                "preferred_style": row["preferred_style"] or "balanced",
                "preferred_budget": row["preferred_budget"] or "moderate",
                "seat_preference": row["seat_preference"],
                "hotel_type": row["hotel_type"] or "resort",
                "hotel_rating": row["hotel_rating"] or "4-star",
                "hotel_user_rating": row["hotel_user_rating"] or "8.5+",
                "ui_layout": row["ui_layout"] or "grid",
                "airline": row["airline"] or "Delta",
                "airline_class": row["airline_class"] or "economy",
                "interests": interests_list if isinstance(interests_list, list) else ["romantic", "nature"],
                "is_test": bool(row["is_test"]) if "is_test" in row.keys() else False,
                "created_at": str(row["created_at"]) if row["created_at"] else None,
                "created_by": row["created_by"] if "created_by" in row.keys() else user_id,
                "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
                "updated_by": row["updated_by"] if "updated_by" in row.keys() else user_id,
            }
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    def upsert_preferences(
        self,
        user_id: str,
        home_airport: Optional[str] = None,
        preferred_style: Optional[str] = None,
        preferred_budget: Optional[str] = None,
        seat_preference: Optional[str] = None,
        hotel_type: Optional[str] = None,
        hotel_rating: Optional[str] = None,
        hotel_user_rating: Optional[str] = None,
        ui_layout: Optional[str] = None,
        airline: Optional[str] = None,
        airline_class: Optional[str] = None,
        interests: Optional[list[str]] = None,
        custom_preferences: Optional[dict[str, Any]] = None,
        is_test: bool = False,
    ) -> bool:
        """Upserts user travel preferences into `users.user_preferences` table."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            interests_json = json.dumps(interests) if interests is not None else None
            custom_pref_str = json.dumps(custom_preferences) if custom_preferences is not None else None
            is_test_val = 1 if (is_test or "test" in user_id.lower()) else 0

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO users.user_preferences (
                    user_id, home_airport, preferred_style, preferred_budget, seat_preference,
                    hotel_type, hotel_rating, hotel_user_rating, ui_layout, airline, airline_class,
                    interests, preferences_json, is_test, created_at, updated_at, created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    home_airport = COALESCE(EXCLUDED.home_airport, user_preferences.home_airport),
                    preferred_style = COALESCE(EXCLUDED.preferred_style, user_preferences.preferred_style),
                    preferred_budget = COALESCE(EXCLUDED.preferred_budget, user_preferences.preferred_budget),
                    seat_preference = COALESCE(EXCLUDED.seat_preference, user_preferences.seat_preference),
                    hotel_type = COALESCE(EXCLUDED.hotel_type, user_preferences.hotel_type),
                    hotel_rating = COALESCE(EXCLUDED.hotel_rating, user_preferences.hotel_rating),
                    hotel_user_rating = COALESCE(EXCLUDED.hotel_user_rating, user_preferences.hotel_user_rating),
                    ui_layout = COALESCE(EXCLUDED.ui_layout, user_preferences.ui_layout),
                    airline = COALESCE(EXCLUDED.airline, user_preferences.airline),
                    airline_class = COALESCE(EXCLUDED.airline_class, user_preferences.airline_class),
                    interests = COALESCE(EXCLUDED.interests, user_preferences.interests),
                    preferences_json = COALESCE(EXCLUDED.preferences_json, user_preferences.preferences_json),
                    is_test = EXCLUDED.is_test,
                    updated_at = EXCLUDED.updated_at,
                    updated_by = EXCLUDED.updated_by;
                """
                cursor.execute(sql, (
                    user_id, home_airport, preferred_style, preferred_budget, seat_preference,
                    hotel_type, hotel_rating, hotel_user_rating, ui_layout, airline, airline_class,
                    interests_json, custom_pref_str, bool(is_test_val), now_iso, now_iso, user_id, user_id
                ))
            else:
                sql = """
                INSERT INTO user_preferences (
                    user_id, home_airport, preferred_style, preferred_budget, seat_preference,
                    hotel_type, hotel_rating, hotel_user_rating, ui_layout, airline, airline_class,
                    interests, preferences_json, is_test, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    home_airport = COALESCE(excluded.home_airport, user_preferences.home_airport),
                    preferred_style = COALESCE(excluded.preferred_style, user_preferences.preferred_style),
                    preferred_budget = COALESCE(excluded.preferred_budget, user_preferences.preferred_budget),
                    seat_preference = COALESCE(excluded.seat_preference, user_preferences.seat_preference),
                    hotel_type = COALESCE(excluded.hotel_type, user_preferences.hotel_type),
                    hotel_rating = COALESCE(excluded.hotel_rating, user_preferences.hotel_rating),
                    hotel_user_rating = COALESCE(excluded.hotel_user_rating, user_preferences.hotel_user_rating),
                    ui_layout = COALESCE(excluded.ui_layout, user_preferences.ui_layout),
                    airline = COALESCE(excluded.airline, user_preferences.airline),
                    airline_class = COALESCE(excluded.airline_class, user_preferences.airline_class),
                    interests = COALESCE(excluded.interests, user_preferences.interests),
                    preferences_json = COALESCE(excluded.preferences_json, user_preferences.preferences_json),
                    is_test = excluded.is_test,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by;
                """
                cursor.execute(sql, (
                    user_id, home_airport, preferred_style, preferred_budget, seat_preference,
                    hotel_type, hotel_rating, hotel_user_rating, ui_layout, airline, airline_class,
                    interests_json, custom_pref_str, is_test_val, now_iso, now_iso, user_id, user_id
                ))
                conn.commit()
            print(f"[USER PREFERENCE DAO] Upserted preferences for user '{user_id}'.")
            return True
        except Exception as err:
            print(f"[USER PREFERENCE DAO WARN] Upsert failed: {err}")
            return False
        finally:
            if self.db_engine != "postgresql":
                conn.close()
