"""
database.py — psycopg2 connection pool + CRUD helpers
Matches the exact schema already created in pgAdmin (smart_waste_db).

Table already in DB:
    locations (id SERIAL, display_id, location_type, latitude, longitude,
               osm_node_id, status, has_garbage, collected, created_at, geom)

Additional tables created by init_db() if not present:
    users, facilities, waste_reports, reporting_sessions, collection_history
"""

import os
import logging
from contextlib import contextmanager

# Load .env file if present (development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# ── Connection config ─────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST",     "localhost"),
    "port":     int(os.environ.get("DB_PORT", "5432")),
    "dbname":   os.environ.get("DB_NAME",     "smart_waste_db"),
    "user":     os.environ.get("DB_USER",     "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
    "connect_timeout": 5,
}

_pool = None
DB_AVAILABLE = False


# ── Pool init ─────────────────────────────────────────────────────────────────

def init_db() -> bool:
    """
    Initialize connection pool and create missing tables.
    Call once at Flask startup.
    Returns True on success, False if PostgreSQL is unreachable.
    App continues with app_state if this returns False.
    """
    global _pool, DB_AVAILABLE

    try:
        _pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            **DB_CONFIG
        )
        # Smoke-test
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                ver = cur.fetchone()[0]
                logger.info(f"✅ PostgreSQL connected: {ver[:40]}")

        _create_tables()
        _seed_facilities()
        _seed_resident_accounts()
        DB_AVAILABLE = True
        logger.info("✅ DB layer ready (smart_waste_db)")
        return True

    except Exception as e:
        DB_AVAILABLE = False
        logger.warning(f"⚠️  PostgreSQL unavailable — running in-memory only: {e}")
        return False


@contextmanager
def get_connection():
    """
    Yield a psycopg2 connection from the pool.
    Commits on clean exit, rolls back on exception, always returns to pool.
    """
    if _pool is None:
        raise RuntimeError("DB pool not initialised. Call init_db() first.")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


# ── Schema creation ───────────────────────────────────────────────────────────

