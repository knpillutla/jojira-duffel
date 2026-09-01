"""
Dedicated Itinerary Module DAO for PostgreSQL / SQLite modular itinerary storage.
Follows single-responsibility pattern and standard database audit schema.
Includes trip_type ('flight' vs 'road_trip'), style/theme ('romantic', 'cultural', etc.),
and UUID primary keys.
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Optional
import uuid

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class ItineraryModuleDAO:
    """
    Data Access Object for relative-time itinerary modules (arrival, core_day, departure)
    stored in PostgreSQL / SQLite for stateless assembly without LLM inference.
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
        """Creates a fresh database connection based on configured db_engine."""
        if self.db_engine == "postgresql" and PSYCOPG2_AVAILABLE:
            try:
                return psycopg2.connect(self.postgres_url, connect_timeout=2)
            except Exception as err:
                err_msg = f"[POSTGRES ERROR] Failed to connect to PostgreSQL ({self.postgres_url}): {err}. Falling back to SQLite."
                print(f"[ITINERARY MODULE DAO] {err_msg}")
                self.db_engine = "sqlite"

        conn = sqlite3.connect(self.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes the itinerary_modules table with mandatory audit & test mode columns."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                ddl = """
                CREATE SCHEMA IF NOT EXISTS planner;

                CREATE TABLE IF NOT EXISTS itinerary_modules (
                    id VARCHAR(36) PRIMARY KEY,
                    destination VARCHAR(50) NOT NULL,
                    trip_type VARCHAR(20) NOT NULL DEFAULT 'flight',
                    style VARCHAR(30) NOT NULL DEFAULT 'balanced',
                    duration_days INT NOT NULL,
                    module_type VARCHAR(20) NOT NULL,
                    time_slot VARCHAR(20),
                    day_index INT NOT NULL,
                    content JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_by VARCHAR(100) DEFAULT 'system',
                    is_test BOOLEAN DEFAULT FALSE
                );

                ALTER TABLE itinerary_modules ADD COLUMN IF NOT EXISTS trip_type VARCHAR(20) NOT NULL DEFAULT 'flight';
                ALTER TABLE itinerary_modules ADD COLUMN IF NOT EXISTS style VARCHAR(30) NOT NULL DEFAULT 'balanced';

                CREATE INDEX IF NOT EXISTS idx_itin_mod_lookup 
                ON itinerary_modules(destination, trip_type, style, duration_days, module_type, time_slot, day_index);

                CREATE INDEX IF NOT EXISTS idx_itin_mod_dest ON itinerary_modules(destination);

                CREATE TABLE IF NOT EXISTS planner.itinerary_modules (
                    id VARCHAR(36) PRIMARY KEY,
                    destination VARCHAR(50) NOT NULL,
                    trip_type VARCHAR(20) NOT NULL DEFAULT 'flight',
                    style VARCHAR(30) NOT NULL DEFAULT 'balanced',
                    duration_days INT NOT NULL,
                    module_type VARCHAR(20) NOT NULL,
                    time_slot VARCHAR(20),
                    day_index INT NOT NULL,
                    content JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(100) DEFAULT 'system',
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_by VARCHAR(100) DEFAULT 'system',
                    is_test BOOLEAN DEFAULT FALSE
                );

                ALTER TABLE planner.itinerary_modules ADD COLUMN IF NOT EXISTS trip_type VARCHAR(20) NOT NULL DEFAULT 'flight';
                ALTER TABLE planner.itinerary_modules ADD COLUMN IF NOT EXISTS style VARCHAR(30) NOT NULL DEFAULT 'balanced';

                CREATE INDEX IF NOT EXISTS idx_planner_itin_mod_lookup 
                ON planner.itinerary_modules(destination, trip_type, style, duration_days, module_type, time_slot, day_index);
                """
                cursor.execute(ddl)
                conn.commit()
            else:
                ddl = """
                CREATE TABLE IF NOT EXISTS itinerary_modules (
                    id TEXT PRIMARY KEY,
                    destination TEXT NOT NULL,
                    trip_type TEXT NOT NULL DEFAULT 'flight',
                    style TEXT NOT NULL DEFAULT 'balanced',
                    duration_days INTEGER NOT NULL,
                    module_type TEXT NOT NULL,
                    time_slot TEXT,
                    day_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT 'system',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT DEFAULT 'system',
                    is_test INTEGER DEFAULT 0
                );
                """
                cursor.executescript(ddl)
                try:
                    cursor.execute("ALTER TABLE itinerary_modules ADD COLUMN trip_type TEXT NOT NULL DEFAULT 'flight';")
                except Exception:
                    pass
                try:
                    cursor.execute("ALTER TABLE itinerary_modules ADD COLUMN style TEXT NOT NULL DEFAULT 'balanced';")
                except Exception:
                    pass
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sqlite_itin_mod_lookup ON itinerary_modules(destination, trip_type, style, duration_days, module_type, time_slot, day_index);")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sqlite_itin_mod_dest ON itinerary_modules(destination);")
                except Exception:
                    pass
                conn.commit()
                conn.commit()
        except Exception as err:
            print(f"[ITINERARY MODULE DAO ERROR] Failed to initialize itinerary_modules table: {err}")
        finally:
            conn.close()

    def save_module(
        self,
        destination: str,
        duration_days: int,
        module_type: str,
        time_slot: Optional[str],
        day_index: int,
        content: dict[str, Any],
        trip_type: str = "flight",
        style: str = "balanced",
        created_by: str = "system",
        is_test: bool = False,
    ) -> bool:
        """Saves or updates a single itinerary module in the database."""
        dest_clean = str(destination).strip().lower()
        tt_clean = str(trip_type).strip().lower()
        style_clean = str(style).strip().lower()
        slot_clean = str(time_slot).strip().lower() if time_slot else None
        mtype_clean = str(module_type).strip().lower()
        now_str = datetime.now(timezone.utc).isoformat()
        content_json = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
        record_id = str(uuid.uuid4())

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                check_q = """
                SELECT id FROM itinerary_modules 
                WHERE destination = %s AND trip_type = %s AND style = %s AND duration_days = %s AND module_type = %s 
                  AND (time_slot = %s OR (time_slot IS NULL AND %s IS NULL)) AND day_index = %s
                LIMIT 1;
                """
                cursor.execute(check_q, (dest_clean, tt_clean, style_clean, duration_days, mtype_clean, slot_clean, slot_clean, day_index))
                row = cursor.fetchone()
                if row:
                    mod_id = row[0] if isinstance(row, (tuple, list)) else row["id"]
                    update_q = """
                    UPDATE itinerary_modules
                    SET content = %s, updated_at = %s, updated_by = %s, is_test = %s
                    WHERE id = %s;
                    """
                    cursor.execute(update_q, (content_json, now_str, created_by, is_test, mod_id))
                else:
                    insert_q = """
                    INSERT INTO itinerary_modules (
                        id, destination, trip_type, style, duration_days, module_type, time_slot, day_index,
                        content, created_at, created_by, updated_at, updated_by, is_test
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.execute(insert_q, (
                        record_id, dest_clean, tt_clean, style_clean, duration_days, mtype_clean, slot_clean, day_index,
                        content_json, now_str, created_by, now_str, created_by, is_test
                    ))
                conn.commit()
                return True
            else:
                cursor.execute(
                    """
                    SELECT id FROM itinerary_modules 
                    WHERE destination = ? AND trip_type = ? AND style = ? AND duration_days = ? AND module_type = ? 
                      AND (time_slot = ? OR (time_slot IS NULL AND ? IS NULL)) AND day_index = ?
                    LIMIT 1;
                    """,
                    (dest_clean, tt_clean, style_clean, duration_days, mtype_clean, slot_clean, slot_clean, day_index)
                )
                row = cursor.fetchone()
                if row:
                    mod_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
                    cursor.execute(
                        """
                        UPDATE itinerary_modules
                        SET content = ?, updated_at = ?, updated_by = ?, is_test = ?
                        WHERE id = ?;
                        """,
                        (content_json, now_str, created_by, 1 if is_test else 0, mod_id)
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO itinerary_modules (
                            id, destination, trip_type, style, duration_days, module_type, time_slot, day_index,
                            content, created_at, created_by, updated_at, updated_by, is_test
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            record_id, dest_clean, tt_clean, style_clean, duration_days, mtype_clean, slot_clean, day_index,
                            content_json, now_str, created_by, now_str, created_by, 1 if is_test else 0
                        )
                    )
                conn.commit()
                return True
        except Exception as err:
            print(f"[ITINERARY MODULE DAO ERROR] Failed to save module for '{dest_clean}': {err}")
            return False
        finally:
            conn.close()

    def save_modules_batch(
        self,
        modules: list[dict[str, Any]],
        created_by: str = "system",
        is_test: bool = False,
    ) -> int:
        """Saves a batch of itinerary modules."""
        saved_count = 0
        for m in modules:
            success = self.save_module(
                destination=m.get("destination", ""),
                duration_days=int(m.get("duration_days", 1)),
                module_type=m.get("module_type", "core_day"),
                time_slot=m.get("time_slot"),
                day_index=int(m.get("day_index", 1)),
                content=m.get("content", {}),
                trip_type=m.get("trip_type", "flight"),
                style=m.get("style", "balanced"),
                created_by=created_by,
                is_test=is_test,
            )
            if success:
                saved_count += 1
        return saved_count

    def get_modules(
        self,
        destination: str,
        duration_days: int,
        trip_type: str = "flight",
        style: str = "balanced",
        arrival_slot: Optional[str] = "12_14",
        departure_slot: Optional[str] = "16_18",
        is_test: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieves matching arrival module (day_index=0), core days (day_index 1..N-2),
        and departure module (day_index=-1) for stateless assembly.
        """
        dest_clean = str(destination).strip().lower()
        tt_clean = str(trip_type).strip().lower()
        style_clean = str(style).strip().lower()
        arr_slot = str(arrival_slot).strip().lower() if arrival_slot else None
        dep_slot = str(departure_slot).strip().lower() if departure_slot else None

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Try specific style first
            query_style = """
            SELECT id, destination, trip_type, style, duration_days, module_type, time_slot, day_index,
                   content, created_at, created_by, updated_at, updated_by, is_test
            FROM itinerary_modules
            WHERE destination = %s AND trip_type = %s AND style = %s AND duration_days = %s
            ORDER BY day_index ASC, id ASC;
            """ if self.db_engine == "postgresql" else """
            SELECT id, destination, trip_type, style, duration_days, module_type, time_slot, day_index,
                   content, created_at, created_by, updated_at, updated_by, is_test
            FROM itinerary_modules
            WHERE destination = ? AND trip_type = ? AND style = ? AND duration_days = ?
            ORDER BY day_index ASC, id ASC;
            """
            params_style = (dest_clean, tt_clean, style_clean, duration_days)
            cursor.execute(query_style, params_style)
            rows = cursor.fetchall()

            # If no rows for specific style, query without style restriction as fallback
            if not rows and style_clean != "balanced":
                query_fallback = """
                SELECT id, destination, trip_type, style, duration_days, module_type, time_slot, day_index,
                       content, created_at, created_by, updated_at, updated_by, is_test
                FROM itinerary_modules
                WHERE destination = %s AND trip_type = %s AND duration_days = %s
                ORDER BY day_index ASC, id ASC;
                """ if self.db_engine == "postgresql" else """
                SELECT id, destination, trip_type, style, duration_days, module_type, time_slot, day_index,
                       content, created_at, created_by, updated_at, updated_by, is_test
                FROM itinerary_modules
                WHERE destination = ? AND trip_type = ? AND duration_days = ?
                ORDER BY day_index ASC, id ASC;
                """
                cursor.execute(query_fallback, (dest_clean, tt_clean, duration_days))
                rows = cursor.fetchall()

            matched_modules = []
            arrival_candidates = []
            departure_candidates = []
            core_days = []

            for row in rows:
                if isinstance(row, dict):
                    r_dict = row
                elif isinstance(row, sqlite3.Row):
                    r_dict = dict(row)
                else:
                    r_dict = {
                        "id": row[0],
                        "destination": row[1],
                        "trip_type": row[2],
                        "style": row[3],
                        "duration_days": row[4],
                        "module_type": row[5],
                        "time_slot": row[6],
                        "day_index": row[7],
                        "content": row[8],
                        "created_at": row[9],
                        "created_by": row[10],
                        "updated_at": row[11],
                        "updated_by": row[12],
                        "is_test": bool(row[13]),
                    }

                raw_c = r_dict.get("content")
                if isinstance(raw_c, str):
                    try:
                        r_dict["content"] = json.loads(raw_c)
                    except Exception:
                        r_dict["content"] = {}

                mtype = str(r_dict.get("module_type", "")).lower()

                if mtype == "arrival" or r_dict.get("day_index") == 0:
                    arrival_candidates.append(r_dict)
                elif mtype == "departure" or r_dict.get("day_index") == -1:
                    departure_candidates.append(r_dict)
                else:
                    core_days.append(r_dict)

            chosen_arrival = None
            if arr_slot:
                for a in arrival_candidates:
                    if str(a.get("time_slot", "")).lower() == arr_slot:
                        chosen_arrival = a
                        break
            if not chosen_arrival and arrival_candidates:
                chosen_arrival = arrival_candidates[0]

            chosen_departure = None
            if dep_slot:
                for d in departure_candidates:
                    if str(d.get("time_slot", "")).lower() == dep_slot:
                        chosen_departure = d
                        break
            if not chosen_departure and departure_candidates:
                chosen_departure = departure_candidates[0]

            if chosen_arrival:
                matched_modules.append(chosen_arrival)
            matched_modules.extend(core_days)
            if chosen_departure:
                matched_modules.append(chosen_departure)

            return matched_modules
        except Exception as err:
            print(f"[ITINERARY MODULE DAO ERROR] Failed querying modules for '{dest_clean}': {err}")
            return []
        finally:
            conn.close()

    def get_distinct_destinations(self) -> list[str]:
        """Returns list of distinct destinations stored in the module cache."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            q = "SELECT DISTINCT destination FROM itinerary_modules ORDER BY destination ASC;"
            cursor.execute(q)
            rows = cursor.fetchall()
            destinations = []
            for r in rows:
                val = r[0] if isinstance(r, (tuple, list)) else (r.get("destination") if isinstance(r, dict) else r["destination"])
                if val:
                    destinations.append(str(val))
            return destinations
        except Exception as err:
            print(f"[ITINERARY MODULE DAO ERROR] Failed getting distinct destinations: {err}")
            return []
        finally:
            conn.close()

    def get_module_stats(self) -> dict[str, Any]:
        """Returns inventory count, distinct destinations, and freshness statistics."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            q_total = "SELECT COUNT(*) FROM itinerary_modules;"
            cursor.execute(q_total)
            total = cursor.fetchone()[0]

            q_dest = "SELECT COUNT(DISTINCT destination) FROM itinerary_modules;"
            cursor.execute(q_dest)
            total_dests = cursor.fetchone()[0]

            q_recent = "SELECT MAX(updated_at) FROM itinerary_modules;"
            cursor.execute(q_recent)
            last_updated = cursor.fetchone()[0]

            return {
                "total_modules_stored": total,
                "total_destinations": total_dests,
                "last_updated": str(last_updated) if last_updated else None,
                "db_engine": self.db_engine,
            }
        except Exception as err:
            return {"error": str(err), "db_engine": self.db_engine}
        finally:
            conn.close()

    def delete_stale_modules(self, max_age_days: int = 30) -> int:
        """Deletes modules older than max_age_days for maintenance cleanup."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.db_engine == "postgresql":
                q = """
                DELETE FROM itinerary_modules 
                WHERE updated_at < NOW() - INTERVAL '%s days';
                """
                cursor.execute(q, (max_age_days,))
                deleted = cursor.rowcount
            else:
                q = f"""
                DELETE FROM itinerary_modules 
                WHERE updated_at < datetime('now', '-{max_age_days} days');
                """
                cursor.execute(q)
                deleted = cursor.rowcount
            conn.commit()
            return deleted
        except Exception as err:
            print(f"[ITINERARY MODULE DAO ERROR] Failed deleting stale modules: {err}")
            return 0
        finally:
            conn.close()
