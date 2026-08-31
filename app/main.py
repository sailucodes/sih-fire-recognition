from fastapi import FastAPI, Query, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.services.storage_service import storage_service
from app.services.osm_service import osm_service
from app.services.firms_service import firms_service
from app.core.feature_engineering import extract_features_for_point
from app.core.ml_model import ml_engine
from app.core.anomaly_detector import evaluate_thermal_risk
from app.core.clustering import cluster_firms_hotspots

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI(
    title="SIH AI Industrial Fire & Persistent Thermal Source Backend",
    version="1.0.0",
    description="Geospatial AI REST & GeoJSON backend for SIH Fire Recognition."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def serve_map_ui():
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SIH Fire Recognition Backend</h1>"

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "system": "AI-Based Industrial Fire & Persistent Thermal Source Detection System",
        "version": "1.0.0",
        "model_status": "loaded" if ml_engine.model is not None else "ready",
        "model_classes": ml_engine.classes_,
        "total_thermal_sources_indexed": len(storage_service.sources),
        "osm_facilities_indexed": len(osm_service.facilities)
    }

@app.get("/predict")
@app.post("/predict")
@app.get("/api/v1/predict")
@app.post("/api/v1/predict")
@app.post("/api/v1/classify")
async def predict_point(request: Request, payload: Optional[Dict[str, Any]] = Body(None)):
    if payload is None:
        payload = {}
    
    # Check query params if GET request
    q_params = dict(request.query_params)
    
    lat = float(payload.get("latitude") or payload.get("lat") or q_params.get("latitude") or q_params.get("lat") or 29.46148)
    lon = float(payload.get("longitude") or payload.get("lon") or q_params.get("longitude") or q_params.get("lon") or 76.86364)
    frp = float(payload.get("frp") or payload.get("mean_frp") or q_params.get("frp") or 25.0)
    brightness = float(payload.get("brightness") or payload.get("mean_brightness") or q_params.get("brightness") or 335.0)
    active_days = int(payload.get("active_days") or q_params.get("active_days") or 4)
    detection_count = int(payload.get("detection_count") or payload.get("total_detections") or q_params.get("detection_count") or 1)
    landcover_class = payload.get("landcover_class") or payload.get("landcover") or q_params.get("landcover_class")

    facilities = osm_service.get_all_facilities()
    features = extract_features_for_point(
        lat=lat, lon=lon, frp=frp,
        brightness=brightness,
        detection_count=detection_count,
        active_days=active_days,
        facilities=facilities,
        landcover_class=landcover_class
    )
    pred_res = ml_engine.predict_single(features)
    conf = pred_res["confidence_pct"]
    pred_type = pred_res["predicted_event_type"]

    # SIH Alert Rule matching teammate app.js
    if pred_type == "Industrial" and conf >= 80.0:
        sih_alert_severity = "HIGH"
    elif pred_type == "Industrial" and conf >= 60.0:
        sih_alert_severity = "MEDIUM"
    else:
        sih_alert_severity = "LOW"

    risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
        pred_type,
        features["min_distance_to_industry_km"],
        frp, frp, active_days, detection_count
    )

    return {
        "source_id": payload.get("source_id", f"PRED_{int(lat*1000)}_{int(lon*1000)}"),
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

@app.get("/predictions.csv")
@app.get("/api/v1/export/report")
async def get_predictions_csv():
    import io, csv
    sources = list(storage_service.sources.values())
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
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=predictions.csv"})