"""
Dedicated Itinerary DAO module for PostgreSQL / SQLite itinerary persistence and refinement versioning.
Follows single-responsibility pattern (one DAO per domain table).
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import sqlite3
from typing import Any, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class ItineraryDAO:
    """
    Dedicated Data Access Object for generated itineraries and templates in PostgreSQL / SQLite.
    Handles storage, retrieval, and versioning when users refine itineraries.
    """

    def __init__(self, config: Optional[Any] = None):
        self.config = config
        self.db_engine = "sqlite"
        self.postgres_url = ""

        if config:
            if getattr(config, "postgres_enabled", False):
                self.db_engine = "postgresql"
                self.postgres_url = getattr(config, "postgres_url", "") or os.getenv("POSTGRES_URL", "")
                if not self.postgres_url:
                    user = getattr(config, "postgres_user", "postgres")
                    pwd = getattr(config, "postgres_password", "postgres")
                    host = getattr(config, "postgres_host", "127.0.0.1")
                    port = getattr(config, "postgres_port", 5432)
                    db = getattr(config, "postgres_db", "jojira_duffel")
                    self.postgres_url = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

        self.sqlite_db_path = os.getenv("SQLITE_DB_PATH", "jojira_duffel.db")
        self.init_db()

    def _get_connection(self):
        """Creates a fresh connection based on configured db_engine."""
        if self.db_engine == "postgresql" and PSYCOPG2_AVAILABLE:
            try:
                return psycopg2.connect(self.postgres_url, connect_timeout=2)
            except Exception as err:
                err_msg = f"[POSTGRES ERROR] Failed to connect to PostgreSQL database ({self.postgres_url}): {err}. Exiting application."
                print(f"\n{'=' * 80}\n{err_msg}\n{'=' * 80}\n")
                import sys
                sys.exit(1)
        else:
            self.db_engine = "sqlite"

        conn = sqlite3.connect(self.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn


    def init_db(self):
        """Initializes itinerary tables and indexes."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                ddl = """
                CREATE SCHEMA IF NOT EXISTS planner;

                CREATE TABLE IF NOT EXISTS generated_itineraries (
                    id VARCHAR(100) PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    parent_itinerary_id VARCHAR(100),
                    destination VARCHAR(100) NOT NULL,
                    start_date VARCHAR(20),
                    end_date VARCHAR(20),
                    duration_days INTEGER,
                    passengers_count INTEGER DEFAULT 1,
                    version INTEGER DEFAULT 1,
                    liked INTEGER DEFAULT 0,
                    likes_count INTEGER DEFAULT 0,
                    feedback_notes TEXT,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_gen_itin_dest ON generated_itineraries(destination);
                CREATE INDEX IF NOT EXISTS idx_gen_itin_parent ON generated_itineraries(parent_itinerary_id);

                CREATE TABLE IF NOT EXISTS planner.generated_itineraries (
                    id VARCHAR(100) PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    parent_itinerary_id VARCHAR(100),
                    destination VARCHAR(100) NOT NULL,
                    start_date VARCHAR(20),
                    end_date VARCHAR(20),
                    duration_days INTEGER,
                    passengers_count INTEGER DEFAULT 1,
                    version INTEGER DEFAULT 1,
                    liked INTEGER DEFAULT 0,
                    likes_count INTEGER DEFAULT 0,
                    feedback_notes TEXT,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );

                CREATE TABLE IF NOT EXISTS itinerary_templates (
                    id VARCHAR(100) PRIMARY KEY,
                    destination VARCHAR(100) NOT NULL,
                    duration_days INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    map_center TEXT,
                    template_days TEXT NOT NULL,
                    tags TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_by VARCHAR(100) DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_itin_tpl_dest_dur ON itinerary_templates(destination, duration_days);

                CREATE TABLE IF NOT EXISTS llm_call_logs (
                    id VARCHAR(100) PRIMARY KEY,
                    provider VARCHAR(50) NOT NULL,
                    model VARCHAR(100) NOT NULL,
                    prompt TEXT,
                    destination VARCHAR(100),
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_llm_log_provider ON llm_call_logs(provider);
                """
                cursor.execute(ddl)
                conn.commit()
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS generated_itineraries (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    parent_itinerary_id TEXT,
                    destination TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    duration_days INTEGER,
                    passengers_count INTEGER DEFAULT 1,
                    version INTEGER DEFAULT 1,
                    liked INTEGER DEFAULT 0,
                    likes_count INTEGER DEFAULT 0,
                    feedback_notes TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_gen_itin_dest ON generated_itineraries(destination);
                CREATE INDEX IF NOT EXISTS idx_gen_itin_parent ON generated_itineraries(parent_itinerary_id);

                CREATE TABLE IF NOT EXISTS itinerary_templates (
                    id TEXT PRIMARY KEY,
                    destination TEXT NOT NULL,
                    duration_days INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    map_center TEXT,
                    template_days TEXT NOT NULL,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                );
                CREATE INDEX IF NOT EXISTS idx_itin_tpl_dest_dur ON itinerary_templates(destination, duration_days);

                CREATE TABLE IF NOT EXISTS llm_call_logs (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt TEXT,
                    destination TEXT,
                    success INTEGER DEFAULT 1,
                    error_message TEXT,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_llm_log_provider ON llm_call_logs(provider);
                """
                cursor.executescript(ddl)
                conn.commit()


            # Ensure audit columns exist on existing tables
            cols_to_add = [
                ("user_id", "VARCHAR(100)", "TEXT"),
                ("liked", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
                ("likes_count", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
                ("feedback_notes", "TEXT", "TEXT"),
                ("created_by", "VARCHAR(100) DEFAULT 'system'", "TEXT DEFAULT 'system'"),
                ("updated_by", "VARCHAR(100) DEFAULT 'system'", "TEXT DEFAULT 'system'"),
            ]
            for tbl in ["generated_itineraries", "itinerary_templates"]:
                for col_name, pg_type, sq_type in cols_to_add:
                    try:
                        if self.db_engine == "postgresql":
                            alt_sql = f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col_name} {pg_type};"
                            cursor.execute(alt_sql)
                            conn.commit()
                        else:
                            alt_sql = f"ALTER TABLE {tbl} ADD COLUMN {col_name} {sq_type};"
                            cursor.execute(alt_sql)
                            conn.commit()
                    except Exception:
                        pass

        except Exception as err:
            print(f"[ITINERARY DAO NOTICE] Table initialization notice: {err}")
        finally:
            conn.close()


    def save_itinerary(
        self,
        prompt: str,
        destination: str,
        start_date: str,
        end_date: str,
        duration_days: int,
        passengers_count: int,
        payload: dict[str, Any],
        parent_itinerary_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Saves a generated or refined travel itinerary into database.
        Supports versioning when a user refines an existing itinerary.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        version = 1

        if parent_itinerary_id:
            parent = self.get_itinerary_by_id(parent_itinerary_id)
            if parent:
                version = parent.get("version", 1) + 1

        hash_input = f"{prompt}_{destination}_{start_date}_{end_date}_{version}_{now_iso}"
        itin_id = f"itin_{hashlib.md5(hash_input.encode()).hexdigest()[:10]}"

        # Tag itinerary_id, user_id & version into payload metadata
        if "meta_data" in payload and isinstance(payload["meta_data"], dict):
            payload["meta_data"]["itinerary_id"] = itin_id
            payload["meta_data"]["user_id"] = user_id
            payload["meta_data"]["version"] = version
            if parent_itinerary_id:
                payload["meta_data"]["parent_itinerary_id"] = parent_itinerary_id

        payload_json = json.dumps(payload)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO generated_itineraries (
                    id, user_id, prompt, parent_itinerary_id, destination, start_date, end_date, duration_days, passengers_count, version, payload, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at;
                """
                cursor.execute(sql, (itin_id, user_id, prompt, parent_itinerary_id, destination, start_date, end_date, duration_days, passengers_count, version, payload_json, now_iso, now_iso))
            else:
                sql = """
                INSERT INTO generated_itineraries (
                    id, user_id, prompt, parent_itinerary_id, destination, start_date, end_date, duration_days, passengers_count, version, payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at;
                """
                cursor.execute(sql, (itin_id, user_id, prompt, parent_itinerary_id, destination, start_date, end_date, duration_days, passengers_count, version, payload_json, now_iso, now_iso))
                conn.commit()


            print(f"[ITINERARY DAO] Persisted itinerary '{itin_id}' (v{version}) for {destination}.")
            return itin_id
        except Exception as db_err:
            print(f"[ITINERARY DAO WARN] Save failed: {db_err}")
            return itin_id
        finally:
            conn.close()

    def get_itinerary_by_id(self, itinerary_id: str) -> Optional[dict[str, Any]]:
        """Retrieves a persisted itinerary payload by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "SELECT payload, version, parent_itinerary_id FROM generated_itineraries WHERE id = %s LIMIT 1;"
                cursor.execute(sql, (itinerary_id,))
            else:
                sql = "SELECT payload, version, parent_itinerary_id FROM generated_itineraries WHERE id = ? LIMIT 1;"
                cursor.execute(sql, (itinerary_id,))

            row = cursor.fetchone()
            if not row:
                return None

            payload = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            if isinstance(payload, dict):
                payload["version"] = row[1]
                payload["parent_itinerary_id"] = row[2]
            return payload
        except Exception:
            return None
        finally:
            conn.close()

    def get_itinerary_by_params(
        self,
        destination: str,
        start_date: str,
        end_date: str,
        duration_days: int,
        passengers_count: int,
    ) -> Optional[dict[str, Any]]:
        """
        Queries PostgreSQL / SQLite for an existing matching itinerary.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = """
                SELECT payload FROM generated_itineraries 
                WHERE LOWER(destination) = LOWER(%s) AND start_date = %s AND end_date = %s AND duration_days = %s AND passengers_count = %s
                ORDER BY created_at DESC LIMIT 1;
                """
                cursor.execute(sql, (destination.strip(), start_date, end_date, duration_days, passengers_count))
            else:
                sql = """
                SELECT payload FROM generated_itineraries 
                WHERE LOWER(destination) = LOWER(?) AND start_date = ? AND end_date = ? AND duration_days = ? AND passengers_count = ?
                ORDER BY created_at DESC LIMIT 1;
                """
                cursor.execute(sql, (destination.strip(), start_date, end_date, duration_days, passengers_count))

            row = cursor.fetchone()
            if not row:
                return None
            return json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception:
            return None
        finally:
            conn.close()

    def update_itinerary_like(self, itinerary_id: str, liked: bool, feedback_notes: Optional[str] = None) -> bool:
        """
        Updates like status or deletes if downvoted.
        If liked=True: sets liked=1 and increments likes_count.
        If liked=False (downvote): deletes row so DB lookup misses and triggers LLM re-creation.
        """
        if not liked:
            return self.delete_itinerary(itinerary_id)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            if self.db_engine == "postgresql":
                sql = """
                UPDATE generated_itineraries 
                SET liked = 1, likes_count = likes_count + 1, feedback_notes = COALESCE(%s, feedback_notes), updated_at = %s
                WHERE id = %s;
                """
                cursor.execute(sql, (feedback_notes, now_iso, itinerary_id))
            else:
                sql = """
                UPDATE generated_itineraries 
                SET liked = 1, likes_count = likes_count + 1, feedback_notes = COALESCE(?, feedback_notes), updated_at = ?
                WHERE id = ?;
                """
                cursor.execute(sql, (feedback_notes, now_iso, itinerary_id))
                conn.commit()
            print(f"[ITINERARY DAO] Upvoted itinerary '{itinerary_id}'.")
            return True
        except Exception as err:
            print(f"[ITINERARY DAO WARN] Update like failed: {err}")
            return False
        finally:
            conn.close()

    def delete_itinerary(self, itinerary_id: str) -> bool:
        """Deletes a downvoted or invalidated itinerary from PostgreSQL / SQLite."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                sql = "DELETE FROM generated_itineraries WHERE id = %s;"
                cursor.execute(sql, (itinerary_id,))
            else:
                sql = "DELETE FROM generated_itineraries WHERE id = ?;"
                cursor.execute(sql, (itinerary_id,))
                conn.commit()
            print(f"[ITINERARY DAO] Deleted itinerary '{itinerary_id}' due to downvote.")
            return True
        except Exception as err:
            print(f"[ITINERARY DAO WARN] Delete failed: {err}")
            return False
        finally:
            conn.close()

    def log_llm_call(
        self,
        provider: str,
        model: str,
        prompt: Optional[str] = None,
        destination: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> bool:
        """Logs an LLM API call invocation to PostgreSQL / SQLite database."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            log_id = f"llm_log_{hashlib.md5(f'{provider}_{model}_{now_iso}'.encode()).hexdigest()[:10]}"
            succ_val = True if self.db_engine == "postgresql" else (1 if success else 0)

            if self.db_engine == "postgresql":
                sql = """
                INSERT INTO llm_call_logs (id, provider, model, prompt, destination, success, error_message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """
                cursor.execute(sql, (log_id, provider, model, prompt, destination, succ_val, error_message, now_iso))
            else:
                sql = """
                INSERT INTO llm_call_logs (id, provider, model, prompt, destination, success, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(sql, (log_id, provider, model, prompt, destination, succ_val, error_message, now_iso))
                conn.commit()
            return True
        except Exception as err:
            print(f"[ITINERARY DAO NOTICE] Log LLM call notice: {err}")
            return False
        finally:
            conn.close()

    def get_llm_call_stats(self) -> dict[str, Any]:
        """Queries total LLM call counts grouped by provider and model."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            sql = "SELECT provider, COUNT(*) FROM llm_call_logs GROUP BY provider;"
            cursor.execute(sql)
            rows = cursor.fetchall()
            stats = {row[0]: row[1] for row in rows}
            return stats
        except Exception:
            return {}
        finally:
            conn.close()