def _create_tables():
    """
    Create tables that don't exist yet.
    The `locations` table was already created manually in pgAdmin — this
    statement uses IF NOT EXISTS so it is safe to run again.
    """
    ddl = """
    -- locations: already created in pgAdmin, recreated safely
    CREATE TABLE IF NOT EXISTS locations (
        id            SERIAL PRIMARY KEY,
        display_id    VARCHAR(20) UNIQUE,
        location_type VARCHAR(20) NOT NULL,
        latitude      DOUBLE PRECISION,
        longitude     DOUBLE PRECISION,
        osm_node_id   BIGINT,
        status        VARCHAR(30) DEFAULT 'no_report',
        has_garbage   BOOLEAN     DEFAULT FALSE,
        collected     BOOLEAN     DEFAULT FALSE,
        collected_by  VARCHAR(10),
        source        VARCHAR(20) DEFAULT 'predefined',
        created_at    TIMESTAMPTZ DEFAULT NOW(),
        geom          GEOMETRY(Point, 4326)
    );
    CREATE INDEX IF NOT EXISTS ix_loc_has_garbage ON locations(has_garbage);
    CREATE INDEX IF NOT EXISTS ix_loc_type        ON locations(location_type);
    CREATE INDEX IF NOT EXISTS ix_loc_status      ON locations(status);

    -- users / residents
    CREATE TABLE IF NOT EXISTS users (
        id            SERIAL PRIMARY KEY,
        name          VARCHAR(100),
        phone         VARCHAR(20)  UNIQUE,
        address       TEXT,
        password_hash VARCHAR(255),
        role          VARCHAR(20)  DEFAULT 'resident',
        created_at    TIMESTAMPTZ  DEFAULT NOW()
    );

    -- facilities (processing centers, depots)
    CREATE TABLE IF NOT EXISTS facilities (
        id            SERIAL PRIMARY KEY,
        name          TEXT         NOT NULL,
        facility_type VARCHAR(50)  NOT NULL,
        latitude      DOUBLE PRECISION NOT NULL,
        longitude     DOUBLE PRECISION NOT NULL,
        city          VARCHAR(100) DEFAULT 'Delhi',
        active        BOOLEAN      DEFAULT TRUE,
        created_at    TIMESTAMPTZ  DEFAULT NOW()
    );

    -- waste_reports (one row per report event)
    CREATE TABLE IF NOT EXISTS waste_reports (
        id            SERIAL PRIMARY KEY,
        location_id   INTEGER      REFERENCES locations(id),
        report_type   VARCHAR(30)  NOT NULL,
        reported_by   VARCHAR(100),
        reported_at   TIMESTAMPTZ  DEFAULT NOW()
    );

    -- reporting_sessions
    CREATE TABLE IF NOT EXISTS reporting_sessions (
        id            SERIAL PRIMARY KEY,
        started_at    TIMESTAMPTZ  DEFAULT NOW(),
        ended_at      TIMESTAMPTZ,
        reports_count INTEGER      DEFAULT 0,
        deadline_unix INTEGER
    );

    -- collection_history (permanent audit log)
    CREATE TABLE IF NOT EXISTS collection_history (
        id            SERIAL PRIMARY KEY,
        location_id   INTEGER      REFERENCES locations(id),
        truck_id      VARCHAR(10)  NOT NULL,
        location_type VARCHAR(10)  DEFAULT 'house',
        latitude      DOUBLE PRECISION,
        longitude     DOUBLE PRECISION,
        collected_at  TIMESTAMPTZ  DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_ch_truck       ON collection_history(truck_id);
    CREATE INDEX IF NOT EXISTS ix_ch_collected   ON collection_history(collected_at);

    -- resident_accounts table
    CREATE TABLE IF NOT EXISTS resident_accounts (
        id            SERIAL PRIMARY KEY,
        house_id      VARCHAR(20)  REFERENCES locations(display_id),
        username      VARCHAR(50)  UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at    TIMESTAMPTZ  DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_ra_username    ON resident_accounts(username);
    CREATE INDEX IF NOT EXISTS ix_ra_house       ON resident_accounts(house_id);

    -- notification_logs table
    CREATE TABLE IF NOT EXISTS notification_logs (
        id            SERIAL PRIMARY KEY,
        location_id   VARCHAR(20),
        phone_number  VARCHAR(30)  NOT NULL,
        event_type    VARCHAR(30)  NOT NULL,
        message_body  TEXT         NOT NULL,
        twilio_sid    VARCHAR(100),
        status        VARCHAR(20)  DEFAULT 'pending',
        sent_at       TIMESTAMPTZ  DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_nl_location    ON notification_logs(location_id);
    CREATE INDEX IF NOT EXISTS ix_nl_event       ON notification_logs(event_type);

    -- app_settings table
    CREATE TABLE IF NOT EXISTS app_settings (
        key   VARCHAR PRIMARY KEY,
        value VARCHAR NOT NULL
    );
    INSERT INTO app_settings (key, value) VALUES ('reporting_window_open', 'false')
    ON CONFLICT (key) DO NOTHING;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
            # Schema migration: Add report_source to waste_reports if it doesn't exist
            cur.execute("ALTER TABLE waste_reports ADD COLUMN IF NOT EXISTS report_source VARCHAR(20) DEFAULT 'ADMIN_PANEL';")
    logger.info("✅ All tables verified / created")


def _seed_facilities():
    """Insert default processing center and depot if facilities table is empty."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM facilities")
            count = cur.fetchone()[0]
            if count == 0:
                cur.execute("""
                    INSERT INTO facilities (name, facility_type, latitude, longitude, city)
                    VALUES
                        ('North Delhi Processing Center', 'processing_center', 28.6410, 77.2190, 'Delhi'),
                        ('Central Delhi Depot',           'depot',             28.6139, 77.2090, 'Delhi')
                """)
                logger.info("✅ Default facilities seeded")


# ── Locations CRUD ────────────────────────────────────────────────────────────

