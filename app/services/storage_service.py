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

STATES_LIST = ["Odisha", "Jharkhand", "Chhattisgarh", "Maharashtra", "Karnataka"]

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
            
            # State mapping matching frontend logic
            state_val = str(row.get("state", "")).strip()
            if not state_val or state_val == "nan" or state_val == "Unknown":
                state_val = STATES_LIST[idx % len(STATES_LIST)]

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