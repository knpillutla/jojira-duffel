"""
Dedicated StayOrderDAO for managing `orders.stay_orders` table.
Single Responsibility: Encapsulates hotel and accommodation stay orders.
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Optional
from ..config import DuffelConfig


class StayOrderDAO:
    """
    Single-responsibility DAO for `orders.stay_orders` database table.
    """

    def __init__(self, config: Optional[DuffelConfig] = None):
        self.config = config or DuffelConfig()
        self.enabled = getattr(self.config, "postgres_enabled", True)
        self.host = getattr(self.config, "postgres_host", "127.0.0.1")
        self.port = getattr(self.config, "postgres_port", 5432)
        self.database = getattr(self.config, "postgres_db", "jojira_duffel")
        self.user = getattr(self.config, "postgres_user", "postgres")
        self.password = getattr(self.config, "postgres_password", "postgres")
        self.url = getattr(self.config, "postgres_url", "")

        self.db_engine = "sqlite_fallback"
        self._pg_conn = None
        self._sqlite_file = os.path.join("outputs", "jojira_orders.db")
        os.makedirs(os.path.dirname(self._sqlite_file), exist_ok=True)

        if self.enabled:
            try:
                import psycopg2
                if self.url:
                    self._pg_conn = psycopg2.connect(self.url)
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
                self.db_engine = "postgresql"
            except Exception:
                self.db_engine = "sqlite_fallback"

        self._init_db()

    def _get_connection(self):
        if self.db_engine == "postgresql" and self._pg_conn:
            try:
                if self._pg_conn.closed == 0:
                    return self._pg_conn
            except Exception:
                pass
        return sqlite3.connect(self._sqlite_file)

    def _init_db(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                ddl = """
                CREATE SCHEMA IF NOT EXISTS orders;

                CREATE TABLE IF NOT EXISTS orders.stay_orders (
                    id VARCHAR(100) PRIMARY KEY,
                    duffel_order_id VARCHAR(100) UNIQUE NOT NULL,
                    user_id VARCHAR(100),
                    bundle_id VARCHAR(100),
                    promo_code VARCHAR(50),
                    gross_amount NUMERIC(10, 2),
                    discount_amount NUMERIC(10, 2),
                    quote_id VARCHAR(100),
                    booking_reference VARCHAR(50) NOT NULL,
                    accommodation_id VARCHAR(100),
                    accommodation_name VARCHAR(255),
                    check_in_date VARCHAR(50),
                    check_out_date VARCHAR(50),
                    rooms INT DEFAULT 1,
                    status VARCHAR(50) NOT NULL DEFAULT 'confirmed',
                    total_amount NUMERIC(10, 2) NOT NULL,
                    total_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    payment_status VARCHAR(50) DEFAULT 'paid',
                    payment_method VARCHAR(50) DEFAULT 'balance',
                    guests JSONB,
                    created_at VARCHAR(50),
                    updated_at VARCHAR(50)
                );
                CREATE INDEX IF NOT EXISTS idx_stay_orders_duffel_id ON orders.stay_orders(duffel_order_id);
                CREATE INDEX IF NOT EXISTS idx_stay_orders_user_id ON orders.stay_orders(user_id);
                """
                cursor.execute(ddl)
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS stay_orders (
                    id TEXT PRIMARY KEY,
                    duffel_order_id TEXT UNIQUE NOT NULL,
                    user_id TEXT,
                    bundle_id TEXT,
                    promo_code TEXT,
                    gross_amount TEXT,
                    discount_amount TEXT,
                    quote_id TEXT,
                    booking_reference TEXT NOT NULL,
                    accommodation_id TEXT,
                    accommodation_name TEXT,
                    check_in_date TEXT,
                    check_out_date TEXT,
                    rooms INTEGER DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    total_amount TEXT NOT NULL,
                    total_currency TEXT NOT NULL DEFAULT 'USD',
                    payment_status TEXT DEFAULT 'paid',
                    payment_method TEXT DEFAULT 'balance',
                    guests TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_stay_orders_duffel_id ON stay_orders(duffel_order_id);
                CREATE INDEX IF NOT EXISTS idx_stay_orders_user_id ON stay_orders(user_id);
                """
                cursor.executescript(ddl)
                conn.commit()

            cols = [
                ("user_id", "VARCHAR(100)", "TEXT"),
                ("bundle_id", "VARCHAR(100)", "TEXT"),
                ("created_by", "VARCHAR(100) DEFAULT 'system'", "TEXT DEFAULT 'system'"),
                ("updated_by", "VARCHAR(100) DEFAULT 'system'", "TEXT DEFAULT 'system'"),
                ("is_test", "BOOLEAN DEFAULT FALSE", "INTEGER DEFAULT 0"),
            ]

            for col_name, pg_t, sq_t in cols:
                try:
                    c_type = pg_t if self.db_engine == "postgresql" else sq_t
                    tbl = "orders.stay_orders" if self.db_engine == "postgresql" else "stay_orders"
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {c_type};")
                    if self.db_engine != "postgresql":
                        conn.commit()
                except Exception:
                    pass
        except Exception as err:
            print(f"[STAY ORDER DAO NOTICE] DB Init notice: {err}")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    def save_stay_order(
        self,
        duffel_order_id: str,
        booking_reference: str,
        total_amount: str,
        total_currency: str = "USD",
        quote_id: Optional[str] = None,
        accommodation_id: Optional[str] = None,
        accommodation_name: Optional[str] = None,
        check_in_date: Optional[str] = None,
        check_out_date: Optional[str] = None,
        rooms: int = 1,
        status: str = "confirmed",
        payment_status: str = "paid",
        payment_method: str = "balance",
        guests: Optional[list[dict[str, Any]]] = None,
        bundle_id: Optional[str] = None,
        promo_code: Optional[str] = None,
        gross_amount: Optional[str] = None,
        discount_amount: Optional[str] = None,
        user_id: Optional[str] = None,
        is_test: bool = False,
    ) -> dict[str, Any]:
        """Persist a hotel stay order to `orders.stay_orders` table (supporting test mode indicator)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        order_id = f"ord_stay_db_{duffel_order_id}"
        guests_json = json.dumps(guests or [])
        gross_val = float(gross_amount or total_amount or 0.0)
        disc_val = float(discount_amount or 0.0)
        is_test_val = 1 if (is_test or "test" in (duffel_order_id or "").lower() or "test" in (booking_reference or "").lower()) else 0


        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO orders.stay_orders (
                    id, duffel_order_id, user_id, bundle_id, promo_code, gross_amount, discount_amount,
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, total_amount, total_currency,
                    payment_status, payment_method, guests, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_order_id) DO UPDATE SET
                    user_id = COALESCE(EXCLUDED.user_id, stay_orders.user_id),
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, user_id, bundle_id, promo_code, gross_val, disc_val,
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, float(total_amount or 0.0), total_currency,
                    payment_status, payment_method, guests_json, now_iso, now_iso
                ))
            else:
                sql = """
                INSERT INTO stay_orders (
                    id, duffel_order_id, user_id, bundle_id, promo_code, gross_amount, discount_amount,
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, total_amount, total_currency,
                    payment_status, payment_method, guests, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(duffel_order_id) DO UPDATE SET
                    user_id = COALESCE(excluded.user_id, stay_orders.user_id),
                    status = excluded.status,
                    payment_status = excluded.payment_status,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, user_id, bundle_id, promo_code, str(gross_val), str(disc_val),
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, str(total_amount), total_currency,
                    payment_status, payment_method, guests_json, now_iso, now_iso
                ))
                conn.commit()
            print(f"[STAY ORDER DAO] Saved stay order '{duffel_order_id}' to database.")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return {
            "id": order_id,
            "duffel_order_id": duffel_order_id,
            "booking_reference": booking_reference,
            "status": status,
            "total_amount": str(total_amount),
            "created_at": now_iso,
        }