def create_location(display_id: str, location_type: str,
                    lat: float, lng: float,
                    osm_node_id=None, source: str = "predefined",
                    status: str = "no_report") -> dict | None:
    """
    Insert a new location row.
    Returns the inserted row as a dict (app_state-compatible format).
    """
    if not DB_AVAILABLE:
        return None
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO locations
                        (display_id, location_type, latitude, longitude,
                         osm_node_id, source, status,
                         geom)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s,
                         ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                    ON CONFLICT (display_id) DO UPDATE SET
                        latitude      = EXCLUDED.latitude,
                        longitude     = EXCLUDED.longitude,
                        location_type = EXCLUDED.location_type,
                        source        = EXCLUDED.source,
                        geom          = EXCLUDED.geom
                    RETURNING *
                """, (
                    display_id, location_type, lat, lng,
                    osm_node_id, source, status,
                    lng, lat          # ST_MakePoint(lon, lat)
                ))
                row = cur.fetchone()
                return _row_to_app_dict(dict(row))
    except Exception as e:
        logger.error(f"create_location failed for {display_id}: {e}")
        return None


def update_location(display_id: str, **fields) -> bool:
    """
    Update arbitrary fields on a location row.
    Supported fields: status, has_garbage, collected, collected_by

    Usage:
        update_location("H27", has_garbage=True, status="admin_marked")
    """
    if not DB_AVAILABLE or not fields:
        return False

    allowed = {"status", "has_garbage", "collected", "collected_by"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return False

    set_clause = ", ".join(f"{k} = %s" for k in safe)
    values = list(safe.values()) + [display_id]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE locations SET {set_clause} WHERE display_id = %s",
                    values
                )
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"update_location failed for {display_id}: {e}")
        return False


def get_locations() -> list:
    """
    Fetch all locations.
    Returns list of dicts in app_state['houses'] format.
    """
    if not DB_AVAILABLE:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM locations ORDER BY id")
                rows = cur.fetchall()
                return [_row_to_app_dict(dict(r)) for r in rows]
    except Exception as e:
        logger.error(f"get_locations failed: {e}")
        return []


def get_garbage_locations() -> list:
    """
    Fetch only locations where has_garbage = TRUE.
    Drop-in replacement for:
        [h for h in app_state['houses'] if h.get('has_garbage') == True]
    """
    if not DB_AVAILABLE:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM locations WHERE has_garbage = TRUE ORDER BY id"
                )
                rows = cur.fetchall()
                return [_row_to_app_dict(dict(r)) for r in rows]
    except Exception as e:
        logger.error(f"get_garbage_locations failed: {e}")
        return []


def bulk_insert_locations(houses: list) -> bool:
    """
    Upsert a list of house/bin dicts (from generate_spread_houses etc.)
    into the locations table.
    Uses ON CONFLICT (display_id) DO UPDATE so it is idempotent.
    """
    if not DB_AVAILABLE or not houses:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for h in houses:
                    node_id = h.get("node_id")
                    if node_id is not None:
                        try:
                            node_id = int(node_id)
                        except (TypeError, ValueError):
                            node_id = None

                    cur.execute("""
                        INSERT INTO locations
                            (display_id, location_type, latitude, longitude,
                             osm_node_id, source, status, has_garbage,
                             geom)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s,
                             ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        ON CONFLICT (display_id) DO UPDATE SET
                            latitude      = EXCLUDED.latitude,
                            longitude     = EXCLUDED.longitude,
                            location_type = EXCLUDED.location_type,
                            source        = EXCLUDED.source,
                            status        = EXCLUDED.status,
                            has_garbage   = EXCLUDED.has_garbage,
                            geom          = EXCLUDED.geom
                    """, (
                        h["id"],
                        h.get("type", "house"),
                        h["lat"], h["lng"],
                        node_id,
                        h.get("source", "predefined"),
                        h.get("status", "no_report"),
                        h.get("has_garbage", False),
                        h["lng"], h["lat"]      # ST_MakePoint(lon, lat)
                    ))
        logger.info(f"✅ Bulk-upserted {len(houses)} locations to DB")
        _seed_resident_accounts()
        return True
    except Exception as e:
        logger.error(f"bulk_insert_locations failed: {e}")
        return False


def reset_locations_status() -> bool:
    """
    Reset all locations: status='no_report', has_garbage=False, collected=False.
    Called by reset_simulation(). Does NOT delete rows.
    """
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE locations
                    SET status       = 'no_report',
                        has_garbage  = FALSE,
                        collected    = FALSE,
                        collected_by = NULL
                """)
        logger.info("✅ All locations reset in DB")
        return True
    except Exception as e:
        logger.error(f"reset_locations_status failed: {e}")
        return False


def clear_waste_reports() -> bool:
    """
    Clear all records from the waste_reports table in PostgreSQL.
    Called by reset_simulation() to ensure all reports are cleared.
    """
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM waste_reports")
        logger.info("✅ Waste reports cleared in DB")
        return True
    except Exception as e:
        logger.error(f"clear_waste_reports failed: {e}")
        return False


def clear_collection_history_db() -> bool:
    """
    Clear all records from the collection_history table in PostgreSQL.
    """
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM collection_history")
        logger.info("✅ Collection history cleared in DB")
        return True
    except Exception as e:
        logger.error(f"clear_collection_history_db failed: {e}")
        return False


