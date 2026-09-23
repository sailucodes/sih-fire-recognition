import json
import csv
import io
from typing import Dict, Any, List, Tuple
from urllib.parse import parse_qs, urlparse

from app.services.storage_service import storage_service, detect_state_for_coordinates
from app.services.osm_service import osm_service
from app.services.firms_service import firms_service
from app.services.auth_service import auth_service
from app.services.language_service import language_service
from app.services.voice_service import voice_service
from app.services.alert_dispatcher_service import alert_dispatcher_service
from app.db.database import db_manager

from app.core.feature_engineering import extract_features_for_point
from app.core.ml_model import ml_engine
from app.core.anomaly_detector import evaluate_thermal_risk
from app.core.clustering import cluster_firms_hotspots
from app.core.spatial_engine import deduce_indian_state

class APIRouter:
    def handle_request(self, method: str, path: str, query_params: Dict[str, List[str]], body_data: bytes) -> Tuple[int, Dict[str, str], bytes]:
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        }

        if method == "OPTIONS":
            return 204, headers, b""

        parsed_path = path.rstrip("/")

        try:
            # 1. Health Check
            if parsed_path == "/api/v1/health" and method == "GET":
                return self._handle_health(headers)

            # 2. Authentication Endpoints
            elif parsed_path == "/api/v1/auth/register" and method == "POST":
                return self._handle_auth_register(body_data, headers)

            elif parsed_path == "/api/v1/auth/login" and method == "POST":
                return self._handle_auth_login(body_data, headers)

            elif parsed_path == "/api/v1/auth/google" and method == "POST":
                return self._handle_auth_google(body_data, headers)

            elif parsed_path == "/api/v1/auth/me" and method == "GET":
                return self._handle_auth_me(query_params, headers)

            # 3. Multilingual & Translation Endpoints
            elif parsed_path == "/api/v1/languages" and method == "GET":
                return 200, headers, json.dumps(language_service.get_supported_languages(), indent=2).encode("utf-8")

            elif (parsed_path.startswith("/api/v1/translations") or parsed_path == "/translations") and method == "GET":
                lang = parsed_path.split("/")[-1] if "/" in parsed_path and not parsed_path.endswith("translations") else query_params.get("lang", ["en-US"])[0]
                return 200, headers, json.dumps(language_service.get_translations(lang), indent=2).encode("utf-8")

            # 4. Voice Control & Speech NLP Command Endpoint
            elif parsed_path in ["/api/v1/voice/command", "/voice/command"] and method == "POST":
                return self._handle_voice_command(body_data, headers)

            # 5. National Authority Alert Dispatcher
            elif parsed_path in ["/api/v1/alerts/dispatch", "/alerts/dispatch"] and method == "POST":
                return self._handle_alert_dispatch(body_data, headers)

            elif parsed_path in ["/api/v1/alerts/dispatched", "/alerts/dispatched"] and method == "GET":
                return 200, headers, json.dumps({"count": len(alert_dispatcher_service.dispatches), "dispatches": alert_dispatcher_service.list_dispatches()}, indent=2).encode("utf-8")

            # 6. Thermal Sources Listing (JSON)
            elif parsed_path in ["/api/v1/sources", "/sources"] and method == "GET":
                return self._handle_list_sources(query_params, headers)

            # 7. Direct GeoJSON Map Overlay
            elif parsed_path in ["/api/v1/sources/geojson", "/geojson"] and method == "GET":
                return self._handle_sources_geojson(query_params, headers)

            # 8. Single Thermal Source Detail & Deletion
            elif parsed_path.startswith("/api/v1/sources/") and method == "GET":
                source_id = parsed_path.split("/")[-1]
                return self._handle_source_detail(source_id, headers)

            elif parsed_path.startswith("/api/v1/sources/") and method == "DELETE":
                source_id = parsed_path.split("/")[-1]
                success = storage_service.delete_source(source_id)
                return 200, headers, json.dumps({
                    "success": success,
                    "source_id": source_id,
                    "message": f"Thermal source {source_id} permanently deleted from database & map."
                }).encode("utf-8")

            # 9. Live Prediction Endpoint (Supports GET & POST for /predict)
            elif parsed_path in ["/predict", "/api/v1/predict", "/api/v1/classify"] and method in ["GET", "POST"]:
                return self._handle_predict_single(method, query_params, body_data, headers)

            # 10. OSM Industrial Infrastructure
            elif parsed_path in ["/api/v1/infrastructure", "/infrastructure"] and method == "GET":
                data = osm_service.get_all_facilities()
                return 200, headers, json.dumps({"count": len(data), "facilities": data}).encode("utf-8")

            elif parsed_path in ["/api/v1/infrastructure/geojson", "/infrastructure/geojson"] and method == "GET":
                geojson = osm_service.get_geojson()
                return 200, headers, json.dumps(geojson).encode("utf-8")

            # 11. Analytics & KPI Summary
            elif parsed_path in ["/api/v1/analytics/summary", "/analytics"] and method == "GET":
                state = query_params.get("state", [None])[0]
                stats = storage_service.get_analytics_summary(state=state)
                return 200, headers, json.dumps(stats).encode("utf-8")

            # 12. Risk Alerts Listing & Dismissal
            elif parsed_path in ["/api/v1/alerts", "/alerts"] and method == "GET":
                state = query_params.get("state", [None])[0]
                alerts = storage_service.get_alerts(state=state)
                return 200, headers, json.dumps({"count": len(alerts), "alerts": alerts}).encode("utf-8")

            elif parsed_path.startswith("/api/v1/alerts/") and method == "DELETE":
                alert_id = parsed_path.split("/")[-1]
                success = storage_service.delete_alert(alert_id)
                return 200, headers, json.dumps({
                    "success": success,
                    "alert_id": alert_id,
                    "message": f"Alert {alert_id} dismissed."
                }).encode("utf-8")

            elif parsed_path in ["/api/v1/alerts", "/alerts"] and method == "DELETE":
                cleared_count = storage_service.clear_all_alerts()
                return 200, headers, json.dumps({
                    "success": True,
                    "cleared_count": cleared_count,
                    "message": f"Successfully cleared all {cleared_count} alerts."
                }).encode("utf-8")

            # 13. Dual CSV Streaming Endpoints (For frontend loadDualCsvData)
            elif parsed_path in ["/event_classification_features.csv", "/data/event_classification_features.csv"] and method == "GET":
                return self._handle_serve_csv("event_classification_features.csv", headers)

            elif parsed_path in ["/source_persistence_features.csv", "/data/source_persistence_features.csv"] and method == "GET":
                return self._handle_serve_csv("source_persistence_features.csv", headers)

            elif parsed_path in ["/predictions.csv", "/api/v1/export/report"] and method == "GET":
                return self._handle_serve_csv("predictions.csv", headers)

            # 14. NASA FIRMS Sync
            elif parsed_path in ["/api/v1/firms/sync", "/firms/sync"] and method in ["GET", "POST"]:
                return self._handle_firms_sync(query_params, headers)

            # 15. OpenAPI Specification
            elif parsed_path == "/api/v1/openapi.json" and method == "GET":
                return self._handle_openapi(headers)

            else:
                return 404, headers, json.dumps({"error": "Endpoint not found", "path": path}).encode("utf-8")

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[ROUTER ERROR] {tb}", flush=True)
            return 500, headers, json.dumps({"error": str(e), "traceback": tb}).encode("utf-8")

    # ---------------- HANDLERS ---------------- #

    def _handle_health(self, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        data = {
            "status": "healthy",
            "system": "AI-Based Industrial Fire & Persistent Thermal Source Detection System",
            "version": "2.0.0",
            "database_engine": "SQLite 3 (thermal_intel.db)",
            "database_path": str(db_manager.db_path),
            "model_status": "loaded" if ml_engine.model is not None else "ready",
            "model_classes": ml_engine.classes_,
            "total_thermal_sources_indexed": len(storage_service.sources),
            "sqlite_thermal_sources_count": db_manager.count_sources(),
            "sqlite_users_count": db_manager.count_users(),
            "osm_facilities_indexed": len(osm_service.facilities),
            "active_alerts_count": len(storage_service.alerts),
            "dispatched_national_briefs": len(alert_dispatcher_service.dispatches),
            "supported_languages": list(language_service.get_supported_languages()["languages"].keys())
        }
        return 200, headers, json.dumps(data, indent=2).encode("utf-8")

    def _handle_auth_register(self, body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        try:
            body = json.loads(body_data.decode("utf-8")) if body_data else {}
        except Exception:
            return 400, headers, json.dumps({"error": "Invalid JSON body"}).encode("utf-8")

        res = auth_service.register(
            email=body.get("email", ""),
            password=body.get("password", ""),
            name=body.get("name", ""),
            role=body.get("role", "State Emergency Analyst"),
            organization=body.get("organization", "State EOC")
        )
        status_code = 200 if res.get("success") else 400
        return status_code, headers, json.dumps(res, indent=2).encode("utf-8")

    def _handle_auth_login(self, body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        try:
            body = json.loads(body_data.decode("utf-8")) if body_data else {}
        except Exception:
            return 400, headers, json.dumps({"error": "Invalid JSON body"}).encode("utf-8")

        res = auth_service.login(
            email=body.get("email", ""),
            password=body.get("password", "")
        )
        status_code = 200 if res.get("success") else 401
        return status_code, headers, json.dumps(res, indent=2).encode("utf-8")

    def _handle_auth_google(self, body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        try:
            body = json.loads(body_data.decode("utf-8")) if body_data else {}
        except Exception:
            body = {}

        res = auth_service.google_auth(
            google_token=body.get("token"),
            email=body.get("email"),
            name=body.get("name")
        )
        return 200, headers, json.dumps(res, indent=2).encode("utf-8")

    def _handle_auth_me(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        token = query_params.get("token", [""])[0]
        user = auth_service.verify_token(token)
        if not user:
            return 401, headers, json.dumps({"error": "Invalid or expired session token"}).encode("utf-8")
        return 200, headers, json.dumps({"authenticated": True, "user": user}, indent=2).encode("utf-8")

    def _handle_voice_command(self, body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        try:
            body = json.loads(body_data.decode("utf-8")) if body_data else {}
        except Exception:
            return 400, headers, json.dumps({"error": "Invalid JSON payload"}).encode("utf-8")

        transcript = body.get("command") or body.get("transcript") or ""
        lang = body.get("language") or body.get("lang") or "en-US"

        res = voice_service.process_voice_command(transcript, lang)
        return 200, headers, json.dumps(res, indent=2).encode("utf-8")

    def _handle_alert_dispatch(self, body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        try:
            body = json.loads(body_data.decode("utf-8")) if body_data else {}
        except Exception:
            body = {}

        state = body.get("state") or "National"
        critical_count = int(body.get("critical_count") or len([a for a in storage_service.alerts if a.get("severity") == "CRITICAL"]))
        high_count = int(body.get("high_count") or len([a for a in storage_service.alerts if a.get("severity") == "HIGH"]))
        officer = body.get("officer_email") or "officer.ndma@gov.in"

        res = alert_dispatcher_service.dispatch_brief(
            state=state,
            critical_count=critical_count,
            high_count=high_count,
            officer_email=officer
        )
        return 200, headers, json.dumps(res, indent=2).encode("utf-8")

    def _handle_serve_csv(self, filename: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        data_dir = storage_service.sources
        file_path = storage_service.__dict__.get("BASE_DIR", "")
        
        import os
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        target = root / "data" / filename
        if not target.exists():
            target = root / "app" / "static" / filename

        if target.exists():
            with open(target, "rb") as f:
                content = f.read()
            csv_headers = {
                "Content-Type": "text/csv",
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Allow-Origin": "*"
            }
            return 200, csv_headers, content
        return 404, headers, json.dumps({"error": f"File {filename} not found"}).encode("utf-8")

    def _handle_list_sources(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        state = query_params.get("state", [None])[0]
        event_type = query_params.get("event_type", [None])[0]
        min_frp = float(query_params.get("min_frp", [0])[0]) if "min_frp" in query_params else None
        is_persistent = (query_params.get("is_persistent", [""])[0].lower() == "true") if "is_persistent" in query_params else None
        risk_level = query_params.get("risk_level", [None])[0]
        limit = int(query_params.get("limit", [1000])[0])

        sources = storage_service.list_sources(
            state=state,
            event_type=event_type,
            min_frp=min_frp,
            is_persistent=is_persistent,
            risk_level=risk_level,
            limit=limit
        )
        return 200, headers, json.dumps({"count": len(sources), "sources": sources}).encode("utf-8")

    def _handle_sources_geojson(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        state = query_params.get("state", [None])[0]
        event_type = query_params.get("event_type", [None])[0]
        min_frp = float(query_params.get("min_frp", [0])[0]) if "min_frp" in query_params else None
        is_persistent = (query_params.get("is_persistent", [""])[0].lower() == "true") if "is_persistent" in query_params else None
        risk_level = query_params.get("risk_level", [None])[0]

        geojson = storage_service.get_geojson(
            state=state,
            event_type=event_type,
            min_frp=min_frp,
            is_persistent=is_persistent,
            risk_level=risk_level
        )
        return 200, headers, json.dumps(geojson).encode("utf-8")

    def _handle_source_detail(self, source_id: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        source = storage_service.get_source(source_id)
        if not source:
            return 404, headers, json.dumps({"error": f"Thermal source {source_id} not found"}).encode("utf-8")
        return 200, headers, json.dumps(source, indent=2).encode("utf-8")

    def _handle_predict_single(self, method: str, query_params: Dict[str, List[str]], body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        body = {}
        if method == "POST" and body_data:
            try:
                body = json.loads(body_data.decode("utf-8"))
            except Exception:
                pass

        lat = float(body.get("latitude") or body.get("lat") or query_params.get("latitude", [query_params.get("lat", [29.46148])[0]])[0])
        lon = float(body.get("longitude") or body.get("lon") or query_params.get("longitude", [query_params.get("lon", [76.86364])[0]])[0])
        mean_frp = float(body.get("mean_frp") or body.get("frp") or query_params.get("mean_frp", [query_params.get("frp", [25.0])[0]])[0])
        max_frp = float(body.get("max_frp") or mean_frp)
        mean_bright = float(body.get("mean_brightness") or body.get("brightness") or 330.0)
        max_bright = float(body.get("max_brightness") or mean_bright)
        
        detection_count = int(body.get("total_detections") or body.get("detection_count") or 1)
        active_days = int(body.get("active_days") or 1)
        obs_span = max(1, int(body.get("observation_span") or body.get("observation_span_days") or 1))
        
        # Calculate persistence score between 0 and 100%
        if body.get("persistence_score") is not None:
            calculated_persistence = float(body.get("persistence_score"))
        elif active_days > 1 or obs_span > 1:
            calculated_persistence = min(100.0, round((active_days / obs_span) * 100, 1))
        else:
            # Scaled persistence based on thermal intensity and recurrence
            calculated_persistence = min(96.0, round(85.0 + min(11.0, (mean_frp - 15) * 0.4), 1)) if mean_frp >= 15 else round(70.0 + mean_frp * 0.5, 1)

        # Accurately deduce state jurisdiction from geospatial coordinates
        provided_state = body.get("state") or query_params.get("state", [None])[0]
        if not provided_state or provided_state in ["", "Select State / UT", "National", "Unknown"]:
            state_val = deduce_indian_state(lat, lon)
        else:
            state_val = provided_state

        fac_type = body.get("facility_type") or body.get("nearest_facility_type")
        if fac_type and fac_type.lower() != "none":
            fac_type = fac_type.lower().replace(" ", "_")
        else:
            fac_type = None
            
        dist_industry = body.get("distance_industry") or body.get("distance_to_nearest_industry") or body.get("min_distance_to_industry_km")
        dist_industry = float(dist_industry) if dist_industry is not None else None

        fac_1km = body.get("industrial_facilities_1km") or body.get("facilities_1km")
        fac_1km = int(fac_1km) if fac_1km is not None else None

        fac_5km = body.get("industrial_facilities_5km") or body.get("facilities_5km")
        fac_5km = int(fac_5km) if fac_5km is not None else None

        landcover_class = body.get("landcover_class") or body.get("landcover")

        facilities = osm_service.get_all_facilities()
        
        features = extract_features_for_point(
            lat=lat, lon=lon, frp=mean_frp, max_frp=max_frp,
            brightness=mean_bright, max_brightness=max_bright,
            detection_count=detection_count, active_days=active_days,
            facilities=facilities, landcover_class=landcover_class,
            observation_span_days=obs_span,
            override_nearest_type=fac_type,
            override_min_dist=dist_industry,
            facilities_1km=fac_1km,
            facilities_5km=fac_5km
        )

        pred_res = ml_engine.predict_single(features)
        conf = pred_res["confidence_pct"]
        pred_type = pred_res["predicted_event_type"]

        # Alert rules matching updated frontend: CRITICAL >= 88, HIGH >= 75
        if pred_type == "Industrial" and conf >= 88.0:
            sih_alert_severity = "CRITICAL"
        elif pred_type == "Industrial" and conf >= 75.0:
            sih_alert_severity = "HIGH"
        elif pred_type == "Industrial" and conf >= 60.0:
            sih_alert_severity = "MEDIUM"
        else:
            sih_alert_severity = "LOW"

        risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
            pred_type, features["min_distance_to_industry_km"],
            mean_frp, max_frp, active_days, detection_count
        )

        response = {
            "source_id": body.get("source_id", f"PRED_{int(lat*1000)}_{int(lon*1000)}"),
            "state": state_val,
            "latitude": lat,
            "longitude": lon,
            "event_type": pred_type,
            "predicted_event_type": pred_type,
            "confidence": conf,
            "confidence_pct": conf,
            "persistence_score": calculated_persistence,
            "probabilities": pred_res["probabilities"],
            "probability_industrial": pred_res["probabilities"].get("Industrial", 0.0),
            "probability_forest_natural": pred_res["probabilities"].get("Forest/Natural", 0.0),
            "probability_agricultural": pred_res["probabilities"].get("Agricultural", 0.0),
            "probability_other": pred_res["probabilities"].get("Other", 0.0),
            "sih_alert_severity": sih_alert_severity,
            "is_persistent": active_days >= 3 or detection_count >= 5,
            "is_persistent_thermal_source": active_days >= 3 or detection_count >= 5,
            "is_flare_anomaly": is_flare_anomaly,
            "risk_level": risk_level,
            "risk_description": risk_desc,
            "nearest_facility_type": features["nearest_facility_type"],
            "nearest_facility_name": features["nearest_facility_name"],
            "nearest_facility_distance_km": features["min_distance_to_industry_km"],
            "landcover_class": features["landcover_class"],
            "features_summary": {
                "nearest_refinery_km": features["nearest_refinery_km"],
                "nearest_powerplant_km": features["nearest_powerplant_km"],
                "nearest_mine_km": features["nearest_mine_km"],
                "nearest_industrial_area_km": features["nearest_industrial_area_km"],
                "industrial_facilities_within_5km": features["mean_industrial_facilities_5km"]
            },
            "mean_frp": round(mean_frp, 2),
            "max_frp": round(max_frp, 2),
            "mean_brightness": round(mean_bright, 2),
            "max_brightness": round(max_bright, 2),
            "active_days": active_days,
            "total_detections": detection_count,
            "observation_span_days": obs_span,
            "min_distance_to_industry_km": features["min_distance_to_industry_km"],
            "explanation": pred_res["explanation"]
        }

        # Persist verified prediction into SQLite and in-memory storage
        storage_service.save_new_source(response)

        return 200, headers, json.dumps(response, indent=2).encode("utf-8")

    def _handle_firms_sync(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        country = query_params.get("country", ["IND"])[0]
        days = int(query_params.get("days", [1])[0])
        api_key = query_params.get("key", [None])[0] or query_params.get("map_key", [None])[0]

        import time
        t0 = time.time()
        try:
            raw_hotspots = firms_service.fetch_live_hotspots(country_code=country, days=days, api_key=api_key)
        except Exception as e:
            return 400, headers, json.dumps({
                "status": "error",
                "error": str(e),
                "message": "NASA FIRMS live synchronization could not proceed.",
                "hint": "Set NASA_FIRMS_MAP_KEY environment variable or provide a valid MAP_KEY from https://firms.modaps.eosdis.nasa.gov/api/map_key/"
            }, indent=2).encode("utf-8")
        t_fetch = time.time() - t0

        t1 = time.time()
        clustered_sources = cluster_firms_hotspots(raw_hotspots, eps_km=1.5)
        t_cluster = time.time() - t1

        facilities = osm_service.get_all_facilities()
        synced_sources = []

        t2 = time.time()
        features_list = []
        for idx, c in enumerate(clustered_sources, start=1):
            c["source_id"] = f"LIVE_FIRMS_{idx:04d}"
            c["state"] = detect_state_for_coordinates(c["latitude"], c["longitude"])
            features = extract_features_for_point(
                lat=c["latitude"], lon=c["longitude"], frp=c["mean_frp"],
                detection_count=c["total_detections"], active_days=c["active_days"],
                facilities=facilities, observation_span_days=c["observation_span_days"]
            )
            features_list.append(features)

        predictions = ml_engine.predict_batch(features_list)

        for idx, c in enumerate(clustered_sources):
            features = features_list[idx]
            pred_res = predictions[idx]
            risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
                pred_res["predicted_event_type"], features["min_distance_to_industry_km"],
                c["mean_frp"], c["max_frp"], c["active_days"], c["total_detections"]
            )

            # Determine SIH alert severity based on event type, FRP, and risk
            if pred_res["predicted_event_type"] == "Industrial" or c.get("max_frp", 0) >= 40.0:
                sih_alert = "CRITICAL"
            elif risk_level == "High" or c.get("max_frp", 0) >= 20.0 or c.get("active_days", 0) >= 3:
                sih_alert = "HIGH"
            elif risk_level == "Medium":
                sih_alert = "MEDIUM"
            else:
                sih_alert = "LOW"

            c["event_type"] = pred_res["predicted_event_type"]
            c["predicted_event_type"] = pred_res["predicted_event_type"]
            c["confidence_pct"] = pred_res["confidence_pct"]
            c["confidence"] = pred_res["confidence_pct"]
            c["risk_level"] = risk_level
            c["risk_description"] = risk_desc
            c["sih_alert_severity"] = sih_alert
            c["is_flare_anomaly"] = is_flare_anomaly
            c["is_persistent"] = c["active_days"] >= 3 or c["total_detections"] >= 5
            c["nearest_facility_type"] = features["nearest_facility_type"]
            c["nearest_facility_name"] = features["nearest_facility_name"]
            c["landcover_class"] = features["landcover_class"]

            # Dynamic satellite persistence calculation (based on active days, span, detection frequency & industrial proximity)
            act_days = max(1, int(c.get("active_days", 1)))
            obs_span = max(1, int(c.get("observation_span_days", days)))
            tot_dets = max(1, int(c.get("total_detections", 1)))
            is_ind = pred_res["predicted_event_type"] == "Industrial"

            day_ratio = min(1.0, act_days / obs_span)
            density_ratio = min(1.0, tot_dets / (act_days * 3.0))
            ind_boost = 25.0 if is_ind else 0.0

            calc_pers = round(min(98.5, max(14.0, (day_ratio * 50.0) + (density_ratio * 25.0) + ind_boost)), 1)
            c["persistence_score"] = calc_pers

            synced_sources.append(c)
        t_ml = time.time() - t2

        sqlite_before = db_manager.count_sources()
        storage_service.save_new_sources_batch(synced_sources)
        sqlite_after = db_manager.count_sources()

        class_counts = {"Agricultural": 0, "Forest/Natural": 0, "Industrial": 0, "Other": 0}
        conf_scores = []
        pers_scores = []
        persistent_count = 0

        for s in synced_sources:
            etype = s.get("predicted_event_type", "Other")
            if etype in class_counts:
                class_counts[etype] += 1
            else:
                class_counts["Other"] += 1
            conf_scores.append(s.get("confidence_pct", 80.0))
            pers_scores.append(s.get("persistence_score", 50.0))
            if s.get("is_persistent"):
                persistent_count += 1

        acq_dates = [h.get("acq_date") for h in raw_hotspots if h.get("acq_date")]
        start_date = min(acq_dates) if acq_dates else time.strftime("%Y-%m-%d")
        end_date = max(acq_dates) if acq_dates else time.strftime("%Y-%m-%d")
        calendar_days = len(set(acq_dates)) if acq_dates else 1
        t_total = time.time() - t0

        return 200, headers, json.dumps({
            "status": "success",
            "message": f"Successfully ingested {len(raw_hotspots)} NASA FIRMS hotspots, clustered into {len(synced_sources)} persistent/dynamic thermal sources.",
            "source": f"NASA FIRMS VIIRS NRT ({country})",
            "observation_window_days": days,
            "observation_window": {
                "start_date": start_date,
                "end_date": end_date,
                "calendar_days_covered": calendar_days
            },
            "processing_time_sec": {
                "firms_fetch": round(t_fetch, 2),
                "clustering": round(t_cluster, 2),
                "ml_prediction": round(t_ml, 2),
                "total": round(t_total, 2)
            },
            "sqlite_storage": {
                "count_before": sqlite_before,
                "count_after": sqlite_after
            },
            "sync_time": time.strftime("%H:%M:%S IST"),
            "hotspots_count": len(raw_hotspots),
            "clusters_count": len(synced_sources),
            "classified_count": len(synced_sources),
            "classification_counts": class_counts,
            "confidence_stats": {
                "mean": round(sum(conf_scores) / max(len(conf_scores), 1), 2),
                "min": round(min(conf_scores), 2) if conf_scores else 0.0,
                "max": round(max(conf_scores), 2) if conf_scores else 0.0
            },
            "persistence_stats": {
                "persistent_count": persistent_count,
                "mean_score": round(sum(pers_scores) / max(len(pers_scores), 1), 2)
            },
            "storage_total_count": len(storage_service.sources),
            "sample_clusters": synced_sources,
            "clusters": synced_sources,
            "sources": synced_sources
        }, indent=2).encode("utf-8")

    def _handle_openapi(self, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "SIH AI-Based Industrial Fire Detection Backend",
                "version": "2.0.0",
                "description": "Enterprise Geospatial AI REST & GeoJSON backend for SIH Fire Recognition. Supports Auth, Multilingual Translations, Voice Control, Dual CSV Streaming, and National Alert Briefing."
            },
            "paths": {
                "/api/v1/health": {
                    "get": {
                        "summary": "Health check & model status",
                        "description": "Returns system health, total thermal sources, OSM facilities, active alerts, and model status.",
                        "responses": {"200": {"description": "System healthy"}}
                    }
                },
                "/predict": {
                    "get": {
                        "summary": "Live AI Prediction endpoint (Query Parameters)",
                        "description": "Run AI classification using query parameters.",
                        "parameters": [
                            {"name": "latitude", "in": "query", "required": False, "schema": {"type": "number", "default": 29.4614}, "description": "Latitude coordinate"},
                            {"name": "longitude", "in": "query", "required": False, "schema": {"type": "number", "default": 76.8636}, "description": "Longitude coordinate"},
                            {"name": "mean_frp", "in": "query", "required": False, "schema": {"type": "number", "default": 45.0}, "description": "Fire Radiative Power (MW)"},
                            {"name": "state", "in": "query", "required": False, "schema": {"type": "string", "default": "Odisha"}, "description": "Indian State jurisdiction"}
                        ],
                        "responses": {"200": {"description": "Prediction result with confidence and SIH alert severity"}}
                    },
                    "post": {
                        "summary": "Live AI Prediction endpoint (JSON Body)",
                        "description": "Submit full satellite and GIS parameters for real-time Random Forest inference.",
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "latitude": {"type": "number", "example": 29.4614},
                                            "longitude": {"type": "number", "example": 76.8636},
                                            "mean_frp": {"type": "number", "example": 45.0},
                                            "max_frp": {"type": "number", "example": 85.0},
                                            "state": {"type": "string", "example": "Odisha"},
                                            "facility_type": {"type": "string", "example": "Refinery"},
                                            "distance_industry": {"type": "number", "example": 0.1},
                                            "active_days": {"type": "integer", "example": 10},
                                            "observation_span": {"type": "integer", "example": 20}
                                        }
                                    },
                                    "example": {
                                        "latitude": 29.4614,
                                        "longitude": 76.8636,
                                        "mean_frp": 45.0,
                                        "max_frp": 85.0,
                                        "state": "Odisha",
                                        "facility_type": "Refinery",
                                        "distance_industry": 0.1,
                                        "active_days": 10,
                                        "observation_span": 20
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "AI Classification Output"}}
                    }
                },
                "/api/v1/auth/register": {
                    "post": {
                        "summary": "Register new authority/analyst user",
                        "description": "Creates a new user record with credentials and returns session token.",
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "email": {"type": "string", "example": "officer.sih@gov.in"},
                                            "password": {"type": "string", "example": "Password@123"},
                                            "name": {"type": "string", "example": "Officer Sharma"},
                                            "role": {"type": "string", "example": "State Emergency Analyst"},
                                            "organization": {"type": "string", "example": "State Disaster Management Authority"}
                                        }
                                    },
                                    "example": {
                                        "email": "officer.sih@gov.in",
                                        "password": "Password@123",
                                        "name": "Officer Sharma",
                                        "role": "State Emergency Analyst",
                                        "organization": "State Disaster Management Authority"
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "Registration successful"}}
                    }
                },
                "/api/v1/auth/login": {
                    "post": {
                        "summary": "User authentication credentials login",
                        "description": "Authenticates user and returns JWT session token.",
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "email": {"type": "string", "example": "admin@sih.gov.in"},
                                            "password": {"type": "string", "example": "Admin@123"}
                                        }
                                    },
                                    "example": {
                                        "email": "admin@sih.gov.in",
                                        "password": "Admin@123"
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "Login successful"}}
                    }
                },
                "/api/v1/voice/command": {
                    "post": {
                        "summary": "Natural language speech transcript intent processing",
                        "description": "Parses voice transcript and extracts state, event type, and dispatch intents.",
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "command": {"type": "string", "example": "Show Odisha"},
                                            "language": {"type": "string", "example": "en-US"}
                                        }
                                    },
                                    "example": {
                                        "command": "Show Odisha",
                                        "language": "en-US"
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "Parsed intent and spoken voice reply"}}
                    }
                },
                "/api/v1/alerts/dispatch": {
                    "post": {
                        "summary": "Dispatch urgent incident briefing to NDMA",
                        "description": "Queues high-priority thermal incident briefing to National Disaster Authority.",
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "state": {"type": "string", "example": "Odisha"},
                                            "critical_count": {"type": "integer", "example": 5},
                                            "high_count": {"type": "integer", "example": 12},
                                            "officer_email": {"type": "string", "example": "chief.ndma@gov.in"}
                                        }
                                    },
                                    "example": {
                                        "state": "Odisha",
                                        "critical_count": 5,
                                        "high_count": 12,
                                        "officer_email": "chief.ndma@gov.in"
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "Briefing dispatched"}}
                    }
                },
                "/api/v1/languages": {
                    "get": {
                        "summary": "Get supported Indian languages list",
                        "responses": {"200": {"description": "List of 5 supported languages"}}
                    }
                },
                "/event_classification_features.csv": {
                    "get": {
                        "summary": "Event classification features CSV",
                        "responses": {"200": {"description": "CSV stream"}}
                    }
                },
                "/source_persistence_features.csv": {
                    "get": {
                        "summary": "Source persistence features CSV",
                        "responses": {"200": {"description": "CSV stream"}}
                    }
                },
                "/predictions.csv": {
                    "get": {
                        "summary": "Unified predictions CSV",
                        "responses": {"200": {"description": "CSV stream"}}
                    }
                }
            }
        }
        return 200, headers, json.dumps(spec, indent=2).encode("utf-8")

router = APIRouter()