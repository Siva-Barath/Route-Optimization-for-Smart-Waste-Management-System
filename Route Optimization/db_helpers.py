"""
db_helpers.py — Database helper functions for Phase 1 migration.

All functions return data in the EXACT same dict format used by app_state.
The rest of the application (optimizer, APIs, frontend) does not need to change.

Every function is safe to call even if DB is unavailable — they return
empty structures so the caller can fall back to app_state gracefully.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from database import DB_AVAILABLE, get_db
from models import (
    User, Location, Facility,
    WasteReport, ReportingSession, CollectionHistory
)

logger = logging.getLogger(__name__)


# ── Guard decorator ───────────────────────────────────────────────────────────

def _db_safe(fallback):
    """
    Decorator that returns `fallback` value if DB is unavailable or any
    exception occurs, preventing DB failures from crashing the Flask app.
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            if not DB_AVAILABLE:
                logger.debug(f"DB unavailable — skipping {fn.__name__}")
                return fallback() if callable(fallback) else fallback
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"❌ db_helpers.{fn.__name__} failed: {e}")
                return fallback() if callable(fallback) else fallback
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


# ── Locations ─────────────────────────────────────────────────────────────────

@_db_safe(fallback=list)
def load_locations_from_db() -> list:
    """
    Load all locations (houses + bins) from DB.
    Returns a list of dicts in the same format as app_state['houses'].

    Each dict contains:
        id, lat, lng, type, source, status, has_garbage, collected
    """
    with get_db() as db:
        locations = db.query(Location).all()
        result = [loc.to_dict() for loc in locations]
        logger.info(f"✅ Loaded {len(result)} locations from DB")
        return result


@_db_safe(fallback=list)
def load_garbage_locations_from_db() -> list:
    """
    Load only locations where has_garbage=True.
    Equivalent to the current filter:
        [h for h in app_state['houses'] if h.get('has_garbage') == True]
    Used by optimize_route() as a drop-in replacement.
    """
    with get_db() as db:
        locations = db.query(Location).filter(
            Location.has_garbage == True
        ).all()
        return [loc.to_dict() for loc in locations]


@_db_safe(fallback=False)
def save_locations_to_db(houses: list) -> bool:
    """
    Bulk-insert or upsert a list of house/bin dicts into the locations table.
    Used during initialization and /api/generate_city.

    Accepts the same dict format produced by generate_spread_houses() and
    generate_smart_bins() — no reformatting needed.

    Returns True on success.
    """
    with get_db() as db:
        for h in houses:
            existing = db.get(Location, h["id"])
            if existing:
                # Update mutable fields, preserve collected state
                existing.lat           = h["lat"]
                existing.lng           = h["lng"]
                existing.location_type = h.get("type", "house")
                existing.source        = h.get("source", "predefined")
                existing.status        = h.get("status", "no_report")
                existing.has_garbage   = h.get("has_garbage", False)
                existing.osm_node_id   = str(h["node_id"]) if h.get("node_id") else None
            else:
                loc = Location(
                    id            = h["id"],
                    location_type = h.get("type", "house"),
                    lat           = h["lat"],
                    lng           = h["lng"],
                    osm_node_id   = str(h["node_id"]) if h.get("node_id") else None,
                    source        = h.get("source", "predefined"),
                    status        = h.get("status", "no_report"),
                    has_garbage   = h.get("has_garbage", False),
                    collected     = h.get("collected", False),
                )
                db.add(loc)
        db.commit()
        logger.info(f"✅ Saved {len(houses)} locations to DB")
        return True


@_db_safe(fallback=False)
def update_location_garbage_status(location_id: str, has_garbage: bool, status: str) -> bool:
    """
    Update has_garbage and status for a single location.
    Replacement for the in-place mutation in update_garbage_status() and report_garbage().
    """
    with get_db() as db:
        loc = db.get(Location, location_id)
        if not loc:
            logger.warning(f"⚠️ Location {location_id} not found in DB")
            return False
        loc.has_garbage = has_garbage
        loc.status      = status
        db.commit()
        return True


