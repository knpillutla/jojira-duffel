"""
Dedicated BundleOrderDAO for managing `orders.bundle_orders` table.
Single Responsibility: Encapsulates combined travel package bundle orders (Flight + Hotel + Car).
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Optional
from ..config import DuffelConfig


class BundleOrderDAO:
    """
    Single-responsibility DAO for `orders.bundle_orders` database table.
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

                CREATE TABLE IF NOT EXISTS orders.bundle_orders (
                    id VARCHAR(100) PRIMARY KEY,
                    duffel_bundle_id VARCHAR(100) UNIQUE NOT NULL,
                    user_id VARCHAR(100),
                    itinerary_id VARCHAR(100),
                    promo_code VARCHAR(50),
                    gross_amount NUMERIC(10, 2),
                    discount_amount NUMERIC(10, 2),
                    flight_order_id VARCHAR(100),
                    stay_order_id VARCHAR(100),
                    car_order_id VARCHAR(100),
                    status VARCHAR(50) NOT NULL DEFAULT 'confirmed',
                    combined_total_amount NUMERIC(10, 2) NOT NULL,
                    total_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    payment_status VARCHAR(50) DEFAULT 'paid',
                    payment_method VARCHAR(50) DEFAULT 'balance',
                    flight_details JSONB,
                    stay_details JSONB,
                    car_details JSONB,
                    created_at VARCHAR(50),
                    updated_at VARCHAR(50)
                );
                CREATE INDEX IF NOT EXISTS idx_bundle_orders_id ON orders.bundle_orders(duffel_bundle_id);
                CREATE INDEX IF NOT EXISTS idx_bundle_orders_user_id ON orders.bundle_orders(user_id);
                CREATE INDEX IF NOT EXISTS idx_bundle_orders_itin_id ON orders.bundle_orders(itinerary_id);
                """
                cursor.execute(ddl)
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS bundle_orders (
                    id TEXT PRIMARY KEY,
                    duffel_bundle_id TEXT UNIQUE NOT NULL,
                    user_id TEXT,
                    itinerary_id TEXT,
                    promo_code TEXT,
                    gross_amount TEXT,
                    discount_amount TEXT,
                    flight_order_id TEXT,
                    stay_order_id TEXT,
                    car_order_id TEXT,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    combined_total_amount TEXT NOT NULL,
                    total_currency TEXT NOT NULL DEFAULT 'USD',
                    payment_status TEXT DEFAULT 'paid',
                    payment_method TEXT DEFAULT 'balance',
                    flight_details TEXT,
                    stay_details TEXT,
                    car_details TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_bundle_orders_id ON bundle_orders(duffel_bundle_id);
                CREATE INDEX IF NOT EXISTS idx_bundle_orders_user_id ON bundle_orders(user_id);
                CREATE INDEX IF NOT EXISTS idx_bundle_orders_itin_id ON bundle_orders(itinerary_id);
                """
                cursor.executescript(ddl)
                conn.commit()

            cols = [
                ("user_id", "VARCHAR(100)", "TEXT"),
                ("itinerary_id", "VARCHAR(100)", "TEXT"),
                ("created_by", "VARCHAR(100) DEFAULT 'system'", "TEXT DEFAULT 'system'"),
                ("updated_by", "VARCHAR(100) DEFAULT 'system'", "TEXT DEFAULT 'system'"),
                ("is_test", "BOOLEAN DEFAULT FALSE", "INTEGER DEFAULT 0"),
            ]

            for col_name, pg_t, sq_t in cols:
                try:
                    c_type = pg_t if self.db_engine == "postgresql" else sq_t
                    tbl = "orders.bundle_orders" if self.db_engine == "postgresql" else "bundle_orders"
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {c_type};")
                    if self.db_engine != "postgresql":
                        conn.commit()
                except Exception:
                    pass
        except Exception as err:
            print(f"[BUNDLE ORDER DAO NOTICE] DB Init notice: {err}")
        finally:
            if self.db_engine != "postgresql":
                conn.close()


    def save_bundle_order(
        self,
        duffel_bundle_id: str,
        flight_order_id: Optional[str] = None,
        stay_order_id: Optional[str] = None,
        car_order_id: Optional[str] = None,
        combined_total_amount: str = "0.00",
        total_currency: str = "USD",
        status: str = "confirmed",
        payment_status: str = "paid",
        payment_method: str = "balance",
        flight_details: Optional[dict[str, Any]] = None,
        stay_details: Optional[dict[str, Any]] = None,
        car_details: Optional[dict[str, Any]] = None,
        promo_code: Optional[str] = None,
        gross_amount: Optional[str] = None,
        discount_amount: Optional[str] = None,
        user_id: Optional[str] = None,
        itinerary_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Persist a combined travel package bundle order to `orders.bundle_orders` table."""
        now_iso = datetime.now(timezone.utc).isoformat()
        order_id = f"ord_bundle_db_{duffel_bundle_id}"
        fl_json = json.dumps(flight_details or {})
        st_json = json.dumps(stay_details or {})
        cr_json = json.dumps(car_details or {})
        gross_val = float(gross_amount or combined_total_amount or 0.0)
        disc_val = float(discount_amount or 0.0)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO orders.bundle_orders (
                    id, duffel_bundle_id, user_id, itinerary_id, promo_code, gross_amount, discount_amount,
                    flight_order_id, stay_order_id, car_order_id, status, combined_total_amount,
                    total_currency, payment_status, payment_method, flight_details,
                    stay_details, car_details, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_bundle_id) DO UPDATE SET
                    user_id = COALESCE(EXCLUDED.user_id, bundle_orders.user_id),
                    itinerary_id = COALESCE(EXCLUDED.itinerary_id, bundle_orders.itinerary_id),
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_bundle_id, user_id, itinerary_id, promo_code, gross_val, disc_val,
                    flight_order_id, stay_order_id, car_order_id, status, float(combined_total_amount or 0.0),
                    total_currency, payment_status, payment_method, fl_json, st_json, cr_json, now_iso, now_iso
                ))
            else:
                sql = """
                INSERT INTO bundle_orders (
                    id, duffel_bundle_id, user_id, itinerary_id, promo_code, gross_amount, discount_amount,
                    flight_order_id, stay_order_id, car_order_id, status, combined_total_amount,
                    total_currency, payment_status, payment_method, flight_details,
                    stay_details, car_details, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(duffel_bundle_id) DO UPDATE SET
                    user_id = COALESCE(excluded.user_id, bundle_orders.user_id),
                    itinerary_id = COALESCE(excluded.itinerary_id, bundle_orders.itinerary_id),
                    status = excluded.status,
                    payment_status = excluded.payment_status,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_bundle_id, user_id, itinerary_id, promo_code, str(gross_val), str(disc_val),
                    flight_order_id, stay_order_id, car_order_id, status, str(combined_total_amount),
                    total_currency, payment_status, payment_method, fl_json, st_json, cr_json, now_iso, now_iso
                ))
                conn.commit()
            print(f"[BUNDLE ORDER DAO] Saved bundle order '{duffel_bundle_id}' to database.")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return {
            "id": order_id,
            "duffel_bundle_id": duffel_bundle_id,
            "status": status,
            "combined_total_amount": str(combined_total_amount),
            "created_at": now_iso,
        }