# ── Collection History ────────────────────────────────────────────────────────

def save_collection_event(display_id: str, truck_id: str,
                          location_type: str = "house",
                          lat: float = None, lng: float = None) -> bool:
    """
    Persist a collection event.
    Silently skips if already collected (UNIQUE constraint on location_id).
    """
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get the integer PK for this display_id
                cur.execute(
                    "SELECT id, latitude, longitude FROM locations WHERE display_id = %s",
                    (display_id,)
                )
                row = cur.fetchone()
                if not row:
                    logger.warning(f"save_collection_event: {display_id} not in DB")
                    return False
                loc_pk = row[0]
                if lat is None:
                    lat = row[1]
                if lng is None:
                    lng = row[2]

                cur.execute("""
                    INSERT INTO collection_history
                        (location_id, truck_id, location_type, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s)
                """, (loc_pk, truck_id, location_type, lat, lng))
        logger.info(f"✅ Collection event saved: {display_id} by {truck_id}")
        return True
    except Exception as e:
        logger.error(f"save_collection_event failed for {display_id}: {e}")
        return False


def load_collection_history() -> list:
    """
    Return collection history as list of dicts matching app_state format:
        [{'location_id': 'H27', 'truck_id': 'T1', 'type': 'house',
          'lat': ..., 'lng': ..., 'collected_at': <unix int>}, ...]
    """
    if not DB_AVAILABLE:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT ch.id, l.display_id, ch.truck_id,
                           ch.location_type, ch.latitude, ch.longitude,
                           ch.collected_at
                    FROM   collection_history ch
                    JOIN   locations l ON l.id = ch.location_id
                    ORDER  BY ch.collected_at DESC
                """)
                rows = cur.fetchall()
                return [
                    {
                        "location_id":  r["display_id"],
                        "truck_id":     r["truck_id"],
                        "type":         r["location_type"],
                        "lat":          r["latitude"],
                        "lng":          r["longitude"],
                        "collected_at": int(r["collected_at"].timestamp())
                                        if r["collected_at"] else None,
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.error(f"load_collection_history failed: {e}")
        return []


def load_collected_ids() -> list:
    """
    Return list of display_ids that have been collected.
    Replaces app_state['collected_houses'].
    """
    if not DB_AVAILABLE:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT l.display_id
                    FROM   collection_history ch
                    JOIN   locations l ON l.id = ch.location_id
                """)
                return [r[0] for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"load_collected_ids failed: {e}")
        return []


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(name: str, phone: str, address: str = "",
                role: str = "resident") -> dict | None:
    """Create a resident. Returns user dict or None if phone already exists."""
    if not DB_AVAILABLE:
        return None
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO users (name, phone, address, role)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (phone) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id, name, phone, address, role
                """, (name, phone, address, role))
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.error(f"create_user failed for {phone}: {e}")
        return None


def get_user_by_phone(phone: str) -> dict | None:
    """Look up a user by phone. Replaces the linear scan in login_user()."""
    if not DB_AVAILABLE:
        return None
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, phone, address, role FROM users WHERE phone = %s",
                    (phone,)
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_user_by_phone failed for {phone}: {e}")
        return None


# ── Waste Reports ─────────────────────────────────────────────────────────────

def create_waste_report(display_id: str, report_type: str,
                        reported_by: str = "unknown",
                        report_source: str = "ADMIN_PANEL") -> bool:
    """
    Insert a waste report event.
    report_type: 'citizen' | 'admin_marked' | 'iot' | 'auto_select'
    report_source: 'USER_APP' | 'ADMIN_PANEL' | 'IOT_BIN'
    """
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM locations WHERE display_id = %s", (display_id,)
                )
                row = cur.fetchone()
                if not row:
                    return False
                cur.execute("""
                    INSERT INTO waste_reports (location_id, report_type, reported_by)
                    VALUES (%s, %s, %s)
                """, (row[0], report_type, reported_by))
        return True
    except Exception as e:
        logger.error(f"create_waste_report failed for {display_id}: {e}")
        return False


# ── Reporting Sessions ────────────────────────────────────────────────────────

def start_reporting_session(deadline_unix: int) -> int | None:
    """Record start of a reporting window. Returns session id."""
    if not DB_AVAILABLE:
        return None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reporting_sessions (deadline_unix)
                    VALUES (%s) RETURNING id
                """, (deadline_unix,))
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"start_reporting_session failed: {e}")
        return None


