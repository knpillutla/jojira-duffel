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
                """
                cursor.execute(ddl)
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS flight_orders (
                    id TEXT PRIMARY KEY,
                    duffel_order_id TEXT UNIQUE NOT NULL,
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
                """
                cursor.executescript(ddl)
                conn.commit()
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
    ) -> dict[str, Any]:
        """
        Persist a flight order when created in 'hold' (or 'instant') status.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        order_id = f"ord_db_{duffel_order_id}"
        passengers_json = json.dumps(passengers or [])
        slices_json = json.dumps(slices or [])

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO flight_orders (
                    id, duffel_order_id, booking_reference, order_type, status,
                    total_amount, total_currency, payment_status, payment_method,
                    payment_required_by, email_confirmation_status, email_recipient,
                    passengers, slices, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (duffel_order_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, booking_reference, order_type, status,
                    float(total_amount or 0.0), total_currency, payment_status, payment_method,
                    payment_required_by, email_confirmation_status, email_recipient,
                    passengers_json, slices_json, now_iso, now_iso
                ))
            else:
                sql = """
                INSERT INTO flight_orders (
                    id, duffel_order_id, booking_reference, order_type, status,
                    total_amount, total_currency, payment_status, payment_method,
                    payment_required_by, email_confirmation_status, email_recipient,
                    passengers, slices, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(duffel_order_id) DO UPDATE SET
                    status = excluded.status,
                    payment_status = excluded.payment_status,
                    updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (
                    order_id, duffel_order_id, booking_reference, order_type, status,
                    str(total_amount), total_currency, payment_status, payment_method,
                    payment_required_by, email_confirmation_status, email_recipient,
                    passengers_json, slices_json, now_iso, now_iso
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
