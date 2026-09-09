import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from app.core.spatial_engine import is_point_in_bbox, haversine_distance
from app.core.anomaly_detector import evaluate_thermal_risk
from app.services.osm_service import osm_service

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CSV_PATH = BASE_DIR / "data" / "predictions.csv"
if not os.path.exists(CSV_PATH):
    CSV_PATH = BASE_DIR / "data" / "event_classification_features.csv"

PERSISTENCE_CSV_PATH = BASE_DIR / "data" / "source_persistence_features.csv"

CATEGORY_COLOR_MAP = {
    "Industrial": "#e63946",
    "Forest/Natural": "#2a9d8f",
    "Agricultural": "#e76f51",
    "Other": "#457b9d"
}

ALL_INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal"
]

STATE_CENTROIDS = {
    "Andhra Pradesh": {"lat": 15.9129, "lng": 79.7400, "lat_min": 12.6, "lat_max": 19.9, "lng_min": 76.7, "lng_max": 84.8},
    "Arunachal Pradesh": {"lat": 28.2180, "lng": 94.7278, "lat_min": 26.6, "lat_max": 29.5, "lng_min": 91.5, "lng_max": 97.4},
    "Assam": {"lat": 26.2006, "lng": 92.9376, "lat_min": 24.1, "lat_max": 28.0, "lng_min": 89.7, "lng_max": 96.0},
    "Bihar": {"lat": 25.0961, "lng": 85.3131, "lat_min": 24.3, "lat_max": 27.5, "lng_min": 83.3, "lng_max": 88.3},
    "Chhattisgarh": {"lat": 21.2787, "lng": 81.8661, "lat_min": 17.8, "lat_max": 24.1, "lng_min": 80.2, "lng_max": 84.4},
    "Goa": {"lat": 15.2993, "lng": 74.1240, "lat_min": 14.9, "lat_max": 15.8, "lng_min": 73.6, "lng_max": 74.4},
    "Gujarat": {"lat": 22.2587, "lng": 71.1924, "lat_min": 20.1, "lat_max": 24.7, "lng_min": 68.1, "lng_max": 74.5},
    "Haryana": {"lat": 29.0588, "lng": 76.0856, "lat_min": 27.6, "lat_max": 30.9, "lng_min": 74.4, "lng_max": 77.6},
    "Himachal Pradesh": {"lat": 31.1048, "lng": 77.1734, "lat_min": 30.4, "lat_max": 33.2, "lng_min": 75.8, "lng_max": 79.0},
    "Jharkhand": {"lat": 23.6102, "lng": 85.2799, "lat_min": 21.9, "lat_max": 25.3, "lng_min": 83.3, "lng_max": 87.9},
    "Karnataka": {"lat": 15.3173, "lng": 75.7139, "lat_min": 11.5, "lat_max": 18.5, "lng_min": 74.0, "lng_max": 78.6},
    "Kerala": {"lat": 10.8505, "lng": 76.2711, "lat_min": 8.3, "lat_max": 12.8, "lng_min": 74.8, "lng_max": 77.4},
    "Madhya Pradesh": {"lat": 22.9734, "lng": 78.6569, "lat_min": 21.1, "lat_max": 26.9, "lng_min": 74.0, "lng_max": 82.8},
    "Maharashtra": {"lat": 19.7515, "lng": 75.7139, "lat_min": 15.6, "lat_max": 22.0, "lng_min": 72.6, "lng_max": 80.9},
    "Manipur": {"lat": 24.6637, "lng": 93.9063, "lat_min": 23.8, "lat_max": 25.7, "lng_min": 93.0, "lng_max": 94.8},
    "Meghalaya": {"lat": 25.4670, "lng": 91.3662, "lat_min": 25.0, "lat_max": 26.1, "lng_min": 89.8, "lng_max": 92.8},
    "Mizoram": {"lat": 23.1645, "lng": 92.9376, "lat_min": 21.9, "lat_max": 24.5, "lng_min": 92.2, "lng_max": 93.4},
    "Nagaland": {"lat": 26.1584, "lng": 94.5624, "lat_min": 25.2, "lat_max": 27.0, "lng_min": 93.3, "lng_max": 95.2},
    "Odisha": {"lat": 20.9517, "lng": 85.0985, "lat_min": 17.8, "lat_max": 22.6, "lng_min": 81.4, "lng_max": 87.5},
    "Punjab": {"lat": 31.1471, "lng": 75.3412, "lat_min": 29.5, "lat_max": 32.5, "lng_min": 73.9, "lng_max": 76.9},
    "Rajasthan": {"lat": 27.0238, "lng": 74.2179, "lat_min": 23.1, "lat_max": 30.2, "lng_min": 69.5, "lng_max": 78.3},
    "Sikkim": {"lat": 27.5330, "lng": 88.5122, "lat_min": 27.0, "lat_max": 28.1, "lng_min": 88.0, "lng_max": 88.9},
    "Tamil Nadu": {"lat": 11.1271, "lng": 78.6569, "lat_min": 8.1, "lat_max": 13.6, "lng_min": 76.2, "lng_max": 80.3},
    "Telangana": {"lat": 18.1124, "lng": 79.0193, "lat_min": 15.8, "lat_max": 19.9, "lng_min": 77.2, "lng_max": 81.8},
    "Tripura": {"lat": 23.9408, "lng": 91.9882, "lat_min": 22.9, "lat_max": 24.5, "lng_min": 91.1, "lng_max": 92.3},
    "Uttar Pradesh": {"lat": 26.8467, "lng": 80.9462, "lat_min": 23.9, "lat_max": 30.4, "lng_min": 77.1, "lng_max": 84.6},
    "Uttarakhand": {"lat": 30.0668, "lng": 79.0193, "lat_min": 28.7, "lat_max": 31.5, "lng_min": 77.6, "lng_max": 81.0},
    "West Bengal": {"lat": 22.9868, "lng": 87.8550, "lat_min": 21.5, "lat_max": 27.2, "lng_min": 85.8, "lng_max": 89.9}
}

