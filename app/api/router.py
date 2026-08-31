import json
import csv
import io
from typing import Dict, Any, List, Tuple
from urllib.parse import parse_qs, urlparse
from app.services.storage_service import storage_service
from app.services.osm_service import osm_service
from app.services.firms_service import firms_service
from app.core.feature_engineering import extract_features_for_point
from app.core.ml_model import ml_engine
from app.core.anomaly_detector import evaluate_thermal_risk
from app.core.clustering import cluster_firms_hotspots

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

            # 2. Thermal Sources Listing (JSON)
            elif parsed_path in ["/api/v1/sources", "/sources"] and method == "GET":
                return self._handle_list_sources(query_params, headers)

            # 3. Direct GeoJSON Map Overlay
            elif parsed_path in ["/api/v1/sources/geojson", "/geojson"] and method == "GET":
                return self._handle_sources_geojson(query_params, headers)

            # 4. Single Thermal Source Detail
            elif parsed_path.startswith("/api/v1/sources/") and method == "GET":
                source_id = parsed_path.split("/")[-1]
                return self._handle_source_detail(source_id, headers)

            # 5. Live Prediction Endpoint (Supports GET & POST for /predict)
            elif parsed_path in ["/predict", "/api/v1/predict", "/api/v1/classify"] and method in ["GET", "POST"]:
                return self._handle_predict_single(method, query_params, body_data, headers)

            # 6. Batch CSV / JSON Classification Upload
            elif parsed_path in ["/api/v1/classify/batch", "/predict/batch"] and method in ["GET", "POST"]:
                return self._handle_classify_batch(body_data, headers)

            # 7. OSM Industrial Infrastructure
            elif parsed_path in ["/api/v1/infrastructure", "/infrastructure"] and method == "GET":
                data = osm_service.get_all_facilities()
                return 200, headers, json.dumps({"count": len(data), "facilities": data}).encode("utf-8")

            elif parsed_path in ["/api/v1/infrastructure/geojson", "/infrastructure/geojson"] and method == "GET":
                geojson = osm_service.get_geojson()
                return 200, headers, json.dumps(geojson).encode("utf-8")

            # 8. Analytics & KPI Summary
            elif parsed_path in ["/api/v1/analytics/summary", "/analytics"] and method == "GET":
                stats = storage_service.get_analytics_summary()
                return 200, headers, json.dumps(stats).encode("utf-8")

            # 9. Time-Series Timeline Breakdown
            elif parsed_path in ["/api/v1/analytics/timeline", "/timeline"] and method == "GET":
                timeline = storage_service.get_timeline()
                return 200, headers, json.dumps({"timeline": timeline}).encode("utf-8")

            # 10. Risk Alerts
            elif parsed_path in ["/api/v1/alerts", "/alerts"] and method == "GET":
                alerts = storage_service.get_alerts()
                return 200, headers, json.dumps({"count": len(alerts), "alerts": alerts}).encode("utf-8")

            # 11. Trigger NASA FIRMS Sync & Ingestion Pipeline
            elif parsed_path in ["/api/v1/firms/sync", "/firms/sync"] and method in ["GET", "POST"]:
                return self._handle_firms_sync(query_params, headers)

            # 12. Export Report (CSV / JSON) / Served for frontend predictions.csv
            elif parsed_path in ["/api/v1/export/report", "/predictions.csv"] and method == "GET":
                return self._handle_export_report(query_params, headers)

            # 13. OpenAPI Specification
            elif parsed_path == "/api/v1/openapi.json" and method == "GET":
                return self._handle_openapi(headers)

            else:
                return 404, headers, json.dumps({"error": "Endpoint not found", "path": path}).encode("utf-8")

        except Exception as e:
            return 500, headers, json.dumps({"error": str(e)}).encode("utf-8")

    # ---------------- HANDLERS ---------------- #

    def _handle_health(self, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        data = {
            "status": "healthy",
            "system": "AI-Based Industrial Fire & Persistent Thermal Source Detection System",
            "version": "1.0.0",
            "model_status": "loaded" if ml_engine.model is not None else "ready",
            "model_classes": ml_engine.classes_,
            "total_thermal_sources_indexed": len(storage_service.sources),
            "osm_facilities_indexed": len(osm_service.facilities)
        }
        return 200, headers, json.dumps(data, indent=2).encode("utf-8")

    def _handle_list_sources(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        event_type = query_params.get("event_type", [None])[0]
        min_frp = float(query_params.get("min_frp", [0])[0]) if "min_frp" in query_params else None
        is_persistent = (query_params.get("is_persistent", [""])[0].lower() == "true") if "is_persistent" in query_params else None
        risk_level = query_params.get("risk_level", [None])[0]
        limit = int(query_params.get("limit", [200])[0])

        sources = storage_service.list_sources(
            event_type=event_type,
            min_frp=min_frp,
            is_persistent=is_persistent,
            risk_level=risk_level,
            limit=limit
        )
        return 200, headers, json.dumps({"count": len(sources), "sources": sources}).encode("utf-8")

    def _handle_sources_geojson(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        event_type = query_params.get("event_type", [None])[0]
        min_frp = float(query_params.get("min_frp", [0])[0]) if "min_frp" in query_params else None
        is_persistent = (query_params.get("is_persistent", [""])[0].lower() == "true") if "is_persistent" in query_params else None
        risk_level = query_params.get("risk_level", [None])[0]
        
        min_lat = float(query_params.get("min_lat", [0])[0]) if "min_lat" in query_params else None
        min_lon = float(query_params.get("min_lon", [0])[0]) if "min_lon" in query_params else None
        max_lat = float(query_params.get("max_lat", [0])[0]) if "max_lat" in query_params else None
        max_lon = float(query_params.get("max_lon", [0])[0]) if "max_lon" in query_params else None

        geojson = storage_service.get_geojson(
            event_type=event_type,
            min_frp=min_frp,
            is_persistent=is_persistent,
            risk_level=risk_level,
            min_lat=min_lat,
            min_lon=min_lon,
            max_lat=max_lat,
            max_lon=max_lon
        )
        return 200, headers, json.dumps(geojson).encode("utf-8")

    def _handle_source_detail(self, source_id: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        source = storage_service.get_source(source_id)
        if not source:
            return 404, headers, json.dumps({"error": f"Thermal source {source_id} not found"}).encode("utf-8")
        return 200, headers, json.dumps(source, indent=2).encode("utf-8")

    def _handle_predict_single(self, method: str, query_params: Dict[str, List[str]], body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        """
        Main Live Prediction Handler matching teammate frontend (http://127.0.0.1:8000/predict).
        Supports both GET (with query parameters or default demo) and POST (JSON body).
        """
        body = {}
        if method == "POST" and body_data:
            try:
                body = json.loads(body_data.decode("utf-8"))
            except Exception:
                pass

        lat = float(body.get("latitude") or body.get("lat") or query_params.get("latitude", [query_params.get("lat", [29.46148])[0]])[0])
        lon = float(body.get("longitude") or body.get("lon") or query_params.get("longitude", [query_params.get("lon", [76.86364])[0]])[0])
        frp = float(body.get("frp") or body.get("mean_frp") or query_params.get("frp", [25.0])[0])
        brightness = float(body.get("brightness") or body.get("mean_brightness") or query_params.get("brightness", [335.0])[0])
        detection_count = int(body.get("detection_count") or body.get("total_detections") or query_params.get("detection_count", [1])[0])
        active_days = int(body.get("active_days") or query_params.get("active_days", [4])[0])
        landcover_class = body.get("landcover_class") or body.get("landcover") or query_params.get("landcover_class", [None])[0]

        facilities = osm_service.get_all_facilities()
        
        # 1. Feature Engineering
        features = extract_features_for_point(
            lat=lat,
            lon=lon,
            frp=frp,
            brightness=brightness,
            detection_count=detection_count,
            active_days=active_days,
            facilities=facilities,
            landcover_class=landcover_class
        )

        # 2. AI Inference
        pred_res = ml_engine.predict_single(features)
        conf = pred_res["confidence_pct"]
        pred_type = pred_res["predicted_event_type"]

        # 3. SIH Alert Level Rule (Matching teammate app.js ALERT_RULES: Industrial + >=80 -> HIGH, >=60 -> MEDIUM)
        if pred_type == "Industrial" and conf >= 80.0:
            sih_alert_severity = "HIGH"
        elif pred_type == "Industrial" and conf >= 60.0:
            sih_alert_severity = "MEDIUM"
        else:
            sih_alert_severity = "LOW"

        # 4. Anomaly & Risk Assessment
        risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
            pred_type,
            features["min_distance_to_industry_km"],
            frp, frp, active_days, detection_count
        )

        response = {
            "source_id": body.get("source_id", f"PRED_{int(lat*1000)}_{int(lon*1000)}"),
            "latitude": lat,
            "longitude": lon,
            "event_type": pred_type,
            "predicted_event_type": pred_type,
            "confidence": conf,
            "confidence_pct": conf,
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
            "explanation": pred_res["explanation"]
        }
        return 200, headers, json.dumps(response, indent=2).encode("utf-8")

    def _handle_classify_batch(self, body_data: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        try:
            body = json.loads(body_data.decode("utf-8")) if body_data else {}
            items = body.get("items", [])
        except Exception:
            return 400, headers, json.dumps({"error": "Invalid JSON batch payload"}).encode("utf-8")

        facilities = osm_service.get_all_facilities()
        results = []

        for item in items:
            lat = float(item.get("latitude", 0.0))
            lon = float(item.get("longitude", 0.0))
            frp = float(item.get("frp", 5.0))
            active_days = int(item.get("active_days", 1))
            total_detections = int(item.get("total_detections", 1))

            features = extract_features_for_point(
                lat=lat, lon=lon, frp=frp,
                detection_count=total_detections,
                active_days=active_days,
                facilities=facilities
            )
            pred_res = ml_engine.predict_single(features)
            risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
                pred_res["predicted_event_type"],
                features["min_distance_to_industry_km"],
                frp, frp, active_days, total_detections
            )

            results.append({
                "source_id": item.get("source_id", "ANON_SOURCE"),
                "latitude": lat,
                "longitude": lon,
                "predicted_event_type": pred_res["predicted_event_type"],
                "confidence_pct": pred_res["confidence_pct"],
                "risk_level": risk_level,
                "is_persistent": active_days >= 3,
                "nearest_facility": features["nearest_facility_name"],
                "min_distance_km": features["min_distance_to_industry_km"]
            })

        return 200, headers, json.dumps({"total_processed": len(results), "results": results}).encode("utf-8")

    def _handle_firms_sync(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        country = query_params.get("country", ["IND"])[0]
        days = int(query_params.get("days", [1])[0])

        raw_hotspots = firms_service.fetch_live_hotspots(country_code=country, days=days)
        clustered_sources = cluster_firms_hotspots(raw_hotspots, eps_km=1.5)
        facilities = osm_service.get_all_facilities()
        synced_sources = []

        for c in clustered_sources:
            features = extract_features_for_point(
                lat=c["latitude"],
                lon=c["longitude"],
                frp=c["mean_frp"],
                detection_count=c["total_detections"],
                active_days=c["active_days"],
                facilities=facilities,
                observation_span_days=c["observation_span_days"]
            )
            pred_res = ml_engine.predict_single(features)
            risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
                pred_res["predicted_event_type"],
                features["min_distance_to_industry_km"],
                c["mean_frp"], c["max_frp"], c["active_days"], c["total_detections"]
            )

            c["event_type"] = pred_res["predicted_event_type"]
            c["predicted_event_type"] = pred_res["predicted_event_type"]
            c["confidence_pct"] = pred_res["confidence_pct"]
            c["risk_level"] = risk_level
            c["risk_description"] = risk_desc
            c["is_flare_anomaly"] = is_flare_anomaly
            c["is_persistent"] = c["active_days"] >= 3 or c["total_detections"] >= 5
            c["nearest_facility_type"] = features["nearest_facility_type"]
            c["nearest_facility_name"] = features["nearest_facility_name"]
            c["min_distance_to_industry_km"] = features["min_distance_to_industry_km"]
            c["landcover_class"] = features["landcover_class"]

            storage_service.save_new_source(c)
            synced_sources.append(c)

        return 200, headers, json.dumps({
            "status": "success",
            "message": f"Successfully ingested {len(raw_hotspots)} FIRMS hotspots, clustered into {len(synced_sources)} persistent/dynamic thermal sources.",
            "hotspots_count": len(raw_hotspots),
            "clusters_count": len(synced_sources),
            "sample_clusters": synced_sources[:5]
        }, indent=2).encode("utf-8")

    def _handle_export_report(self, query_params: Dict[str, List[str]], headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        fmt = query_params.get("format", ["csv"])[0].lower()
        sources = list(storage_service.sources.values())

        if fmt == "json":
            return 200, headers, json.dumps({"count": len(sources), "report": sources}, indent=2).encode("utf-8")

        output = io.StringIO()
        fieldnames = [
            "source_id", "latitude", "longitude", "nearest_refinery_km", "nearest_powerplant_km",
            "nearest_mine_km", "nearest_industrial_area_km", "landcover_code", "landcover_class",
            "mean_distance_to_industry_km", "min_distance_to_industry_km", "mean_industrial_facilities_1km",
            "mean_industrial_facilities_5km", "industrial_land_ratio", "forest_land_ratio", "agricultural_land_ratio",
            "nearest_facility_type", "first_detection", "last_detection", "total_detections", "active_days",
            "mean_frp", "max_frp", "observation_span_days", "recurrence_rate", "detections_per_span_day",
            "mean_gap_hours", "std_gap_hours", "median_gap_hours", "min_gap_hours", "max_gap_hours",
            "temporal_regularity", "max_active_days_7d", "max_active_days_14d", "max_active_days_30d",
            "observation_days", "event_type", "predicted_event_type", "confidence_pct"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for s in sources:
            writer.writerow(s)

        csv_headers = {
            "Content-Type": "text/csv",
            "Content-Disposition": "attachment; filename=predictions.csv",
            "Access-Control-Allow-Origin": "*"
        }
        return 200, csv_headers, output.getvalue().encode("utf-8")

    def _handle_openapi(self, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "SIH AI-Based Industrial Fire Detection Backend",
                "version": "1.0.0",
                "description": "Geospatial AI REST & GeoJSON backend for the identification and classification of Industrial Fires, Gas Flaring, Wildfires, and Agricultural burns."
            },
            "paths": {
                "/api/v1/health": {"get": {"summary": "Health check & model status"}},
                "/predict": {"get": {"summary": "Live AI Prediction endpoint"}, "post": {"summary": "Live AI Prediction endpoint matching teammate frontend"}},
                "/api/v1/sources": {"get": {"summary": "List thermal sources with filters"}},
                "/api/v1/sources/geojson": {"get": {"summary": "Direct RFC 7946 GeoJSON map overlay"}},
                "/api/v1/classify": {"post": {"summary": "On-demand real-time coordinate classification"}},
                "/api/v1/infrastructure/geojson": {"get": {"summary": "OSM Industrial infrastructure map layer"}},
                "/api/v1/analytics/summary": {"get": {"summary": "Aggregated statistics & KPI counts"}},
                "/api/v1/alerts": {"get": {"summary": "Industrial risk and explosion alerts"}},
                "/api/v1/firms/sync": {"post": {"summary": "Trigger NASA FIRMS live sync and clustering"}},
                "/predictions.csv": {"get": {"summary": "Predictions CSV file for frontend loading"}}
            }
        }
        return 200, headers, json.dumps(spec, indent=2).encode("utf-8")

router = APIRouter()