@_db_safe(fallback=False)
def mark_location_collected(location_id: str, truck_id: str) -> bool:
    """
    Mark a location as collected in the DB.
    Replacement for house['collected'] = True in mark_house_complete().
    """
    with get_db() as db:
        loc = db.get(Location, location_id)
        if not loc:
            return False
        loc.collected    = True
        loc.collected_by = truck_id
        db.commit()
        return True


@_db_safe(fallback=False)
def reset_all_locations() -> bool:
    """
    Reset all locations to initial state (no_report, has_garbage=False, collected=False).
    Equivalent to the reset loop in reset_simulation().
    Does NOT delete rows — preserves the location registry.
    """
    with get_db() as db:
        db.query(Location).update({
            "status":      "no_report",
            "has_garbage": False,
            "collected":   False,
            "collected_by": None,
        })
        db.commit()
        logger.info("✅ All locations reset in DB")
        return True


# ── Users / Residents ─────────────────────────────────────────────────────────

@_db_safe(fallback=None)
def create_user(name: str, phone: str, address: str = "",
                role: str = "resident") -> Optional[dict]:
    """
    Create a new resident user.
    Returns user dict on success, None if phone already exists.

    Used by register_house() to separate resident data from location data.
    """
    with get_db() as db:
        existing = db.query(User).filter_by(phone=phone).first()
        if existing:
            logger.info(f"User with phone {phone} already exists")
            return existing.to_dict()

        user = User(name=name, phone=phone, address=address, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"✅ Created user {user.id} — {name}")
        return user.to_dict()


@_db_safe(fallback=None)
def get_user_by_phone(phone: str) -> Optional[dict]:
    """
    Look up a user by phone number.
    Returns user dict or None.
    Replaces the linear scan in login_user().
    """
    with get_db() as db:
        user = db.query(User).filter_by(phone=phone).first()
        return user.to_dict() if user else None


@_db_safe(fallback=None)
def create_location_for_user(location_id: str, lat: float, lng: float,
                              resident_id: int) -> Optional[dict]:
    """
    Create a location row linked to a resident.
    Used by register_house() for user-registered houses.
    Returns location dict in app_state format.
    """
    with get_db() as db:
        loc = Location(
            id            = location_id,
            location_type = "house",
            lat           = lat,
            lng           = lng,
            source        = "live",
            status        = "no_report",
            has_garbage   = False,
            resident_id   = resident_id,
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)
        return loc.to_dict()


# ── Waste Reports ─────────────────────────────────────────────────────────────