STATES_LIST = ALL_INDIAN_STATES

def detect_state_for_coordinates(lat: float, lon: float) -> str:
    # Check bounding boxes first
    for s_name, bbox in STATE_CENTROIDS.items():
        if bbox["lat_min"] <= lat <= bbox["lat_max"] and bbox["lng_min"] <= lon <= bbox["lng_max"]:
            return s_name
    # Fallback to nearest centroid
    best_state = "Odisha"
    min_d = 999999.0
    for s_name, bbox in STATE_CENTROIDS.items():
        d = ((lat - bbox["lat"])**2 + (lon - bbox["lng"])**2)**0.5
        if d < min_d:
            min_d = d
            best_state = s_name
    return best_state

class ThermalStorageService:
    def __init__(self):
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.alerts: List[Dict[str, Any]] = []
        self._initialize_database()

    def _initialize_database(self):
        if not os.path.exists(CSV_PATH):
            print(f"Notice: CSV data file {CSV_PATH} not found yet.")
            return

        df = pd.read_csv(CSV_PATH)
        facilities = osm_service.get_all_facilities()
        
        # Load persistence records if available
        pers_map = {}
        if os.path.exists(PERSISTENCE_CSV_PATH):
            try:
                p_df = pd.read_csv(PERSISTENCE_CSV_PATH)
                for _, p_row in p_df.iterrows():
                    pers_map[str(p_row.get("source_id", "")).strip()] = p_row.to_dict()
            except Exception:
                pass
        
        for idx, row in df.iterrows():
            s_id = str(row.get("source_id", f"SOURCE_{idx + 1:04d}")).strip()
            lat = float(row.get("latitude", 0.0))
            lon = float(row.get("longitude", 0.0))
            event_type = str(row.get("event_type", "Other"))
            pred_event_type = str(row.get("predicted_event_type", event_type))
            
            mean_frp = float(row.get("mean_frp", 5.0) or 5.0)
            max_frp = float(row.get("max_frp", mean_frp) or mean_frp)
            mean_bright = float(row.get("mean_brightness", 330.0) or 330.0)
            max_bright = float(row.get("max_brightness", mean_bright) or mean_bright)
            
            active_days = int(row.get("active_days", 1) or 1)
            total_detections = int(row.get("total_detections", 1) or 1)
            obs_span = max(1, int(row.get("observation_span_days", 7) or 7))
            min_dist_ind = float(row.get("min_distance_to_industry_km", 20.0) or 20.0)
            conf_pct = float(row.get("confidence_pct", 85.0) or 85.0)
            
            # State mapping based on geographic coordinates across 28 Indian states
            state_val = str(row.get("state", "")).strip()
            if not state_val or state_val == "nan" or state_val == "Unknown":
                state_val = detect_state_for_coordinates(lat, lon)

            # Calculate persistence score between 0 and 100%
            pers_record = pers_map.get(s_id, {})
            if "persistence_score" in pers_record:
                raw_p = float(pers_record["persistence_score"])
                pers_score = round(raw_p * 100, 1) if raw_p <= 1.0 else round(raw_p, 1)
            else:
                pers_score = min(100.0, round((active_days / obs_span) * 100, 1))

            risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
                pred_event_type, min_dist_ind, mean_frp, max_frp, active_days, total_detections
            )

            # SIH Alert Rule matching frontend ALERT_RULES: CRITICAL >= 88, HIGH >= 75, MEDIUM >= 60
            if conf_pct >= 88.0:
                sih_alert = "CRITICAL"
            elif conf_pct >= 75.0:
                sih_alert = "HIGH"
            elif conf_pct >= 60.0:
                sih_alert = "MEDIUM"
            else:
                sih_alert = "LOW"
            
            nearest_fac_name = "Industrial Complex"
            for fac in facilities:
                if haversine_distance(lat, lon, fac["latitude"], fac["longitude"]) <= min_dist_ind + 0.5:
                    nearest_fac_name = fac["name"]
                    break

            source_obj = {
                "source_id": s_id,
                "state": state_val,
                "latitude": lat,
                "longitude": lon,
                "event_type": event_type,
                "predicted_event_type": pred_event_type,
                "confidence": conf_pct,
                "confidence_pct": conf_pct,
                "persistence_score": pers_score,
                "sih_alert_severity": sih_alert,
                "total_detections": total_detections,
                "active_days": active_days,
                "observation_span_days": obs_span,
                "mean_frp": round(mean_frp, 2),
                "max_frp": round(max_frp, 2),
                "mean_brightness": round(mean_bright, 2),
                "max_brightness": round(max_bright, 2),
                "nearest_facility_type": str(row.get("nearest_facility_type", "industrial_area")),
                "nearest_facility_name": nearest_fac_name,
                "min_distance_to_industry_km": round(min_dist_ind, 2),
                "nearest_refinery_km": round(float(row.get("nearest_refinery_km", 50.0) or 50.0), 2),
                "nearest_powerplant_km": round(float(row.get("nearest_powerplant_km", 50.0) or 50.0), 2),
                "nearest_mine_km": round(float(row.get("nearest_mine_km", 50.0) or 50.0), 2),
                "nearest_industrial_area_km": round(float(row.get("nearest_industrial_area_km", 50.0) or 50.0), 2),
                "mean_industrial_facilities_1km": int(row.get("mean_industrial_facilities_1km", 0) or 0),
                "mean_industrial_facilities_5km": int(row.get("mean_industrial_facilities_5km", 0) or 0),
                "landcover_class": str(row.get("landcover_class", "Built-up")),
                "first_detection": str(row.get("first_detection", "2026-08-19 00:00:00+00:00")),
                "last_detection": str(row.get("last_detection", "2026-08-25 00:00:00+00:00")),
                "is_persistent": active_days >= 3 or total_detections >= 5,
                "is_flare_anomaly": is_flare_anomaly,
                "risk_level": risk_level,
                "risk_description": risk_desc,
                "marker_color": CATEGORY_COLOR_MAP.get(pred_event_type, "#457b9d")
            }
            
            self.sources[s_id] = source_obj
            
            if sih_alert in ["CRITICAL", "HIGH", "MEDIUM"]:
                self.alerts.append({
                    "alert_id": f"ALERT_{len(self.alerts) + 1:04d}",
                    "source_id": s_id,
                    "state": state_val,
                    "timestamp": source_obj["last_detection"],
                    "latitude": lat,
                    "longitude": lon,
                    "event_type": pred_event_type,
                    "confidence": conf_pct,
                    "confidence_pct": conf_pct,
                    "persistence_score": pers_score,
                    "severity": sih_alert,
                    "title": f"{sih_alert} Alert: {pred_event_type} Anomaly in {state_val} ({nearest_fac_name})",
                    "message": risk_desc,
                    "facility_context": f"{source_obj['nearest_facility_type'].title()} ({min_dist_ind:.2f} km away), FRP: {max_frp:.1f} MW"
                })

        print(f"[OK] In-Memory GIS Storage ready: {len(self.sources)} thermal sources loaded, {len(self.alerts)} active alerts.")

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self.sources.get(source_id)

    def list_sources(
        self,
        state: Optional[str] = None,
        event_type: Optional[str] = None,
        min_frp: Optional[float] = None,
        is_persistent: Optional[bool] = None,
        risk_level: Optional[str] = None,
        min_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lat: Optional[float] = None,
        max_lon: Optional[float] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        results = []
        for s in self.sources.values():
            if state and state.upper() != "ALL" and s["state"].lower() != state.lower():
                continue
            if event_type and event_type.upper() != "ALL" and s["predicted_event_type"].lower() != event_type.lower():
                continue
            if min_frp is not None and s["max_frp"] < min_frp:
                continue
            if is_persistent is not None and s["is_persistent"] != is_persistent:
                continue
            if risk_level and s["risk_level"].lower() != risk_level.lower():
                continue
            if None not in (min_lat, min_lon, max_lat, max_lon):
                if not is_point_in_bbox(s["latitude"], s["longitude"], min_lat, min_lon, max_lat, max_lon):
                    continue
            results.append(s)
            if len(results) >= limit:
                break
        return results

    def get_geojson(
        self,
        state: Optional[str] = None,
        event_type: Optional[str] = None,
        min_frp: Optional[float] = None,
        is_persistent: Optional[bool] = None,
        risk_level: Optional[str] = None,
        min_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lat: Optional[float] = None,
        max_lon: Optional[float] = None
    ) -> Dict[str, Any]:
        filtered = self.list_sources(
            state=state,
            event_type=event_type,
            min_frp=min_frp,
            is_persistent=is_persistent,
            risk_level=risk_level,
            min_lat=min_lat,
            min_lon=min_lon,
            max_lat=max_lat,
            max_lon=max_lon,
            limit=5000
        )

        features = []
        for s in filtered:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [s["longitude"], s["latitude"]]
                },
                "properties": {
                    "source_id": s["source_id"],
                    "state": s["state"],
                    "event_type": s["event_type"],
                    "predicted_event_type": s["predicted_event_type"],
                    "confidence": s["confidence_pct"],
                    "confidence_pct": s["confidence_pct"],
                    "persistence_score": s["persistence_score"],
                    "sih_alert_severity": s["sih_alert_severity"],
                    "mean_frp": s["mean_frp"],
                    "max_frp": s["max_frp"],
                    "mean_brightness": s["mean_brightness"],
                    "max_brightness": s["max_brightness"],
                    "active_days": s["active_days"],
                    "total_detections": s["total_detections"],
                    "is_persistent": s["is_persistent"],
                    "is_flare_anomaly": s["is_flare_anomaly"],
                    "risk_level": s["risk_level"],
                    "risk_description": s["risk_description"],
                    "nearest_facility_name": s["nearest_facility_name"],
                    "nearest_facility_type": s["nearest_facility_type"],
                    "min_distance_to_industry_km": s["min_distance_to_industry_km"],
                    "landcover_class": s["landcover_class"],
                    "marker_color": s["marker_color"],
                    "marker_radius": max(5, min(20, int(s["mean_frp"] * 1.5)))
                }
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def get_analytics_summary(self, state: Optional[str] = None) -> Dict[str, Any]:
        sources = self.list_sources(state=state, limit=10000)
        total = len(sources)
        if total == 0:
            return {
                "total_thermal_sources": 0, "industrial_sources": 0, "forest_natural_sources": 0,
                "agricultural_sources": 0, "other_sources": 0, "active_alerts": 0
            }

        counts = defaultdict(int)
        persistent_count = 0
        critical_count = 0
        high_count = 0

        for s in sources:
            cat = s["predicted_event_type"]
            counts[cat] += 1
            if s["is_persistent"]:
                persistent_count += 1
            if s["sih_alert_severity"] == "CRITICAL":
                critical_count += 1
            elif s["sih_alert_severity"] == "HIGH":
                high_count += 1

        return {
            "total_thermal_sources": total,
            "state_jurisdiction": state or "National",
            "industrial_sources": counts["Industrial"],
            "forest_natural_sources": counts["Forest/Natural"],
            "agricultural_sources": counts["Agricultural"],
            "other_sources": counts["Other"],
            "persistent_sources_count": persistent_count,
            "critical_alerts_count": critical_count,
            "high_alerts_count": high_count,
            "total_alerts": critical_count + high_count
        }

    def get_alerts(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        if not state or state.upper() == "ALL":
            return self.alerts
        return [a for a in self.alerts if a.get("state", "").lower() == state.lower()]

    def save_new_source(self, source_obj: Dict[str, Any]) -> str:
        s_id = source_obj.get("source_id") or f"SOURCE_{len(self.sources) + 1:04d}"
        source_obj["source_id"] = s_id
        source_obj["marker_color"] = CATEGORY_COLOR_MAP.get(source_obj.get("predicted_event_type", "Other"), "#457b9d")
        if "state" not in source_obj or not source_obj["state"]:
            source_obj["state"] = "Odisha"
        self.sources[s_id] = source_obj
        return s_id

storage_service = ThermalStorageService()