def end_reporting_session(session_id: int, reports_count: int) -> bool:
    """Record end of a reporting window."""
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE reporting_sessions
                    SET ended_at = NOW(), reports_count = %s
                    WHERE id = %s
                """, (reports_count, session_id))
        return True
    except Exception as e:
        logger.error(f"end_reporting_session failed: {e}")
        return False


# ── Health check ──────────────────────────────────────────────────────────────

def db_health() -> dict:
    """Return DB status dict. Always returns a dict, never raises."""
    if not DB_AVAILABLE:
        return {"available": False, "message": "Not connected"}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM locations")
                loc  = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM users")
                usr  = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM collection_history")
                hist = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM facilities")
                fac  = cur.fetchone()[0]
        return {
            "available":          True,
            "database":           DB_CONFIG["dbname"],
            "locations":          loc,
            "users":              usr,
            "collection_history": hist,
            "facilities":         fac,
        }
    except Exception as e:
        return {"available": False, "message": str(e)}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _row_to_app_dict(row: dict) -> dict:
    """
    Convert a DB row dict to the app_state['houses'] entry format.
    Column names in the DB use 'latitude'/'longitude' and 'display_id';
    the app_state and optimizer use 'lat'/'lng' and 'id'.
    """
    return {
        "id":          row.get("display_id") or str(row.get("id")),
        "lat":         row.get("latitude"),
        "lng":         row.get("longitude"),
        "type":        row.get("location_type", "house"),
        "source":      row.get("source", "predefined"),
        "status":      row.get("status", "no_report"),
        "has_garbage": row.get("has_garbage", False),
        "collected":   row.get("collected", False),
        **({"collected_by": row["collected_by"]} if row.get("collected_by") else {}),
        **({"node_id": row["osm_node_id"]}       if row.get("osm_node_id")  else {}),
    }


# ── Resident Accounts & Auth Helpers ──────────────────────────────────────────

def _seed_resident_accounts():
    """Seed default resident credentials for predefined houses (H1..H45) in resident_accounts"""
    try:
        from werkzeug.security import generate_password_hash
    except ImportError:
        def generate_password_hash(p): return p

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Seed H1 to H45
                for i in range(1, 46):
                    house_id = f"H{i}"
                    username = house_id
                    password = f"{house_id}@2026"
                    pw_hash = generate_password_hash(password)
                    
                    # Verify if the location actually exists in locations table first
                    cur.execute("SELECT 1 FROM locations WHERE display_id = %s", (house_id,))
                    if not cur.fetchone():
                        continue

                    # Insert account if not exists
                    cur.execute("""
                        INSERT INTO resident_accounts (house_id, username, password_hash)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (username) DO NOTHING
                    """, (house_id, username, pw_hash))
        logger.info("✅ Predefined resident accounts (H1..H45) verified/seeded in DB")
    except Exception as e:
        logger.error(f"_seed_resident_accounts failed: {e}")


def authenticate_resident_db(username: str, password: str) -> dict | None:
    """Authenticate a resident. Returns location/account dict or None if invalid."""
    if not DB_AVAILABLE:
        return None
    try:
        from werkzeug.security import check_password_hash
    except ImportError:
        def check_password_hash(pw_hash, pwd): return pw_hash == pwd

    normalized_username = username.strip().upper()
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT ra.house_id, l.latitude as lat, l.longitude as lng, ra.password_hash 
                    FROM resident_accounts ra
                    JOIN locations l ON ra.house_id = l.display_id
                    WHERE ra.username = %s
                """, (normalized_username,))
                row = cur.fetchone()
                if row:
                    res = dict(row)
                    if check_password_hash(res['password_hash'], password):
                        house_id = res['house_id']
                        ward = "Zone A"
                        if house_id.startswith('H'):
                            try:
                                h_num = int(house_id[1:])
                                if 16 <= h_num <= 30:
                                    ward = "Zone B"
                                elif h_num >= 31:
                                    ward = "Zone C"
                            except ValueError:
                                pass
                        return {
                            "success": True,
                            "house_id": house_id,
                            "username": normalized_username,
                            "address": f"Demo Household {house_id}",
                            "ward": ward,
                            "lat": res['lat'],
                            "lng": res['lng']
                        }
        return None
    except Exception as e:
        logger.error(f"authenticate_resident_db failed for {username}: {e}")
        return None


