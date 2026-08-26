"""
PostgreSQL Data Access Object (OrderDAO) for Jojira Duffel Flight Orders.
Handles order persistence on hold creation, status updates on ticketing, payment status tracking, and email confirmation status.
"""

from datetime import datetime, timezone
import json
import logging
import os
import sqlite3
from typing import Any, Optional

from ..config import DuffelConfig

logger = logging.getLogger(__name__)


class OrderDAO:
    """Data Access Object for managing flight order persistence and lifecycle updates."""

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
                import psycopg2.extras
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
            except Exception as err:
                logger.info(f"[ORDER DAO] PostgreSQL connection not established: {err}. Using local SQLite engine fallback.")
                self.db_engine = "sqlite_fallback"

        self.init_db()

    def _get_connection(self):
        if self.db_engine == "postgresql" and self._pg_conn:
            try:
                if self._pg_conn.closed == 0:
                    return self._pg_conn
            except Exception:
                pass
        return sqlite3.connect(self._sqlite_file)

    def init_db(self):
        """Create flight_orders table and indexes if they do not exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                ddl = """
                CREATE TABLE IF NOT EXISTS flight_orders (
                    id VARCHAR(100) PRIMARY KEY,
                    duffel_order_id VARCHAR(100) UNIQUE NOT NULL,
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
                CREATE INDEX IF NOT EXISTS idx_flight_orders_duffel_id ON flight_orders(duffel_order_id);
                CREATE INDEX IF NOT EXISTS idx_flight_orders_status ON flight_orders(status);

                CREATE TABLE IF NOT EXISTS stay_orders (
                    id VARCHAR(100) PRIMARY KEY,
                    duffel_order_id VARCHAR(100) UNIQUE NOT NULL,
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
                CREATE INDEX IF NOT EXISTS idx_stay_orders_duffel_id ON stay_orders(duffel_order_id);

                CREATE TABLE IF NOT EXISTS car_orders (
                    id VARCHAR(100) PRIMARY KEY,
                    duffel_order_id VARCHAR(100) UNIQUE NOT NULL,
                    bundle_id VARCHAR(100),
                    promo_code VARCHAR(50),
                    gross_amount NUMERIC(10, 2),
                    discount_amount NUMERIC(10, 2),
                    offer_id VARCHAR(100),
                    booking_reference VARCHAR(50) NOT NULL,
                    supplier_name VARCHAR(100),
                    vehicle_name VARCHAR(100),
                    pickup_location VARCHAR(100),
                    dropoff_location VARCHAR(100),
                    pickup_datetime VARCHAR(50),
                    dropoff_datetime VARCHAR(50),
                    driver_age INT DEFAULT 30,
                    driver_details JSONB,
                    status VARCHAR(50) NOT NULL DEFAULT 'confirmed',
                    total_amount NUMERIC(10, 2) NOT NULL,
                    total_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    payment_status VARCHAR(50) DEFAULT 'paid',
                    payment_method VARCHAR(50) DEFAULT 'balance',
                    created_at VARCHAR(50),
                    updated_at VARCHAR(50)
                );
                CREATE INDEX IF NOT EXISTS idx_car_orders_duffel_id ON car_orders(duffel_order_id);

                CREATE TABLE IF NOT EXISTS bundle_orders (
                    id VARCHAR(100) PRIMARY KEY,
                    duffel_bundle_id VARCHAR(100) UNIQUE NOT NULL,
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
                CREATE INDEX IF NOT EXISTS idx_bundle_orders_id ON bundle_orders(duffel_bundle_id);

                CREATE TABLE IF NOT EXISTS itinerary_templates (
                    id VARCHAR(100) PRIMARY KEY,
                    destination VARCHAR(100) NOT NULL,
                    duration_days INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    map_center JSONB,
                    template_days JSONB NOT NULL,
                    tags JSONB,
                    created_at VARCHAR(50),
                    updated_at VARCHAR(50)
                );
                CREATE INDEX IF NOT EXISTS idx_itinerary_dest_dur ON itinerary_templates(destination, duration_days);
                """
                cursor.execute(ddl)
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS flight_orders (
                    id TEXT PRIMARY KEY,
                    duffel_order_id TEXT UNIQUE NOT NULL,
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

                CREATE TABLE IF NOT EXISTS stay_orders (
                    id TEXT PRIMARY KEY,
                    duffel_order_id TEXT UNIQUE NOT NULL,
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

                CREATE TABLE IF NOT EXISTS car_orders (
                    id TEXT PRIMARY KEY,
                    duffel_order_id TEXT UNIQUE NOT NULL,
                    bundle_id TEXT,
                    promo_code TEXT,
                    gross_amount TEXT,
                    discount_amount TEXT,
                    offer_id TEXT,
                    booking_reference TEXT NOT NULL,
                    supplier_name TEXT,
                    vehicle_name TEXT,
                    pickup_location TEXT,
                    dropoff_location TEXT,
                    pickup_datetime TEXT,
                    dropoff_datetime TEXT,
                    driver_age INTEGER DEFAULT 30,
                    driver_details TEXT,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    total_amount TEXT NOT NULL,
                    total_currency TEXT NOT NULL DEFAULT 'USD',
                    payment_status TEXT DEFAULT 'paid',
                    payment_method TEXT DEFAULT 'balance',
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_car_orders_duffel_id ON car_orders(duffel_order_id);

                CREATE TABLE IF NOT EXISTS bundle_orders (
                    id TEXT PRIMARY KEY,
                    duffel_bundle_id TEXT UNIQUE NOT NULL,
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

                CREATE TABLE IF NOT EXISTS itinerary_templates (
                    id TEXT PRIMARY KEY,
                    destination TEXT NOT NULL,
                    duration_days INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    map_center TEXT,
                    template_days TEXT NOT NULL,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_itinerary_dest_dur ON itinerary_templates(destination, duration_days);
                """
                cursor.executescript(ddl)
                conn.commit()

            # Ensure bundle_id, promo_code, gross_amount, discount_amount columns exist on existing tables
            cols_to_add = [
                ("bundle_id", "VARCHAR(100)", "TEXT"),
                ("promo_code", "VARCHAR(50)", "TEXT"),
                ("gross_amount", "NUMERIC(10, 2)", "TEXT"),
                ("discount_amount", "NUMERIC(10, 2)", "TEXT"),
            ]
            for tbl in ["flight_orders", "stay_orders", "car_orders", "bundle_orders"]:
                for col_name, pg_type, sq_type in cols_to_add:
                    try:
                        col_type = pg_type if self.db_engine == "postgresql" else sq_type
                        alt_sql = f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_type};"
                        cursor.execute(alt_sql)
                        if self.db_engine != "postgresql":
                            conn.commit()
                    except Exception:
                        pass
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    def save_hold_order(
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
    ) -> dict[str, Any]:
        """
        Persist a flight order when created in 'hold' (or 'instant') status.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        order_id = f"ord_db_{duffel_order_id}"
        passengers_json = json.dumps(passengers or [])
        slices_json = json.dumps(slices or [])
        gross_val = float(gross_amount or total_amount or 0.0)
        disc_val = float(discount_amount or 0.0)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO flight_orders (
                    id, duffel_order_id, bundle_id, promo_code, gross_amount, discount_amount,
                    booking_reference, order_type, status, total_amount, total_currency,
                    payment_status, payment_method, payment_required_by, email_confirmation_status,
                    email_recipient, passengers, slices, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_order_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, bundle_id, promo_code, gross_val, disc_val,
                    booking_reference, order_type, status, float(total_amount or 0.0), total_currency,
                    payment_status, payment_method, payment_required_by, email_confirmation_status,
                    email_recipient, passengers_json, slices_json, now_iso, now_iso
                ))
            else:
                sql = """
                INSERT INTO flight_orders (
                    id, duffel_order_id, bundle_id, promo_code, gross_amount, discount_amount,
                    booking_reference, order_type, status, total_amount, total_currency,
                    payment_status, payment_method, payment_required_by, email_confirmation_status,
                    email_recipient, passengers, slices, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(duffel_order_id) DO UPDATE SET
                    status = excluded.status,
                    payment_status = excluded.payment_status,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, bundle_id, promo_code, str(gross_val), str(disc_val),
                    booking_reference, order_type, status, str(total_amount), total_currency,
                    payment_status, payment_method, payment_required_by, email_confirmation_status,
                    email_recipient, passengers_json, slices_json, now_iso, now_iso
                ))
                conn.commit()
            print(f"[ORDER DAO] Saved hold order '{duffel_order_id}' to database (Engine: {self.db_engine}).")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return {
            "id": order_id,
            "duffel_order_id": duffel_order_id,
            "booking_reference": booking_reference,
            "status": status,
            "payment_status": payment_status,
            "email_confirmation_status": email_confirmation_status,
            "created_at": now_iso,
            "promo_code": promo_code,
            "gross_amount": f"{gross_val:.2f}",
            "discount_amount": f"{disc_val:.2f}",
        }

    def update_order_status(
        self,
        duffel_order_id: str,
        status: Optional[str] = None,
        payment_status: Optional[str] = None,
        email_confirmation_status: Optional[str] = None,
        payment_details: Optional[dict[str, Any]] = None,
        email_recipient: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Update the status, payment_status, email_confirmation_status, and payment details of an existing order.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            payment_details_json = json.dumps(payment_details) if payment_details else None

            if self.db_engine == "postgresql":
                updates = ["updated_at = %s"]
                params = [now_iso]
                if status:
                    updates.append("status = %s")
                    params.append(status)
                if payment_status:
                    updates.append("payment_status = %s")
                    params.append(payment_status)
                if email_confirmation_status:
                    updates.append("email_confirmation_status = %s")
                    params.append(email_confirmation_status)
                if payment_details_json:
                    updates.append("payment_details = %s")
                    params.append(payment_details_json)
                if email_recipient:
                    updates.append("email_recipient = %s")
                    params.append(email_recipient)

                params.append(duffel_order_id)
                sql = f"UPDATE flight_orders SET {', '.join(updates)} WHERE duffel_order_id = %s"
                cursor.execute(sql, tuple(params))
            else:
                updates = ["updated_at = ?"]
                params = [now_iso]
                if status:
                    updates.append("status = ?")
                    params.append(status)
                if payment_status:
                    updates.append("payment_status = ?")
                    params.append(payment_status)
                if email_confirmation_status:
                    updates.append("email_confirmation_status = ?")
                    params.append(email_confirmation_status)
                if payment_details_json:
                    updates.append("payment_details = ?")
                    params.append(payment_details_json)
                if email_recipient:
                    updates.append("email_recipient = ?")
                    params.append(email_recipient)

                params.append(duffel_order_id)
                sql = f"UPDATE flight_orders SET {', '.join(updates)} WHERE duffel_order_id = ?"
                cursor.execute(sql, tuple(params))
                conn.commit()

            print(f"[ORDER DAO] Updated status for order '{duffel_order_id}': status='{status}', payment_status='{payment_status}', email_status='{email_confirmation_status}'.")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return self.get_order_by_duffel_id(duffel_order_id)

    def get_order_by_duffel_id(self, duffel_order_id: str) -> Optional[dict[str, Any]]:
        """Fetch an order record by Duffel order ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT id, duffel_order_id, booking_reference, order_type, status, total_amount, total_currency, payment_status, payment_method, payment_details, payment_required_by, email_confirmation_status, email_recipient, passengers, slices, created_at, updated_at FROM flight_orders WHERE duffel_order_id = %s"
                cursor.execute(sql, (duffel_order_id,))
            else:
                sql = "SELECT id, duffel_order_id, booking_reference, order_type, status, total_amount, total_currency, payment_status, payment_method, payment_details, payment_required_by, email_confirmation_status, email_recipient, passengers, slices, created_at, updated_at FROM flight_orders WHERE duffel_order_id = ?"
                cursor.execute(sql, (duffel_order_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "duffel_order_id": row[1],
                "booking_reference": row[2],
                "order_type": row[3],
                "status": row[4],
                "total_amount": str(row[5]),
                "total_currency": row[6],
                "payment_status": row[7],
                "payment_method": row[8],
                "payment_details": json.loads(row[9]) if row[9] and isinstance(row[9], str) else (row[9] if isinstance(row[9], dict) else {}),
                "payment_required_by": row[10],
                "email_confirmation_status": row[11],
                "email_recipient": row[12],
                "passengers": json.loads(row[13]) if row[13] and isinstance(row[13], str) else (row[13] if isinstance(row[13], list) else []),
                "slices": json.loads(row[14]) if row[14] and isinstance(row[14], str) else (row[14] if isinstance(row[14], list) else []),
                "created_at": row[15],
                "updated_at": row[16],
            }
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    # --- Stay Order Persistence ---

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
    ) -> dict[str, Any]:
        """Persist a hotel stay order to the database."""
        now_iso = datetime.now(timezone.utc).isoformat()
        order_id = f"ord_stay_db_{duffel_order_id}"
        guests_json = json.dumps(guests or [])
        gross_val = float(gross_amount or total_amount or 0.0)
        disc_val = float(discount_amount or 0.0)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO stay_orders (
                    id, duffel_order_id, bundle_id, promo_code, gross_amount, discount_amount,
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, total_amount, total_currency,
                    payment_status, payment_method, guests, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_order_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, bundle_id, promo_code, gross_val, disc_val,
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, float(total_amount or 0.0), total_currency,
                    payment_status, payment_method, guests_json, now_iso, now_iso
                ))
            else:
                sql = """
                INSERT INTO stay_orders (
                    id, duffel_order_id, bundle_id, promo_code, gross_amount, discount_amount,
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, total_amount, total_currency,
                    payment_status, payment_method, guests, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(duffel_order_id) DO UPDATE SET
                    status = excluded.status,
                    payment_status = excluded.payment_status,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, bundle_id, promo_code, str(gross_val), str(disc_val),
                    quote_id, booking_reference, accommodation_id, accommodation_name,
                    check_in_date, check_out_date, rooms, status, str(total_amount), total_currency,
                    payment_status, payment_method, guests_json, now_iso, now_iso
                ))
                conn.commit()
            print(f"[ORDER DAO] Saved stay order '{duffel_order_id}' to database.")
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
            "promo_code": promo_code,
            "gross_amount": f"{gross_val:.2f}",
            "discount_amount": f"{disc_val:.2f}",
        }

    def get_stay_order_by_duffel_id(self, duffel_order_id: str) -> Optional[dict[str, Any]]:
        """Fetch a stay order record by Duffel order ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT id, duffel_order_id, quote_id, booking_reference, accommodation_id, accommodation_name, check_in_date, check_out_date, rooms, status, total_amount, total_currency, payment_status, payment_method, guests, created_at, updated_at FROM stay_orders WHERE duffel_order_id = %s"
                cursor.execute(sql, (duffel_order_id,))
            else:
                sql = "SELECT id, duffel_order_id, quote_id, booking_reference, accommodation_id, accommodation_name, check_in_date, check_out_date, rooms, status, total_amount, total_currency, payment_status, payment_method, guests, created_at, updated_at FROM stay_orders WHERE duffel_order_id = ?"
                cursor.execute(sql, (duffel_order_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "duffel_order_id": row[1],
                "quote_id": row[2],
                "booking_reference": row[3],
                "accommodation_id": row[4],
                "accommodation_name": row[5],
                "check_in_date": row[6],
                "check_out_date": row[7],
                "rooms": row[8],
                "status": row[9],
                "total_amount": str(row[10]),
                "total_currency": row[11],
                "payment_status": row[12],
                "payment_method": row[13],
                "guests": json.loads(row[14]) if row[14] and isinstance(row[14], str) else (row[14] if isinstance(row[14], list) else []),
                "created_at": row[15],
                "updated_at": row[16],
            }
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    # --- Car Order Persistence ---

    def save_car_order(
        self,
        duffel_order_id: str,
        booking_reference: str,
        total_amount: str,
        total_currency: str = "USD",
        offer_id: Optional[str] = None,
        supplier_name: Optional[str] = None,
        vehicle_name: Optional[str] = None,
        pickup_location: Optional[str] = None,
        dropoff_location: Optional[str] = None,
        pickup_datetime: Optional[str] = None,
        dropoff_datetime: Optional[str] = None,
        driver_age: int = 30,
        status: str = "confirmed",
        payment_status: str = "paid",
        payment_method: str = "balance",
        driver_details: Optional[dict[str, Any]] = None,
        bundle_id: Optional[str] = None,
        promo_code: Optional[str] = None,
        gross_amount: Optional[str] = None,
        discount_amount: Optional[str] = None,
    ) -> dict[str, Any]:
        """Persist a car rental order to the database."""
        now_iso = datetime.now(timezone.utc).isoformat()
        order_id = f"ord_car_db_{duffel_order_id}"
        driver_json = json.dumps(driver_details or {})
        gross_val = float(gross_amount or total_amount or 0.0)
        disc_val = float(discount_amount or 0.0)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO car_orders (
                    id, duffel_order_id, bundle_id, promo_code, gross_amount, discount_amount,
                    offer_id, booking_reference, supplier_name, vehicle_name, pickup_location,
                    dropoff_location, pickup_datetime, dropoff_datetime, driver_age,
                    driver_details, status, total_amount, total_currency, payment_status,
                    payment_method, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_order_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, bundle_id, promo_code, gross_val, disc_val,
                    offer_id, booking_reference, supplier_name, vehicle_name, pickup_location,
                    dropoff_location, pickup_datetime, dropoff_datetime, driver_age,
                    driver_json, status, float(total_amount or 0.0), total_currency, payment_status,
                    payment_method, now_iso, now_iso
                ))
            else:
                sql = """
                INSERT INTO car_orders (
                    id, duffel_order_id, bundle_id, promo_code, gross_amount, discount_amount,
                    offer_id, booking_reference, supplier_name, vehicle_name, pickup_location,
                    dropoff_location, pickup_datetime, dropoff_datetime, driver_age,
                    driver_details, status, total_amount, total_currency, payment_status,
                    payment_method, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(duffel_order_id) DO UPDATE SET
                    status = excluded.status,
                    payment_status = excluded.payment_status,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, bundle_id, promo_code, str(gross_val), str(disc_val),
                    offer_id, booking_reference, supplier_name, vehicle_name, pickup_location,
                    dropoff_location, pickup_datetime, dropoff_datetime, driver_age,
                    driver_json, status, str(total_amount), total_currency, payment_status,
                    payment_method, now_iso, now_iso
                ))
                conn.commit()
            print(f"[ORDER DAO] Saved car order '{duffel_order_id}' to database.")
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
            "promo_code": promo_code,
            "gross_amount": f"{gross_val:.2f}",
            "discount_amount": f"{disc_val:.2f}",
        }

    def get_car_order_by_duffel_id(self, duffel_order_id: str) -> Optional[dict[str, Any]]:
        """Fetch a car rental order record by Duffel order ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT id, duffel_order_id, offer_id, booking_reference, supplier_name, vehicle_name, pickup_location, dropoff_location, pickup_datetime, dropoff_datetime, driver_age, driver_details, status, total_amount, total_currency, payment_status, payment_method, created_at, updated_at FROM car_orders WHERE duffel_order_id = %s"
                cursor.execute(sql, (duffel_order_id,))
            else:
                sql = "SELECT id, duffel_order_id, offer_id, booking_reference, supplier_name, vehicle_name, pickup_location, dropoff_location, pickup_datetime, dropoff_datetime, driver_age, driver_details, status, total_amount, total_currency, payment_status, payment_method, created_at, updated_at FROM car_orders WHERE duffel_order_id = ?"
                cursor.execute(sql, (duffel_order_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "duffel_order_id": row[1],
                "offer_id": row[2],
                "booking_reference": row[3],
                "supplier_name": row[4],
                "vehicle_name": row[5],
                "pickup_location": row[6],
                "dropoff_location": row[7],
                "pickup_datetime": row[8],
                "dropoff_datetime": row[9],
                "driver_age": row[10],
                "driver_details": json.loads(row[11]) if row[11] and isinstance(row[11], str) else (row[11] if isinstance(row[11], dict) else {}),
                "status": row[12],
                "total_amount": str(row[13]),
                "total_currency": row[14],
                "payment_status": row[15],
                "payment_method": row[16],
                "created_at": row[17],
                "updated_at": row[18],
            }
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return self.create_car_order({})

    # --- Bundle Order Persistence ---

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
    ) -> dict[str, Any]:
        """Persist a combined travel package bundle order."""
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
                INSERT INTO bundle_orders (
                    id, duffel_bundle_id, promo_code, gross_amount, discount_amount,
                    flight_order_id, stay_order_id, car_order_id, status, combined_total_amount,
                    total_currency, payment_status, payment_method, flight_details,
                    stay_details, car_details, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_bundle_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_bundle_id, promo_code, gross_val, disc_val,
                    flight_order_id, stay_order_id, car_order_id, status, float(combined_total_amount or 0.0),
                    total_currency, payment_status, payment_method, fl_json, st_json, cr_json, now_iso, now_iso
                ))
            else:
                sql = """
                INSERT INTO bundle_orders (
                    id, duffel_bundle_id, promo_code, gross_amount, discount_amount,
                    flight_order_id, stay_order_id, car_order_id, status, combined_total_amount,
                    total_currency, payment_status, payment_method, flight_details,
                    stay_details, car_details, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(duffel_bundle_id) DO UPDATE SET
                    status = excluded.status,
                    payment_status = excluded.payment_status,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_bundle_id, promo_code, str(gross_val), str(disc_val),
                    flight_order_id, stay_order_id, car_order_id, status, str(combined_total_amount),
                    total_currency, payment_status, payment_method, fl_json, st_json, cr_json, now_iso, now_iso
                ))
                conn.commit()
            print(f"[ORDER DAO] Saved bundle order '{duffel_bundle_id}' to database.")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return {
            "id": order_id,
            "duffel_bundle_id": duffel_bundle_id,
            "status": status,
            "combined_total_amount": str(combined_total_amount),
            "created_at": now_iso,
            "promo_code": promo_code,
            "gross_amount": f"{gross_val:.2f}",
            "discount_amount": f"{disc_val:.2f}",
        }

    def get_bundle_order_by_id(self, duffel_bundle_id: str) -> Optional[dict[str, Any]]:
        """Fetch a bundle order record by bundle order ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT id, duffel_bundle_id, flight_order_id, stay_order_id, car_order_id, status, combined_total_amount, total_currency, payment_status, payment_method, flight_details, stay_details, car_details, created_at, updated_at FROM bundle_orders WHERE duffel_bundle_id = %s"
                cursor.execute(sql, (duffel_bundle_id,))
            else:
                sql = "SELECT id, duffel_bundle_id, flight_order_id, stay_order_id, car_order_id, status, combined_total_amount, total_currency, payment_status, payment_method, flight_details, stay_details, car_details, created_at, updated_at FROM bundle_orders WHERE duffel_bundle_id = ?"
                cursor.execute(sql, (duffel_bundle_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "duffel_bundle_id": row[1],
                "flight_order_id": row[2],
                "stay_order_id": row[3],
                "car_order_id": row[4],
                "status": row[5],
                "combined_total_amount": str(row[6]),
                "total_currency": row[7],
                "payment_status": row[8],
                "payment_method": row[9],
                "flight_details": json.loads(row[10]) if row[10] and isinstance(row[10], str) else (row[10] if isinstance(row[10], dict) else {}),
                "stay_details": json.loads(row[11]) if row[11] and isinstance(row[11], str) else (row[11] if isinstance(row[11], dict) else {}),
                "car_details": json.loads(row[12]) if row[12] and isinstance(row[12], str) else (row[12] if isinstance(row[12], dict) else {}),
                "created_at": row[13],
                "updated_at": row[14],
            }
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    # --- Unified All Orders Retrieval ---

    def get_all_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent bookings across Flights, Stays, Cars, and Bundles."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            sql = """
            SELECT id, duffel_order_id, 'flight' AS booking_type, booking_reference, status, total_amount, total_currency, payment_status, created_at FROM flight_orders
            UNION ALL
            SELECT id, duffel_order_id, 'stay' AS booking_type, booking_reference, status, total_amount, total_currency, payment_status, created_at FROM stay_orders
            UNION ALL
            SELECT id, duffel_order_id, 'car' AS booking_type, booking_reference, status, total_amount, total_currency, payment_status, created_at FROM car_orders
            UNION ALL
            SELECT id, duffel_bundle_id AS duffel_order_id, 'bundle' AS booking_type, duffel_bundle_id AS booking_reference, status, combined_total_amount AS total_amount, total_currency, payment_status, created_at FROM bundle_orders
            ORDER BY created_at DESC LIMIT %s;
            """ if self.db_engine == "postgresql" else """
            SELECT id, duffel_order_id, 'flight' AS booking_type, booking_reference, status, total_amount, total_currency, payment_status, created_at FROM flight_orders
            UNION ALL
            SELECT id, duffel_order_id, 'stay' AS booking_type, booking_reference, status, total_amount, total_currency, payment_status, created_at FROM stay_orders
            UNION ALL
            SELECT id, duffel_order_id, 'car' AS booking_type, booking_reference, status, total_amount, total_currency, payment_status, created_at FROM car_orders
            UNION ALL
            SELECT id, duffel_bundle_id AS duffel_order_id, 'bundle' AS booking_type, duffel_bundle_id AS booking_reference, status, combined_total_amount AS total_amount, total_currency, payment_status, created_at FROM bundle_orders
            ORDER BY created_at DESC LIMIT ?;
            """
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "duffel_order_id": r[1],
                    "booking_type": r[2],
                    "booking_reference": r[3],
                    "status": r[4],
                    "total_amount": str(r[5]),
                    "total_currency": r[6],
                    "payment_status": r[7],
                    "created_at": r[8],
                }
                for r in rows
            ]
        finally:
            if self.db_engine != "postgresql":
                conn.close()

    # --- Itinerary Templates Store (Date-Neutral, Price-Agnostic) ---

    def save_itinerary_template(
        self,
        destination: str,
        duration_days: int,
        title: str,
        map_center: dict[str, Any],
        template_days: list[dict[str, Any]],
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Persists a date-neutral, price-agnostic itinerary template for a destination and duration.
        """
        dest_clean = destination.strip()
        tpl_id = f"tpl_{dest_clean.lower().replace(' ', '_')}_{duration_days}day"
        now_iso = datetime.now(timezone.utc).isoformat()

        map_center_json = json.dumps(map_center)
        template_days_json = json.dumps(template_days)
        tags_json = json.dumps(tags or ["sightseeing", "culture"])

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO itinerary_templates (
                    id, destination, duration_days, title, map_center, template_days, tags, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    map_center = EXCLUDED.map_center,
                    template_days = EXCLUDED.template_days,
                    tags = EXCLUDED.tags,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (tpl_id, dest_clean, duration_days, title, map_center_json, template_days_json, tags_json, now_iso, now_iso))
            else:
                sql = """
                INSERT INTO itinerary_templates (
                    id, destination, duration_days, title, map_center, template_days, tags, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    map_center = excluded.map_center,
                    template_days = excluded.template_days,
                    tags = excluded.tags,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (tpl_id, dest_clean, duration_days, title, map_center_json, template_days_json, tags_json, now_iso, now_iso))
                conn.commit()
            print(f"[ORDER DAO] Saved itinerary template '{tpl_id}' for {dest_clean} ({duration_days} days).")
        finally:
            if self.db_engine != "postgresql":
                conn.close()

        return {
            "id": tpl_id,
            "destination": dest_clean,
            "duration_days": duration_days,
            "title": title,
            "map_center": map_center,
            "template_days": template_days,
            "tags": tags or [],
        }

    def get_itinerary_template(self, destination: str, duration_days: int) -> Optional[dict[str, Any]]:
        """
        Retrieves a date-neutral itinerary template matching destination and duration.
        """
        dest_clean = destination.strip()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT id, destination, duration_days, title, map_center, template_days, tags, created_at FROM itinerary_templates WHERE LOWER(destination) = LOWER(%s) AND duration_days = %s LIMIT 1;"
                cursor.execute(sql, (dest_clean, duration_days))
            else:
                sql = "SELECT id, destination, duration_days, title, map_center, template_days, tags, created_at FROM itinerary_templates WHERE LOWER(destination) = LOWER(?) AND duration_days = ? LIMIT 1;"
                cursor.execute(sql, (dest_clean, duration_days))

            row = cursor.fetchone()
            if not row:
                return None

            map_c = json.loads(row[4]) if row[4] and isinstance(row[4], str) else (row[4] if isinstance(row[4], dict) else {})
            tpl_d = json.loads(row[5]) if row[5] and isinstance(row[5], str) else (row[5] if isinstance(row[5], list) else [])
            tg = json.loads(row[6]) if row[6] and isinstance(row[6], str) else (row[6] if isinstance(row[6], list) else [])

            return {
                "id": row[0],
                "destination": row[1],
                "duration_days": row[2],
                "title": row[3],
                "map_center": map_c,
                "template_days": tpl_d,
                "tags": tg,
                "created_at": row[7],
            }
        finally:
            if self.db_engine != "postgresql":
                conn.close()