@_db_safe(fallback=None)
def create_waste_report(location_id: str, report_type: str,
                        reported_by: str = "unknown") -> Optional[dict]:
    """
    Insert a waste report event into the waste_reports table.
    Call this alongside every has_garbage=True mutation.

    report_type: 'citizen' | 'admin_marked' | 'iot' | 'auto_select'
    """
    with get_db() as db:
        # Verify location exists
        loc = db.get(Location, location_id)
        if not loc:
            logger.warning(f"⚠️ Cannot create waste report — location {location_id} not found")
            return None

        report = WasteReport(
            location_id = location_id,
            report_type = report_type,
            reported_by = reported_by,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report.to_dict()


# ── Reporting Sessions ────────────────────────────────────────────────────────

@_db_safe(fallback=None)
def start_reporting_session(deadline_unix: int) -> Optional[int]:
    """
    Record the start of a reporting window.
    Returns the session ID (int) to store in app_state for later closing.
    """
    with get_db() as db:
        session = ReportingSession(deadline_unix=deadline_unix)
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info(f"✅ Reporting session {session.id} started")
        return session.id


@_db_safe(fallback=False)
def end_reporting_session(session_id: int, reports_count: int) -> bool:
    """
    Record the end of a reporting window with total reports count.
    """
    with get_db() as db:
        session = db.get(ReportingSession, session_id)
        if not session:
            return False
        session.ended_at      = datetime.now(timezone.utc)
        session.reports_count = reports_count
        db.commit()
        logger.info(f"✅ Reporting session {session_id} ended — {reports_count} reports")
        return True


# ── Collection History ────────────────────────────────────────────────────────

@_db_safe(fallback=False)
def save_collection_event(location_id: str, truck_id: str,
                          location_type: str = "house",
                          lat: float = None, lng: float = None) -> bool:
    """
    Persist a single collection event to the collection_history table.
    Replaces the app_state['collection_history'].append() call in mark_house_complete().

    Silently skips duplicates (UniqueConstraint on location_id).

    Returns True on success or if already exists.
    """
    with get_db() as db:
        # Check if already collected (UniqueConstraint would raise otherwise)
        existing = db.query(CollectionHistory).filter_by(
            location_id=location_id
        ).first()
        if existing:
            logger.debug(f"Collection event for {location_id} already exists — skipping")
            return True

        # If lat/lng not provided, pull from location table
        if lat is None or lng is None:
            loc = db.get(Location, location_id)
            if loc:
                lat = loc.lat
                lng = loc.lng

        record = CollectionHistory(
            location_id   = location_id,
            truck_id      = truck_id,
            location_type = location_type,
            lat           = lat,
            lng           = lng,
        )
        db.add(record)
        db.commit()
        logger.info(f"✅ Collection event saved: {location_id} by {truck_id}")
        return True


@_db_safe(fallback=list)
def load_collection_history() -> list:
    """
    Load full collection history from DB.
    Returns a list of dicts in the EXACT same format as app_state['collection_history']:

        [{
            'location_id':  'H27',
            'truck_id':     'T1',
            'type':         'house',
            'lat':          28.61...,
            'lng':          77.21...,
            'collected_at': 1717123456   (unix timestamp int)
        }, ...]
    """
    with get_db() as db:
        records = db.query(CollectionHistory).order_by(
            CollectionHistory.collected_at.desc()
        ).all()
        result = [r.to_dict() for r in records]
        logger.info(f"✅ Loaded {len(result)} collection history records from DB")
        return result


@_db_safe(fallback=list)
def load_collected_location_ids() -> list:
    """
    Return just the list of location_id strings that have been collected.
    Equivalent to app_state['collected_houses'] (which stores IDs).
    """
    with get_db() as db:
        rows = db.query(CollectionHistory.location_id).all()
        return [row[0] for row in rows]


@_db_safe(fallback=dict)
def get_collection_summary() -> dict:
    """
    Return summary stats for the collection history page.
    Mirrors the structure returned by /api/get_collection_history.
    """
    with get_db() as db:
        records = db.query(CollectionHistory).all()
        dicts   = [r.to_dict() for r in records]
        trucks  = sorted(set(r["truck_id"] for r in dicts))
        return {
            "records":       dicts,
            "trucks":        trucks,
            "summary": {
                "total_collected": len(dicts),
                "total_trucks":    len(trucks),
                "total_houses":    sum(1 for r in dicts if r["type"] != "bin"),
                "total_bins":      sum(1 for r in dicts if r["type"] == "bin"),
            }
        }


# ── Verification helper ────────────────────────────────────────────────────────

def verify_db_health() -> dict:
    """
    Check DB connectivity and return status summary.
    Used by the app startup log and optionally exposed via /api/db_health.
    Does not raise — always returns a dict.
    """
    if not DB_AVAILABLE:
        return {"available": False, "message": "DB not initialized"}

    try:
        from database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        with get_db() as db:
            loc_count      = db.query(Location).count()
            user_count     = db.query(User).count()
            history_count  = db.query(CollectionHistory).count()
            facility_count = db.query(Facility).count()

        return {
            "available":       True,
            "locations":       loc_count,
            "users":           user_count,
            "collection_events": history_count,
            "facilities":      facility_count,
        }
    except Exception as e:
        return {"available": False, "message": str(e)}
