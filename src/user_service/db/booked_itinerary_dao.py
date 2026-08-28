"""
Dedicated BookedItineraryDAO for managing `users.user_booked_itineraries` table.
Single Responsibility: Encapsulates confirmed user travel bookings and links them to live order tickets (flights, hotels, cars, bundles).
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Optional
from ..config import UserServiceConfig


class BookedItineraryDAO:
    """
    Single-responsibility DAO for `users.user_booked_itineraries` database table.
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

                CREATE TABLE IF NOT EXISTS users.user_booked_itineraries (
                    id VARCHAR(100) PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
                    trip_plan_id VARCHAR(100),
                    flight_order_id VARCHAR(100),
                    stay_order_id VARCHAR(100),
                    car_order_id VARCHAR(100),
                    bundle_order_id VARCHAR(100),
                    destination VARCHAR(100) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'confirmed',
                    total_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
                    total_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    booking_details JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system',
                    is_test BOOLEAN DEFAULT FALSE
                );
                CREATE INDEX IF NOT EXISTS idx_booked_itin_user ON users.user_booked_itineraries(user_id);
                """
                cursor.execute(ddl)
                conn.commit()
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS user_booked_itineraries (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    trip_plan_id TEXT,
                    flight_order_id TEXT,
                    stay_order_id TEXT,
                    car_order_id TEXT,
                    bundle_order_id TEXT,
                    destination TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    total_amount REAL NOT NULL DEFAULT 0.00,
                    total_currency TEXT NOT NULL DEFAULT 'USD',
                    booking_details TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system',
                    is_test INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_booked_itin_user ON user_booked_itineraries(user_id);
                """
                cursor.executescript(ddl)
                conn.commit()
            try:
                tbl = "users.user_booked_itineraries" if self.db_engine == "postgresql" else "user_booked_itineraries"
                c_type = "BOOLEAN DEFAULT FALSE" if self.db_engine == "postgresql" else "INTEGER DEFAULT 0"
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN is_test {c_type};")
                conn.commit()
            except Exception:
                conn.rollback()

        except Exception as err:
            print(f"[BOOKED ITINERARY DAO NOTICE] DB Init notice: {err}")
        finally:
            conn.close()

    def create_booked_itinerary(
        self,
        user_id: Optional[str],
        title: str,
        destination: str,
        total_amount: float,
        total_currency: str = "USD",
        status: str = "confirmed",
        trip_plan_id: Optional[str] = None,
        flight_order_id: Optional[str] = None,
        stay_order_id: Optional[str] = None,
        car_order_id: Optional[str] = None,
        bundle_order_id: Optional[str] = None,
        booking_details: Optional[dict[str, Any]] = None,
        is_test: bool = False,
    ) -> str:
        """Persists a confirmed travel booking (supporting test mode indicator)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            booking_id = f"bkg_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}"
            user_id_val = user_id or "guest"
            details_json_str = json.dumps(booking_details or {})
            is_test_val = 1 if (is_test or "test" in (title or "").lower() or "test" in (booking_id or "").lower()) else 0

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO users.user_booked_itineraries (
                    id, user_id, trip_plan_id, flight_order_id, stay_order_id, car_order_id, bundle_order_id,
                    destination, title, status, total_amount, total_currency, booking_details, is_test, created_at, updated_at, created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                cursor.execute(sql, (
                    booking_id, user_id_val, trip_plan_id, flight_order_id, stay_order_id, car_order_id, bundle_order_id,
                    destination, title, status, total_amount, total_currency, details_json_str, bool(is_test_val), now_iso, now_iso, user_id_val, user_id_val
                ))
            else:
                sql = """
                INSERT INTO user_booked_itineraries (
                    id, user_id, trip_plan_id, flight_order_id, stay_order_id, car_order_id, bundle_order_id,
                    destination, title, status, total_amount, total_currency, booking_details, is_test, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(sql, (
                    booking_id, user_id_val, trip_plan_id, flight_order_id, stay_order_id, car_order_id, bundle_order_id,
                    destination, title, status, total_amount, total_currency, details_json_str, is_test_val, now_iso, now_iso, user_id_val, user_id_val
                ))
                conn.commit()


            print(f"[BOOKED ITINERARY DAO] Recorded confirmed booking '{booking_id}' ('{title}') for user '{user_id}'.")
            return booking_id
        finally:
            conn.close()

    def get_user_booked_itineraries(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves list of confirmed booked itineraries for a user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT id, title, destination, status, total_amount, total_currency, flight_order_id, stay_order_id, car_order_id, bundle_order_id, is_test, created_at, created_by, updated_at, updated_by
                FROM users.user_booked_itineraries
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """
                cursor.execute(sql, (user_id, limit))
            else:
                sql = """
                SELECT id, title, destination, status, total_amount, total_currency, flight_order_id, stay_order_id, car_order_id, bundle_order_id, is_test, created_at, created_by, updated_at, updated_by
                FROM user_booked_itineraries
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
                        "destination": row[2],
                        "status": row[3],
                        "total_amount": float(row[4] or 0.0),
                        "total_currency": row[5],
                        "flight_order_id": row[6],
                        "stay_order_id": row[7],
                        "car_order_id": row[8],
                        "bundle_order_id": row[9],
                        "is_test": bool(row[10]),
                        "created_at": str(row[11]) if row[11] else None,
                        "created_by": row[12] or user_id,
                        "updated_at": str(row[13]) if row[13] else None,
                        "updated_by": row[14] or user_id,
                    })
                else:
                    results.append({
                        "id": row["id"],
                        "title": row["title"],
                        "destination": row["destination"],
                        "status": row["status"],
                        "total_amount": float(row["total_amount"] or 0.0),
                        "total_currency": row["total_currency"],
                        "flight_order_id": row["flight_order_id"],
                        "stay_order_id": row["stay_order_id"],
                        "car_order_id": row["car_order_id"],
                        "bundle_order_id": row["bundle_order_id"],
                        "is_test": bool(row["is_test"]) if "is_test" in row.keys() else False,
                        "created_at": str(row["created_at"]) if row["created_at"] else None,
                        "created_by": row["created_by"] if "created_by" in row.keys() else user_id,
                        "updated_at": str(row["updated_at"]) if "updated_at" in row.keys() else None,
                        "updated_by": row["updated_by"] if "updated_by" in row.keys() else user_id,
                    })
            return results
        finally:
            conn.close()

    def get_booked_itinerary_by_id(self, user_id: str, booking_id: str) -> Optional[dict[str, Any]]:
        """Retrieves full confirmed booking details with linked live order tickets."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT id, trip_plan_id, flight_order_id, stay_order_id, car_order_id, bundle_order_id,
                       destination, title, status, total_amount, total_currency, booking_details, is_test, created_at, created_by, updated_at, updated_by
                FROM users.user_booked_itineraries
                WHERE user_id = %s AND id = %s
                LIMIT 1;
                """
                cursor.execute(sql, (user_id, booking_id))
            else:
                sql = """
                SELECT id, trip_plan_id, flight_order_id, stay_order_id, car_order_id, bundle_order_id,
                       destination, title, status, total_amount, total_currency, booking_details, is_test, created_at, created_by, updated_at, updated_by
                FROM user_booked_itineraries
                WHERE user_id = ? AND id = ?
                LIMIT 1;
                """
                cursor.execute(sql, (user_id, booking_id))

            row = cursor.fetchone()
            if not row:
                return None

            if isinstance(row, tuple):
                d_raw = row[11]
                return {
                    "id": row[0],
                    "user_id": user_id,
                    "trip_plan_id": row[1],
                    "flight_order_id": row[2],
                    "stay_order_id": row[3],
                    "car_order_id": row[4],
                    "bundle_order_id": row[5],
                    "destination": row[6],
                    "title": row[7],
                    "status": row[8],
                    "total_amount": float(row[9] or 0.0),
                    "total_currency": row[10],
                    "booking_details": json.loads(d_raw) if d_raw and isinstance(d_raw, str) else (d_raw or {}),
                    "is_test": bool(row[12]),
                    "created_at": str(row[13]) if row[13] else None,
                    "created_by": row[14] or user_id,
                    "updated_at": str(row[15]) if row[15] else None,
                    "updated_by": row[16] or user_id,
                }

            d_raw = row["booking_details"]
            return {
                "id": row["id"],
                "user_id": user_id,
                "trip_plan_id": row["trip_plan_id"],
                "flight_order_id": row["flight_order_id"],
                "stay_order_id": row["stay_order_id"],
                "car_order_id": row["car_order_id"],
                "bundle_order_id": row["bundle_order_id"],
                "destination": row["destination"],
                "title": row["title"],
                "status": row["status"],
                "total_amount": float(row["total_amount"] or 0.0),
                "total_currency": row["total_currency"],
                "booking_details": json.loads(d_raw) if d_raw and isinstance(d_raw, str) else (d_raw or {}),
                "is_test": bool(row["is_test"]) if "is_test" in row.keys() else False,
                "created_at": str(row["created_at"]) if row["created_at"] else None,
                "created_by": row["created_by"] if "created_by" in row.keys() else user_id,
                "updated_at": str(row["updated_at"]) if "updated_at" in row.keys() else None,
                "updated_by": row["updated_by"] if "updated_by" in row.keys() else user_id,
            }
        finally:
            conn.close()
