"""
Dedicated TripPlanDAO for managing `users.user_trip_plans` table.
Single Responsibility: Encapsulates AI planner drafts, day-by-day attraction schedules, maps, and suggested package deals.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import sqlite3
from typing import Any, Optional
from ..config import UserServiceConfig


class TripPlanDAO:
    """
    Single-responsibility DAO for `users.user_trip_plans` database table.
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

                CREATE TABLE IF NOT EXISTS users.user_trip_plans (
                    id VARCHAR(100) PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
                    title VARCHAR(255) NOT NULL,
                    prompt TEXT NOT NULL,
                    destination VARCHAR(100),
                    origin VARCHAR(10),
                    trip_duration_days INTEGER,
                    day_by_day_schedule JSONB,
                    package_options JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_trip_plans_user ON users.user_trip_plans(user_id);
                """
                cursor.execute(ddl)
                conn.commit()
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS user_trip_plans (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    destination TEXT,
                    origin TEXT,
                    trip_duration_days INTEGER,
                    day_by_day_schedule TEXT,
                    package_options TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_trip_plans_user ON user_trip_plans(user_id);
                """
                cursor.executescript(ddl)
                conn.commit()
            try:
                tbl = "users.user_trip_plans" if self.db_engine == "postgresql" else "user_trip_plans"
                c_type = "BOOLEAN DEFAULT FALSE" if self.db_engine == "postgresql" else "INTEGER DEFAULT 0"
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN is_test {c_type};")
                if self.db_engine != "postgresql":
                    conn.commit()
            except Exception:
                pass
        except Exception as err:
            print(f"[TRIP PLAN DAO NOTICE] DB Init notice: {err}")
        finally:
            conn.close()


    def save_trip_plan(
        self,
        user_id: str,
        title: str,
        prompt: str,
        destination: Optional[str] = None,
        origin: Optional[str] = None,
        trip_duration_days: Optional[int] = None,
        day_by_day_schedule: Optional[dict[str, Any]] = None,
        package_options: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """Saves a new AI Trip Plan draft into `users.user_trip_plans` database table."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            plan_id = f"plan_{hashlib.md5(f'{user_id}_{prompt}_{now_iso}'.encode()).hexdigest()[:10]}"
            schedule_json_str = json.dumps(day_by_day_schedule or {})
            packages_json_str = json.dumps(package_options or [])

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO users.user_trip_plans (
                    id, user_id, title, prompt, destination, origin, trip_duration_days,
                    day_by_day_schedule, package_options, created_at, updated_at, created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                cursor.execute(sql, (
                    plan_id, user_id, title, prompt, destination, origin, trip_duration_days,
                    schedule_json_str, packages_json_str, now_iso, now_iso, user_id, user_id
                ))
            else:
                sql = """
                INSERT INTO user_trip_plans (
                    id, user_id, title, prompt, destination, origin, trip_duration_days,
                    day_by_day_schedule, package_options, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(sql, (
                    plan_id, user_id, title, prompt, destination, origin, trip_duration_days,
                    schedule_json_str, packages_json_str, now_iso, now_iso, user_id, user_id
                ))
                conn.commit()

            print(f"[TRIP PLAN DAO] Saved AI Trip Plan '{plan_id}' ('{title}') for user '{user_id}'.")
            return plan_id
        finally:
            conn.close()

    def get_user_trip_plans(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves lightweight list of saved AI Trip Plans for a user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT id, title, prompt, destination, origin, trip_duration_days, created_at
                FROM users.user_trip_plans
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """
                cursor.execute(sql, (user_id, limit))
            else:
                sql = """
                SELECT id, title, prompt, destination, origin, trip_duration_days, created_at
                FROM user_trip_plans
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
                        "title": row[1],
                        "prompt": row[2],
                        "destination": row[3],
                        "origin": row[4],
                        "trip_duration_days": row[5],
                        "created_at": str(row[6]) if row[6] else None,
                    })
                else:
                    results.append({
                        "id": row["id"],
                        "title": row["title"],
                        "prompt": row["prompt"],
                        "destination": row["destination"],
                        "origin": row["origin"],
                        "trip_duration_days": row["trip_duration_days"],
                        "created_at": str(row["created_at"]) if row["created_at"] else None,
                    })
            return results
        finally:
            conn.close()

    def get_trip_plan_by_id(self, user_id: str, plan_id: str) -> Optional[dict[str, Any]]:
        """Retrieves complete AI Trip Plan detail including day-by-day schedule and suggested package deals."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT id, title, prompt, destination, origin, trip_duration_days, day_by_day_schedule, package_options, created_at
                FROM users.user_trip_plans
                WHERE user_id = %s AND id = %s
                LIMIT 1;
                """
                cursor.execute(sql, (user_id, plan_id))
            else:
                sql = """
                SELECT id, title, prompt, destination, origin, trip_duration_days, day_by_day_schedule, package_options, created_at
                FROM user_trip_plans
                WHERE user_id = ? AND id = ?
                LIMIT 1;
                """
                cursor.execute(sql, (user_id, plan_id))

            row = cursor.fetchone()
            if not row:
                return None

            if isinstance(row, tuple):
                sch_raw, pkg_raw = row[6], row[7]
                return {
                    "id": row[0],
                    "user_id": user_id,
                    "title": row[1],
                    "prompt": row[2],
                    "destination": row[3],
                    "origin": row[4],
                    "trip_duration_days": row[5],
                    "day_by_day_schedule": json.loads(sch_raw) if sch_raw and isinstance(sch_raw, str) else (sch_raw or {}),
                    "package_options": json.loads(pkg_raw) if pkg_raw and isinstance(pkg_raw, str) else (pkg_raw or []),
                    "created_at": str(row[8]) if row[8] else None,
                }

            sch_raw, pkg_raw = row["day_by_day_schedule"], row["package_options"]
            return {
                "id": row["id"],
                "user_id": user_id,
                "title": row["title"],
                "prompt": row["prompt"],
                "destination": row["destination"],
                "origin": row["origin"],
                "trip_duration_days": row["trip_duration_days"],
                "day_by_day_schedule": json.loads(sch_raw) if sch_raw and isinstance(sch_raw, str) else (sch_raw or {}),
                "package_options": json.loads(pkg_raw) if pkg_raw and isinstance(pkg_raw, str) else (pkg_raw or []),
                "created_at": str(row["created_at"]) if row["created_at"] else None,
            }
        finally:
            conn.close()