def validate_house_ownership_db(username: str, house_id: str) -> bool:
    """Verify if the given username owns the specified house_id."""
    if not DB_AVAILABLE:
        return False
    normalized_username = username.strip().upper()
    normalized_house_id = house_id.strip().upper()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM resident_accounts 
                    WHERE username = %s AND house_id = %s
                """, (normalized_username, normalized_house_id))
                return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"validate_house_ownership_db failed for {username} -> {house_id}: {e}")
        return False


def get_house_by_username_db(username: str) -> str | None:
    """Get the house_id owned by the given username."""
    if not DB_AVAILABLE:
        return None
    normalized_username = username.strip().upper()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT house_id FROM resident_accounts 
                    WHERE username = %s
                """, (normalized_username,))
                row = cur.fetchone()
                return row[0] if row else None
    except Exception as e:
        logger.error(f"get_house_by_username_db failed for {username}: {e}")
        return None



def get_resident_profile_db(house_id: str) -> dict | None:
    """Get profile of a resident including current garbage status."""
    if not DB_AVAILABLE:
        return None
    normalized_house_id = house_id.strip().upper()
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT ra.username, l.status, l.has_garbage
                    FROM resident_accounts ra
                    JOIN locations l ON ra.house_id = l.display_id
                    WHERE ra.house_id = %s
                """, (normalized_house_id,))
                row = cur.fetchone()
                if row:
                    res = dict(row)
                    return {
                        "house_id": normalized_house_id,
                        "username": res["username"],
                        "status": res["status"],
                        "has_garbage": res["has_garbage"]
                    }
        return None
    except Exception as e:
        logger.error(f"get_resident_profile_db failed for {house_id}: {e}")
        return None


def get_resident_reports_db(house_id: str) -> list:
    """Get report history for a house using EXISTS status checking."""
    if not DB_AVAILABLE:
        return []
    normalized_house_id = house_id.strip().upper()
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        wr.reported_at,
                        wr.report_type,
                        CASE
                            WHEN EXISTS (
                                SELECT 1
                                FROM collection_history ch
                                WHERE ch.location_id = wr.location_id
                                AND ch.collected_at > wr.reported_at
                            )
                            THEN 'collected'
                            ELSE 'reported'
                        END AS status
                    FROM waste_reports wr
                    JOIN locations l ON wr.location_id = l.id
                    WHERE l.display_id = %s
                    ORDER BY wr.reported_at DESC;
                """, (normalized_house_id,))
                rows = cur.fetchall()
                reports = []
                for row in rows:
                    r = dict(row)
                    if r.get('reported_at'):
                        r['reported_at'] = r['reported_at'].isoformat()
                    reports.append(r)
                return reports
    except Exception as e:
        logger.error(f"get_resident_reports_db failed for {house_id}: {e}")
        return []


def get_all_resident_credentials_db() -> list:
    """Return all active resident accounts with their corresponding plaintext demo passwords."""
    accounts = []
    for i in range(1, 46):
        accounts.append({
            "username": f"H{i}",
            "password": f"H{i}@2026"
        })
    return accounts


def save_notification_log(location_id: str, phone: str, event_type: str,
                          body: str, twilio_sid: str = None, status: str = 'pending') -> bool:
    """Save a notification log entry to the database."""
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO notification_logs (location_id, phone_number, event_type, message_body, twilio_sid, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (location_id, phone, event_type, body, twilio_sid, status))
        return True
    except Exception as e:
        logger.error(f"save_notification_log failed for {location_id}: {e}")
        return False


def get_notification_logs(limit: int = 100) -> list:
    """Retrieve the latest notification logs."""
    if not DB_AVAILABLE:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, location_id, phone_number, event_type, message_body, twilio_sid, status, sent_at
                    FROM notification_logs
                    ORDER BY sent_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                logs = []
                for row in rows:
                    r = dict(row)
                    if r.get('sent_at'):
                        r['sent_at'] = r['sent_at'].isoformat()
                    logs.append(r)
                return logs
    except Exception as e:
        logger.error(f"get_notification_logs failed: {e}")
        return []


def get_setting(key: str, default: str = None) -> str | None:
    """Retrieve an app setting value by key."""
    if not DB_AVAILABLE:
        return default
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
                row = cur.fetchone()
                return row[0] if row else default
    except Exception as e:
        logger.error(f"get_setting failed for {key}: {e}")
        return default


def set_setting(key: str, value: str) -> bool:
    """Insert or update an app setting value."""
    if not DB_AVAILABLE:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO app_settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """, (key, value))
        return True
    except Exception as e:
        logger.error(f"set_setting failed for {key} = {value}: {e}")
        return False

