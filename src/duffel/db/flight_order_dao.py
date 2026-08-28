"""
Dedicated FlightOrderDAO for managing `orders.flight_orders` table.
Single Responsibility: Encapsulates flight order creation, status updates, payment tracking, and ticketing.
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Optional
from ..config import DuffelConfig


class FlightOrderDAO:
    """
    Single-responsibility DAO for `orders.flight_orders` database table.
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

                CREATE TABLE IF NOT EXISTS orders.flight_orders (
                    id VARCHAR(100) PRIMARY KEY,
                    duffel_order_id VARCHAR(100) UNIQUE NOT NULL,
                    user_id VARCHAR(100),
                    bundle_id VARCHAR(100),
                    promo_code VARCHAR(50),
                    gross_amount NUMERIC(10, 2),
                    discount_amount NUMERIC(10, 2),
                    booking_reference VARCHAR(50) NOT NULL,
                    order_type VARCHAR(20) NOT NULL DEFAULT 'hold',
                    status VARCHAR(50) NOT NULL DEFAULT 'hold',
                    total_amount NUMERIC(10, 2) NOT NULL,
                    total_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    payment_status VARCHAR(50) DEFAULT 'pending',
                    payment_method VARCHAR(50) DEFAULT 'balance',
                    payment_details JSONB,
                    payment_required_by VARCHAR(50),
                    email_confirmation_status VARCHAR(50) DEFAULT 'pending',
                    email_recipient VARCHAR(255),
                    passengers JSONB,
                    slices JSONB,
                    created_at VARCHAR(50),
                    updated_at VARCHAR(50)
                );
                CREATE INDEX IF NOT EXISTS idx_flight_orders_duffel_id ON orders.flight_orders(duffel_order_id);
                CREATE INDEX IF NOT EXISTS idx_flight_orders_user_id ON orders.flight_orders(user_id);
                """
                cursor.execute(ddl)
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS flight_orders (
                    id TEXT PRIMARY KEY,
                    duffel_order_id TEXT UNIQUE NOT NULL,
                    user_id TEXT,
                    bundle_id TEXT,
                    promo_code TEXT,
                    gross_amount TEXT,
                    discount_amount TEXT,
                    booking_reference TEXT NOT NULL,
                    order_type TEXT NOT NULL DEFAULT 'hold',
                    status TEXT NOT NULL DEFAULT 'hold',
                    total_amount TEXT NOT NULL,
                    total_currency TEXT NOT NULL DEFAULT 'USD',
                    payment_status TEXT DEFAULT 'pending',
                    payment_method TEXT DEFAULT 'balance',
                    payment_details TEXT,
                    payment_required_by TEXT,
                    email_confirmation_status TEXT DEFAULT 'pending',
                    email_recipient TEXT,
                    passengers TEXT,
                    slices TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_flight_orders_duffel_id ON flight_orders(duffel_order_id);
                CREATE INDEX IF NOT EXISTS idx_flight_orders_user_id ON flight_orders(user_id);
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
                    tbl = "orders.flight_orders" if self.db_engine == "postgresql" else "flight_orders"
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {c_type};")
                    if self.db_engine != "postgresql":
                        conn.commit()
                except Exception:
                    pass
        except Exception as err:
            print(f"[FLIGHT ORDER DAO] DB Init notice: {err}")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    def save_flight_order(
        self,
        duffel_order_id: str,
        booking_reference: str,
        total_amount: str,
        total_currency: str = "USD",
        order_type: str = "hold",
        status: str = "hold",
        payment_method: str = "balance",
        payment_required_by: Optional[str] = None,
        email_recipient: Optional[str] = "customer@example.com",
        passengers: Optional[list[dict[str, Any]]] = None,
        slices: Optional[list[dict[str, Any]]] = None,
        payment_status: str = "pending",
        email_confirmation_status: str = "pending",
        bundle_id: Optional[str] = None,
        promo_code: Optional[str] = None,
        gross_amount: Optional[str] = None,
        discount_amount: Optional[str] = None,
        user_id: Optional[str] = None,
        is_test: bool = False,
    ) -> dict[str, Any]:
        """Persist a flight order to `orders.flight_orders` table (supporting test mode indicator)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        order_id = f"ord_db_{duffel_order_id}"
        passengers_json = json.dumps(passengers or [])
        slices_json = json.dumps(slices or [])
        gross_val = float(gross_amount or total_amount or 0.0)
        disc_val = float(discount_amount or 0.0)
        is_test_val = 1 if (is_test or "test" in (duffel_order_id or "").lower() or "test" in (booking_reference or "").lower()) else 0

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO orders.flight_orders (
                    id, duffel_order_id, booking_reference, total_amount, total_currency,
                    order_type, status, payment_method, payment_required_by, email_recipient,
                    passengers, slices, payment_status, email_confirmation_status, bundle_id,
                    promo_code, gross_amount, discount_amount, user_id, is_test, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_order_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    is_test = EXCLUDED.is_test,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, booking_reference, float(total_amount), total_currency,
                    order_type, status, payment_method, payment_required_by, email_recipient,
                    passengers_json, slices_json, payment_status, email_confirmation_status, bundle_id,
                    promo_code, gross_val, disc_val, user_id, bool(is_test_val), now_iso, now_iso
                ))
            else:
                sql = """
                INSERT OR REPLACE INTO flight_orders (
                    id, duffel_order_id, booking_reference, total_amount, total_currency,
                    order_type, status, payment_method, payment_required_by, email_recipient,
                    passengers, slices, payment_status, email_confirmation_status, bundle_id,
                    promo_code, gross_amount, discount_amount, user_id, is_test, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, booking_reference, str(total_amount), total_currency,
                    order_type, status, payment_method, payment_required_by, email_recipient,
                    passengers_json, slices_json, payment_status, email_confirmation_status, bundle_id,
                    promo_code, str(gross_val), str(disc_val), user_id, is_test_val, now_iso, now_iso
                ))
                conn.commit()

            print(f"[FLIGHT ORDER DAO] Saved flight order '{duffel_order_id}' to database.")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return {
            "id": order_id,
            "duffel_order_id": duffel_order_id,
            "booking_reference": booking_reference,
            "status": status,
            "payment_status": payment_status,
            "created_at": now_iso,
        }
