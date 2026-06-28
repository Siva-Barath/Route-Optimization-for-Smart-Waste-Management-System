"""
SQLAlchemy ORM models — Phase 1
Tables: users, facilities, locations, waste_reports, reporting_sessions, collection_history
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, Text,
    DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


# ── Users / Residents ─────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    display_id    = Column(String(20), unique=True, nullable=True)   # H1, U001, etc.
    name          = Column(String(100), nullable=True)
    phone         = Column(String(20), unique=True, nullable=True)
    address       = Column(Text, nullable=True)
    password_hash = Column(String(255), nullable=True)
    role          = Column(String(20), default="resident")  # resident | driver | admin
    created_at    = Column(DateTime(timezone=True), default=utcnow)

    # relationships
    locations     = relationship("Location", back_populates="resident",
                                 foreign_keys="Location.resident_id")

    def to_dict(self):
        return {
            "id":         self.id,
            "display_id": self.display_id,
            "name":       self.name,
            "phone":      self.phone,
            "address":    self.address,
            "role":       self.role,
        }


# ── Facilities (processing centers, depots) ───────────────────────────────────
class Facility(Base):
    __tablename__ = "facilities"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(200), nullable=False)
    facility_type = Column(String(50), nullable=False)  # processing_center | depot
    lat           = Column(Float, nullable=False)
    lng           = Column(Float, nullable=False)
    city          = Column(String(100), default="Delhi")
    active        = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            "id":            self.id,
            "name":          self.name,
            "facility_type": self.facility_type,
            "lat":           self.lat,
            "lng":           self.lng,
        }


# ── Locations (houses + bins unified) ────────────────────────────────────────
class Location(Base):
    __tablename__ = "locations"

    # Primary key is the human-readable ID used throughout the system (H1, B3, U001)
    id            = Column(String(20), primary_key=True)
    location_type = Column(String(20), nullable=False)   # house | bin | processing_center

    lat           = Column(Float, nullable=False)
    lng           = Column(Float, nullable=False)
    osm_node_id   = Column(String(30), nullable=True)    # OSMnx road node

    source        = Column(String(20), default="predefined")  # predefined | live | fallback
    status        = Column(String(30), default="no_report")   # no_report | admin_marked | reported | pending | FULL | EMPTY
    has_garbage   = Column(Boolean, default=False)
    collected     = Column(Boolean, default=False)
    collected_by  = Column(String(10), nullable=True)    # truck ID

    # Resident link (nullable — predefined houses have no resident)
    resident_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    resident      = relationship("User", back_populates="locations",
                                 foreign_keys=[resident_id])

    created_at    = Column(DateTime(timezone=True), default=utcnow)
    updated_at    = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    waste_reports      = relationship("WasteReport", back_populates="location",
                                      foreign_keys="WasteReport.location_id")
    collection_records = relationship("CollectionHistory", back_populates="location",
                                      foreign_keys="CollectionHistory.location_id")

    __table_args__ = (
        Index("ix_locations_has_garbage", "has_garbage"),
        Index("ix_locations_type",        "location_type"),
        Index("ix_locations_status",      "status"),
    )

    def to_dict(self):
        """
        Returns a dict in the exact same format used by app_state['houses'].
        Frontend and optimizer receive identical structure.
        """
        d = {
            "id":          self.id,
            "lat":         self.lat,
            "lng":         self.lng,
            "type":        self.location_type,
            "source":      self.source,
            "status":      self.status,
            "has_garbage": self.has_garbage,
            "collected":   self.collected,
        }
        if self.collected_by:
            d["collected_by"] = self.collected_by
        if self.osm_node_id:
            d["node_id"] = self.osm_node_id
        # Include resident fields if present (for user-registered houses)
        if self.resident:
            d["name"]  = self.resident.name
            d["phone"] = self.resident.phone
        return d


# ── Waste Reports ─────────────────────────────────────────────────────────────
class WasteReport(Base):
    __tablename__ = "waste_reports"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    location_id  = Column(String(20), ForeignKey("locations.id"), nullable=False)
    report_type  = Column(String(30), nullable=False)  # citizen | admin_marked | iot | auto_select
    reported_by  = Column(String(100), nullable=True)  # phone or 'admin' or 'iot'
    reported_at  = Column(DateTime(timezone=True), default=utcnow)

    location     = relationship("Location", back_populates="waste_reports",
                                foreign_keys=[location_id])

    def to_dict(self):
        return {
            "id":          self.id,
            "location_id": self.location_id,
            "report_type": self.report_type,
            "reported_by": self.reported_by,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None,
        }


# ── Reporting Sessions ────────────────────────────────────────────────────────
class ReportingSession(Base):
    __tablename__ = "reporting_sessions"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    started_at    = Column(DateTime(timezone=True), default=utcnow)
    ended_at      = Column(DateTime(timezone=True), nullable=True)
    reports_count = Column(Integer, default=0)
    deadline_unix = Column(Integer, nullable=True)   # unix timestamp, mirrors app_state

    def to_dict(self):
        return {
            "id":            self.id,
            "started_at":    self.started_at.isoformat() if self.started_at else None,
            "ended_at":      self.ended_at.isoformat()   if self.ended_at   else None,
            "reports_count": self.reports_count,
        }


# ── Collection History ────────────────────────────────────────────────────────
class CollectionHistory(Base):
    __tablename__ = "collection_history"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    location_id  = Column(String(20), ForeignKey("locations.id"), nullable=False)
    truck_id     = Column(String(10), nullable=False)
    location_type = Column(String(10), nullable=False, default="house")  # house | bin
    lat          = Column(Float, nullable=True)
    lng          = Column(Float, nullable=True)
    collected_at = Column(DateTime(timezone=True), default=utcnow)

    location     = relationship("Location", back_populates="collection_records",
                                foreign_keys=[location_id])

    __table_args__ = (
        Index("ix_collection_history_location_id", "location_id"),
        Index("ix_collection_history_truck_id",    "truck_id"),
        Index("ix_collection_history_collected_at","collected_at"),
        # Prevent duplicate collection entries for same location
        UniqueConstraint("location_id", name="uq_collection_history_location"),
    )

    def to_dict(self):
        """
        Returns dict in exact same format as app_state['collection_history'] entries.
        """
        return {
            "location_id":  self.location_id,
            "truck_id":     self.truck_id,
            "type":         self.location_type,
            "lat":          self.lat,
            "lng":          self.lng,
            "collected_at": int(self.collected_at.timestamp()) if self.collected_at else None,
        }
