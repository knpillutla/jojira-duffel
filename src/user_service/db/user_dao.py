"""
Dedicated UserDAO for Jojira User Identity & Preferences.
Supports PostgreSQL with SQLite fallback. All tables include mandatory audit fields.
"""

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Optional, Union
from ..config import UserServiceConfig


class UserDAO:
    """
    Single-responsibility DAO managing `users` and `user_preferences` tables.
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

                CREATE TABLE IF NOT EXISTS users.users (
                    id VARCHAR(100) PRIMARY KEY,
                    google_user_id VARCHAR(150) UNIQUE,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255),
                    first_name VARCHAR(150),
                    last_name VARCHAR(150),
                    phone_number VARCHAR(50),
                    date_of_birth VARCHAR(20),
                    picture_url TEXT,
                    last_login_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );

                CREATE INDEX IF NOT EXISTS idx_users_google_id ON users.users(google_user_id);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users.users(email);

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
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    google_user_id TEXT UNIQUE,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone_number TEXT,
                    date_of_birth TEXT,
                    picture_url TEXT,
                    last_login_at TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );

                CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_user_id);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

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

            # Automatic schema migration for new passenger profile columns & preferences_json
            for col_name, col_type in [("first_name", "TEXT"), ("last_name", "TEXT"), ("phone_number", "TEXT"), ("date_of_birth", "TEXT")]:
                try:
                    if self.db_engine == "postgresql":
                        cursor.execute(f"ALTER TABLE users.users ADD COLUMN IF NOT EXISTS {col_name} VARCHAR(150);")
                    else:
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")
                    conn.commit()
                except Exception:
                    pass

            try:
                if self.db_engine == "postgresql":
                    cursor.execute("ALTER TABLE users.user_preferences ADD COLUMN IF NOT EXISTS preferences_json JSONB;")
                else:
                    cursor.execute("ALTER TABLE user_preferences ADD COLUMN preferences_json TEXT;")
                conn.commit()
            except Exception:
                pass

            cols = [
                ("users.users" if self.db_engine == "postgresql" else "users", "is_test", "BOOLEAN DEFAULT FALSE" if self.db_engine == "postgresql" else "INTEGER DEFAULT 0"),
                ("users.user_preferences" if self.db_engine == "postgresql" else "user_preferences", "is_test", "BOOLEAN DEFAULT FALSE" if self.db_engine == "postgresql" else "INTEGER DEFAULT 0"),
                ("users.user_preferences" if self.db_engine == "postgresql" else "user_preferences", "hotel_type", "VARCHAR(100)"),
                ("users.user_preferences" if self.db_engine == "postgresql" else "user_preferences", "hotel_rating", "VARCHAR(50)"),
                ("users.user_preferences" if self.db_engine == "postgresql" else "user_preferences", "hotel_user_rating", "VARCHAR(50)"),
                ("users.user_preferences" if self.db_engine == "postgresql" else "user_preferences", "ui_layout", "VARCHAR(50)"),
                ("users.user_preferences" if self.db_engine == "postgresql" else "user_preferences", "airline", "VARCHAR(100)"),
                ("users.user_preferences" if self.db_engine == "postgresql" else "user_preferences", "airline_class", "VARCHAR(50)"),
            ]
            for tbl, col_name, c_type in cols:
                try:
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {c_type};")
                    if self.db_engine != "postgresql":
                        conn.commit()
                except Exception:
                    pass

        except Exception as err:
            print(f"[USER DAO NOTICE] DB Init notice: {err}")
        finally:
            conn.close()


    def sync_google_user(
        self,
        email: str,
        google_user_id: Optional[str] = None,
        name: Optional[str] = None,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        picture_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Upserts a user record from Google OAuth login token payload."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            
            # Resolve first_name and last_name from given_name/family_name or full name
            f_name = first_name or given_name
            l_name = last_name or family_name
            if not f_name and name:
                parts = name.strip().split()
                f_name = parts[0] if parts else ""
                if not l_name and len(parts) > 1:
                    l_name = " ".join(parts[1:])

            # User ID is the email address directly
            user_id = email.lower().strip()

            
            if self.db_engine == "postgresql":
                sql_check = "SELECT id, google_user_id, email, name, picture_url, created_at FROM users.users WHERE email = %s OR (google_user_id = %s AND %s IS NOT NULL);"
                cursor.execute(sql_check, (email.lower().strip(), google_user_id, google_user_id))
            else:
                sql_check = "SELECT id, google_user_id, email, name, picture_url, created_at FROM users WHERE email = ? OR (google_user_id = ? AND ? IS NOT NULL);"
                cursor.execute(sql_check, (email.lower().strip(), google_user_id, google_user_id))
            
            existing = cursor.fetchone()

            if existing:
                u_id = existing[0] if isinstance(existing, tuple) else existing["id"]
                if self.db_engine == "postgresql":
                    sql_upd = """
                    UPDATE users.users 
                    SET google_user_id = COALESCE(%s, google_user_id),
                        name = COALESCE(%s, name),
                        first_name = COALESCE(%s, first_name),
                        last_name = COALESCE(%s, last_name),
                        phone_number = COALESCE(%s, phone_number),
                        date_of_birth = COALESCE(%s, date_of_birth),
                        picture_url = COALESCE(%s, picture_url),
                        last_login_at = %s,
                        updated_at = %s,
                        updated_by = %s
                    WHERE id = %s;
                    """
                    cursor.execute(sql_upd, (google_user_id, name, f_name, l_name, phone_number, date_of_birth, picture_url, now_iso, now_iso, u_id, u_id))
                else:
                    sql_upd = """
                    UPDATE users 
                    SET google_user_id = COALESCE(?, google_user_id),
                        name = COALESCE(?, name),
                        first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        phone_number = COALESCE(?, phone_number),
                        date_of_birth = COALESCE(?, date_of_birth),
                        picture_url = COALESCE(?, picture_url),
                        last_login_at = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE id = ?;
                    """
                    cursor.execute(sql_upd, (google_user_id, name, f_name, l_name, phone_number, date_of_birth, picture_url, now_iso, now_iso, u_id, u_id))
                    conn.commit()
                print(f"[USER DAO] Synced existing Google user '{email}' (ID: {u_id}).")
                user_id = u_id
            else:
                if self.db_engine == "postgresql":
                    sql_ins = """
                    INSERT INTO users.users (id, google_user_id, email, name, first_name, last_name, phone_number, date_of_birth, picture_url, last_login_at, created_at, updated_at, created_by, updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.execute(sql_ins, (user_id, google_user_id, email.lower().strip(), name, f_name, l_name, phone_number, date_of_birth, picture_url, now_iso, now_iso, now_iso, user_id, user_id))
                    
                    sql_pref = """
                    INSERT INTO users.user_preferences (user_id, home_airport, preferred_style, preferred_budget, created_at, updated_at, created_by, updated_by)
                    VALUES (%s, 'ATL', 'balanced', 'moderate', %s, %s, %s, %s) ON CONFLICT DO NOTHING;
                    """
                    cursor.execute(sql_pref, (user_id, now_iso, now_iso, user_id, user_id))
                    conn.commit()

                else:
                    sql_ins = """
                    INSERT INTO users (id, google_user_id, email, name, first_name, last_name, phone_number, date_of_birth, picture_url, last_login_at, created_at, updated_at, created_by, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """
                    cursor.execute(sql_ins, (user_id, google_user_id, email.lower().strip(), name, f_name, l_name, phone_number, date_of_birth, picture_url, now_iso, now_iso, now_iso, user_id, user_id))
                    
                    sql_pref = """
                    INSERT INTO user_preferences (user_id, home_airport, preferred_style, preferred_budget, created_at, updated_at, created_by, updated_by)
                    VALUES (?, 'ATL', 'balanced', 'moderate', ?, ?, ?, ?) ON CONFLICT(user_id) DO NOTHING;
                    """
                    cursor.execute(sql_pref, (user_id, now_iso, now_iso, user_id, user_id))
                    conn.commit()
                print(f"[USER DAO] Created new Google user '{email}' (ID: {user_id}).")

            return self.get_user_by_id(user_id)
        except Exception as err:
            print(f"[USER DAO WARN] Sync Google user failed: {err}")
            raise err
        finally:
            conn.close()

    def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        """Retrieves user profile and preferences by user_id."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT u.id, u.google_user_id, u.email, u.name, u.first_name, u.last_name, u.phone_number, u.date_of_birth, u.picture_url, u.last_login_at, u.created_at, u.updated_at,
                       p.home_airport, p.preferred_style, p.preferred_budget, p.seat_preference, p.interests
                FROM users.users u
                LEFT JOIN users.user_preferences p ON u.id = p.user_id
                WHERE u.id = %s;
                """
                cursor.execute(sql, (user_id,))
            else:
                sql = """
                SELECT u.id, u.google_user_id, u.email, u.name, u.first_name, u.last_name, u.phone_number, u.date_of_birth, u.picture_url, u.last_login_at, u.created_at, u.updated_at,
                       p.home_airport, p.preferred_style, p.preferred_budget, p.seat_preference, p.interests
                FROM users u
                LEFT JOIN user_preferences p ON u.id = p.user_id
                WHERE u.id = ?;
                """
                cursor.execute(sql, (user_id,))

            row = cursor.fetchone()
            if not row:
                return None

            if isinstance(row, tuple):
                interests_raw = row[16]
                try:
                    interests_list = json.loads(interests_raw) if interests_raw else []
                except Exception:
                    interests_list = []
                return {
                    "id": row[0],
                    "google_user_id": row[1],
                    "email": row[2],
                    "name": row[3] or (row[2].split("@")[0].replace(".", " ").replace("_", " ").title() if row[2] else None),
                    "first_name": row[4] or (row[3].split()[0] if row[3] else None),
                    "last_name": row[5] or (" ".join(row[3].split()[1:]) if row[3] and len(row[3].split()) > 1 else None),
                    "given_name": row[4] or (row[3].split()[0] if row[3] else None),
                    "family_name": row[5] or (" ".join(row[3].split()[1:]) if row[3] and len(row[3].split()) > 1 else None),
                    "phone_number": row[6],
                    "date_of_birth": row[7],
                    "picture_url": row[8],
                    "last_login_at": str(row[9]) if row[9] else None,
                    "created_at": str(row[10]) if row[10] else None,
                    "updated_at": str(row[11]) if row[11] else None,
                    "preferences": {
                        "home_airport": row[12] or "ATL",
                        "preferred_style": row[13] or "balanced",
                        "preferred_budget": row[14] or "moderate",
                        "seat_preference": row[15],
                        "interests": interests_list
                    }
                }
            else:
                interests_raw = row["interests"]
                try:
                    interests_list = json.loads(interests_raw) if interests_raw else []
                except Exception:
                    interests_list = []
                u_email = row["email"] or ""
                u_name = row["name"] or (u_email.split("@")[0].replace(".", " ").replace("_", " ").title() if u_email else None)
                return {
                    "id": row["id"],
                    "google_user_id": row["google_user_id"],
                    "email": u_email,
                    "name": u_name,
                    "first_name": row["first_name"] or (u_name.split()[0] if u_name else None),
                    "last_name": row["last_name"] or (" ".join(u_name.split()[1:]) if u_name and len(u_name.split()) > 1 else None),
                    "given_name": row["first_name"] or (u_name.split()[0] if u_name else None),
                    "family_name": row["last_name"] or (" ".join(u_name.split()[1:]) if u_name and len(u_name.split()) > 1 else None),

                    "phone_number": row["phone_number"],
                    "date_of_birth": row["date_of_birth"],
                    "picture_url": row["picture_url"],
                    "last_login_at": str(row["last_login_at"]) if row["last_login_at"] else None,
                    "created_at": str(row["created_at"]) if row["created_at"] else None,
                    "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
                    "preferences": {
                        "home_airport": row["home_airport"] or "ATL",
                        "preferred_style": row["preferred_style"] or "balanced",
                        "preferred_budget": row["preferred_budget"] or "moderate",
                        "seat_preference": row["seat_preference"],
                        "interests": interests_list
                    }
                }
        finally:
            conn.close()

    def ensure_user_exists(self, user_id: str, email: Optional[str] = None, name: Optional[str] = None) -> dict[str, Any]:
        """Ensures user record exists by user_id (which is the email address), auto-creating user if missing."""
        clean_id = (user_id or "").lower().strip()
        existing = self.get_user_by_id(clean_id)
        if existing:
            return existing

        user_email = (email or clean_id).lower().strip()
        user_id_val = user_email

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            if name:
                user_name = name
            else:
                handle = user_email.split("@")[0].replace(".", " ").replace("_", " ").strip()
                user_name = handle.title() if handle else user_email

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO users.users (id, email, name, created_at, updated_at, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, 'auto_provision', 'auto_provision')
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, name = COALESCE(EXCLUDED.name, users.users.name);
                """
                cursor.execute(sql, (user_id_val, user_email, user_name, now_iso, now_iso))
            else:
                sql = """
                INSERT INTO users (id, email, name, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, 'auto_provision', 'auto_provision')
                ON CONFLICT(id) DO UPDATE SET email = excluded.email, name = COALESCE(excluded.name, users.name);
                """
                cursor.execute(sql, (user_id_val, user_email, user_name, now_iso, now_iso))

            conn.commit()
        except Exception as e:
            print(f"[USER DAO NOTICE] Auto-provision user '{user_id_val}' notice: {e}")
        finally:
            conn.close()

        res = self.get_user_by_id(user_id_val) or self.get_user_by_id(clean_id)
        if not res:
            res = {
                "id": user_id_val,
                "email": user_email,
                "name": user_name,
                "first_name": user_name.split()[0] if user_name else "",
                "last_name": " ".join(user_name.split()[1:]) if user_name and len(user_name.split()) > 1 else "",
                "preferences": {
                    "home_airport": "ATL",
                    "preferred_style": "balanced",
                    "preferred_budget": "moderate",
                    "seat_preference": None,
                    "interests": []
                }
            }
        return res





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
        """Updates user preferences in user_preferences table."""
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
            print(f"[USER DAO] Updated preferences for user '{user_id}'.")
            return True

        except Exception as err:
            print(f"[USER DAO WARN] Update preferences failed: {err}")
            return False
        finally:
            conn.close()
