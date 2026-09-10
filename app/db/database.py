import sqlite3
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "thermal_intel.db"

class DatabaseManager:
    """
    SQLite Database Manager for SIH 2026 Thermal AI Platform.
    Manages persistent relational storage for:
    1. Users (Auth, Credentials, Roles)
    2. Thermal Sources (Clustered Hotspots, Ground Truth, Live Ingested Sources)
    3. Dispatched Alerts (National Authority Briefs & Audit Logs)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        os.makedirs(self.db_path.parent, exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """Initializes database tables and creates indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    organization TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            # 2. Thermal Sources Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS thermal_sources (
                    source_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    predicted_event_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    confidence_pct REAL NOT NULL,
                    persistence_score REAL NOT NULL,
                    sih_alert_severity TEXT NOT NULL,
                    total_detections INTEGER NOT NULL,
                    active_days INTEGER NOT NULL,
                    observation_span_days INTEGER NOT NULL,
                    mean_frp REAL NOT NULL,
                    max_frp REAL NOT NULL,
                    mean_brightness REAL NOT NULL,
                    max_brightness REAL NOT NULL,
                    nearest_facility_name TEXT,
                    nearest_facility_type TEXT,
                    min_distance_to_industry_km REAL,
                    nearest_refinery_km REAL,
                    nearest_powerplant_km REAL,
                    nearest_mine_km REAL,
                    nearest_industrial_area_km REAL,
                    mean_industrial_facilities_1km INTEGER,
                    mean_industrial_facilities_5km INTEGER,
                    landcover_class TEXT,
                    first_detection TEXT,
                    last_detection TEXT,
                    is_persistent INTEGER NOT NULL,
                    is_flare_anomaly INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_description TEXT,
                    marker_color TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_state ON thermal_sources (state);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON thermal_sources (predicted_event_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_severity ON thermal_sources (sih_alert_severity);")

            # 3. Dispatched Alerts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dispatched_alerts (
                    dispatch_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    target_agency TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    dispatched_by TEXT NOT NULL,
                    critical_events_count INTEGER NOT NULL,
                    high_events_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            conn.commit()

    # ---------------- USER REPOSITORY METHODS ---------------- #

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def insert_user(self, email: str, password_hash: str, name: str, role: str, organization: str) -> bool:
        created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (email, password_hash, name, role, organization, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (email.lower().strip(), password_hash, name, role, organization, created_at))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def count_users(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    # ---------------- THERMAL SOURCE REPOSITORY METHODS ---------------- #

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM thermal_sources WHERE source_id = ?", (source_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def list_all_sources(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM thermal_sources ORDER BY source_id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def count_sources(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM thermal_sources")
            return cursor.fetchone()[0]

    def upsert_source(self, s: Dict[str, Any]):
        created_at = s.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO thermal_sources (
                    source_id, state, latitude, longitude, event_type, predicted_event_type,
                    confidence, confidence_pct, persistence_score, sih_alert_severity,
                    total_detections, active_days, observation_span_days, mean_frp, max_frp,
                    mean_brightness, max_brightness, nearest_facility_name, nearest_facility_type,
                    min_distance_to_industry_km, nearest_refinery_km, nearest_powerplant_km,
                    nearest_mine_km, nearest_industrial_area_km, mean_industrial_facilities_1km,
                    mean_industrial_facilities_5km, landcover_class, first_detection, last_detection,
                    is_persistent, is_flare_anomaly, risk_level, risk_description, marker_color, created_at
                ) VALUES (
                    :source_id, :state, :latitude, :longitude, :event_type, :predicted_event_type,
                    :confidence, :confidence_pct, :persistence_score, :sih_alert_severity,
                    :total_detections, :active_days, :observation_span_days, :mean_frp, :max_frp,
                    :mean_brightness, :max_brightness, :nearest_facility_name, :nearest_facility_type,
                    :min_distance_to_industry_km, :nearest_refinery_km, :nearest_powerplant_km,
                    :nearest_mine_km, :nearest_industrial_area_km, :mean_industrial_facilities_1km,
                    :mean_industrial_facilities_5km, :landcover_class, :first_detection, :last_detection,
                    :is_persistent, :is_flare_anomaly, :risk_level, :risk_description, :marker_color, :created_at
                )
                ON CONFLICT(source_id) DO UPDATE SET
                    predicted_event_type = excluded.predicted_event_type,
                    confidence = excluded.confidence,
                    confidence_pct = excluded.confidence_pct,
                    persistence_score = excluded.persistence_score,
                    sih_alert_severity = excluded.sih_alert_severity,
                    total_detections = excluded.total_detections,
                    active_days = excluded.active_days,
                    mean_frp = excluded.mean_frp,
                    max_frp = excluded.max_frp,
                    is_persistent = excluded.is_persistent,
                    is_flare_anomaly = excluded.is_flare_anomaly,
                    risk_level = excluded.risk_level,
                    risk_description = excluded.risk_description,
                    last_detection = excluded.last_detection
            """, {
                "source_id": s["source_id"],
                "state": s.get("state", "Odisha"),
                "latitude": float(s["latitude"]),
                "longitude": float(s["longitude"]),
                "event_type": s.get("event_type", "Other"),
                "predicted_event_type": s.get("predicted_event_type", s.get("event_type", "Other")),
                "confidence": float(s.get("confidence", s.get("confidence_pct", 80.0))),
                "confidence_pct": float(s.get("confidence_pct", s.get("confidence", 80.0))),
                "persistence_score": float(s.get("persistence_score", 50.0)),
                "sih_alert_severity": s.get("sih_alert_severity", "MEDIUM"),
                "total_detections": int(s.get("total_detections", 1)),
                "active_days": int(s.get("active_days", 1)),
                "observation_span_days": int(s.get("observation_span_days", 7)),
                "mean_frp": float(s.get("mean_frp", 5.0)),
                "max_frp": float(s.get("max_frp", s.get("mean_frp", 5.0))),
                "mean_brightness": float(s.get("mean_brightness", 330.0)),
                "max_brightness": float(s.get("max_brightness", s.get("mean_brightness", 330.0))),
                "nearest_facility_name": s.get("nearest_facility_name", "Industrial Complex"),
                "nearest_facility_type": s.get("nearest_facility_type", "industrial_area"),
                "min_distance_to_industry_km": float(s.get("min_distance_to_industry_km", 20.0)),
                "nearest_refinery_km": float(s.get("nearest_refinery_km", 50.0)),
                "nearest_powerplant_km": float(s.get("nearest_powerplant_km", 50.0)),
                "nearest_mine_km": float(s.get("nearest_mine_km", 50.0)),
                "nearest_industrial_area_km": float(s.get("nearest_industrial_area_km", 50.0)),
                "mean_industrial_facilities_1km": int(s.get("mean_industrial_facilities_1km", 0)),
                "mean_industrial_facilities_5km": int(s.get("mean_industrial_facilities_5km", 0)),
                "landcover_class": s.get("landcover_class", "Built-up"),
                "first_detection": s.get("first_detection", time.strftime("%Y-%m-%d %H:%M:%S")),
                "last_detection": s.get("last_detection", time.strftime("%Y-%m-%d %H:%M:%S")),
                "is_persistent": 1 if s.get("is_persistent") else 0,
                "is_flare_anomaly": 1 if s.get("is_flare_anomaly") else 0,
                "risk_level": s.get("risk_level", "Medium"),
                "risk_description": s.get("risk_description", ""),
                "marker_color": s.get("marker_color", "#457b9d"),
                "created_at": created_at
            })
            conn.commit()

    def bulk_insert_sources(self, sources_list: List[Dict[str, Any]]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for s in sources_list:
                created_at = s.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT OR IGNORE INTO thermal_sources (
                        source_id, state, latitude, longitude, event_type, predicted_event_type,
                        confidence, confidence_pct, persistence_score, sih_alert_severity,
                        total_detections, active_days, observation_span_days, mean_frp, max_frp,
                        mean_brightness, max_brightness, nearest_facility_name, nearest_facility_type,
                        min_distance_to_industry_km, nearest_refinery_km, nearest_powerplant_km,
                        nearest_mine_km, nearest_industrial_area_km, mean_industrial_facilities_1km,
                        mean_industrial_facilities_5km, landcover_class, first_detection, last_detection,
                        is_persistent, is_flare_anomaly, risk_level, risk_description, marker_color, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s["source_id"], s.get("state", "Odisha"), float(s["latitude"]), float(s["longitude"]),
                    s.get("event_type", "Other"), s.get("predicted_event_type", s.get("event_type", "Other")),
                    float(s.get("confidence", s.get("confidence_pct", 80.0))),
                    float(s.get("confidence_pct", s.get("confidence", 80.0))),
                    float(s.get("persistence_score", 50.0)), s.get("sih_alert_severity", "MEDIUM"),
                    int(s.get("total_detections", 1)), int(s.get("active_days", 1)),
                    int(s.get("observation_span_days", 7)), float(s.get("mean_frp", 5.0)),
                    float(s.get("max_frp", s.get("mean_frp", 5.0))), float(s.get("mean_brightness", 330.0)),
                    float(s.get("max_brightness", s.get("mean_brightness", 330.0))),
                    s.get("nearest_facility_name", "Industrial Complex"), s.get("nearest_facility_type", "industrial_area"),
                    float(s.get("min_distance_to_industry_km", 20.0)), float(s.get("nearest_refinery_km", 50.0)),
                    float(s.get("nearest_powerplant_km", 50.0)), float(s.get("nearest_mine_km", 50.0)),
                    float(s.get("nearest_industrial_area_km", 50.0)), int(s.get("mean_industrial_facilities_1km", 0)),
                    int(s.get("mean_industrial_facilities_5km", 0)), s.get("landcover_class", "Built-up"),
                    s.get("first_detection", time.strftime("%Y-%m-%d %H:%M:%S")),
                    s.get("last_detection", time.strftime("%Y-%m-%d %H:%M:%S")),
                    1 if s.get("is_persistent") else 0, 1 if s.get("is_flare_anomaly") else 0,
                    s.get("risk_level", "Medium"), s.get("risk_description", ""),
                    s.get("marker_color", "#457b9d"), created_at
                ))
            conn.commit()

    def delete_source(self, source_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM thermal_sources WHERE source_id = ?", (source_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_dispatch(self, dispatch_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dispatched_alerts WHERE dispatch_id = ?", (dispatch_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ---------------- DISPATCHED ALERTS REPOSITORY METHODS ---------------- #

    def insert_dispatch(self, record: Dict[str, Any]):
        created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dispatched_alerts (
                    dispatch_id, timestamp, target_agency, jurisdiction, summary,
                    dispatched_by, critical_events_count, high_events_count,
                    status, priority, recommended_action, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["dispatch_id"], record["timestamp"], record["target_agency"],
                record["jurisdiction"], record["summary"], record["dispatched_by"],
                record["critical_events_count"], record["high_events_count"],
                record["status"], record["priority"], record["recommended_action"],
                created_at
            ))
            conn.commit()

    def list_dispatches(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dispatched_alerts ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def count_dispatches(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM dispatched_alerts")
            return cursor.fetchone()[0]

db_manager = DatabaseManager()
