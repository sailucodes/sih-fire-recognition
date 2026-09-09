from fastapi import FastAPI, Query, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.services.storage_service import storage_service
from app.services.osm_service import osm_service
from app.services.firms_service import firms_service
from app.services.auth_service import auth_service
from app.services.language_service import language_service
from app.services.voice_service import voice_service
from app.services.alert_dispatcher_service import alert_dispatcher_service

from app.core.feature_engineering import extract_features_for_point
from app.core.ml_model import ml_engine
from app.core.anomaly_detector import evaluate_thermal_risk
from app.core.clustering import cluster_firms_hotspots

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
DATA_DIR = BASE_DIR / "data"

app = FastAPI(
    title="SIH AI Industrial Fire & Persistent Thermal Source Backend",
    version="2.0.0",
    description="Enterprise Geospatial AI REST & GeoJSON backend for SIH Fire Recognition."
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
    return "<h1>SIH Fire Recognition Backend v2.0</h1>"

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "system": "AI-Based Industrial Fire & Persistent Thermal Source Detection System",
        "version": "2.0.0",
        "model_status": "loaded" if ml_engine.model is not None else "ready",
        "model_classes": ml_engine.classes_,
        "total_thermal_sources_indexed": len(storage_service.sources),
        "osm_facilities_indexed": len(osm_service.facilities),
        "active_alerts_count": len(storage_service.alerts),
        "dispatched_national_briefs": len(alert_dispatcher_service.dispatches),
        "supported_languages": list(language_service.get_supported_languages()["languages"].keys())
    }

# ----------------- AUTHENTICATION ----------------- #
@app.post("/api/v1/auth/register")
async def auth_register(payload: Dict[str, Any] = Body(...)):
    res = auth_service.register(
        email=payload.get("email", ""),
        password=payload.get("password", ""),
        name=payload.get("name", ""),
        role=payload.get("role", "State Emergency Analyst"),
        organization=payload.get("organization", "State EOC")
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.post("/api/v1/auth/login")
async def auth_login(payload: Dict[str, Any] = Body(...)):
    res = auth_service.login(
        email=payload.get("email", ""),
        password=payload.get("password", "")
    )
    if not res.get("success"):
        raise HTTPException(status_code=401, detail=res.get("error"))
    return res

@app.post("/api/v1/auth/google")
async def auth_google(payload: Dict[str, Any] = Body(...)):
    return auth_service.google_auth(
        google_token=payload.get("token"),
        email=payload.get("email"),
        name=payload.get("name")
    )

@app.get("/api/v1/auth/me")
async def auth_me(token: str = Query(...)):
    user = auth_service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session token")
    return {"authenticated": True, "user": user}

# ----------------- MULTILINGUAL & VOICE ----------------- #
@app.get("/api/v1/languages")
async def get_languages():
    return language_service.get_supported_languages()

@app.get("/api/v1/translations/{lang}")
@app.get("/translations")
async def get_translations(lang: str = "en-US"):
    return language_service.get_translations(lang)

@app.post("/api/v1/voice/command")
@app.post("/voice/command")
async def process_voice(payload: Dict[str, Any] = Body(...)):
    cmd = payload.get("command") or payload.get("transcript") or ""
    lang = payload.get("language") or payload.get("lang") or "en-US"
    return voice_service.process_voice_command(cmd, lang)

# ----------------- ALERT DISPATCHER ----------------- #
@app.post("/api/v1/alerts/dispatch")
@app.post("/alerts/dispatch")
async def dispatch_alert(payload: Dict[str, Any] = Body(...)):
    state = payload.get("state") or "National"
    critical_cnt = int(payload.get("critical_count") or len([a for a in storage_service.alerts if a.get("severity") == "CRITICAL"]))
    high_cnt = int(payload.get("high_count") or len([a for a in storage_service.alerts if a.get("severity") == "HIGH"]))
    officer = payload.get("officer_email") or "officer.ndma@gov.in"
    return alert_dispatcher_service.dispatch_brief(state, critical_cnt, high_cnt, officer)

@app.get("/api/v1/alerts/dispatched")
async def get_dispatches():
    return {"count": len(alert_dispatcher_service.dispatches), "dispatches": alert_dispatcher_service.list_dispatches()}

# ----------------- PREDICTION ENDPOINT ----------------- #
@app.get("/predict")
@app.post("/predict")
@app.get("/api/v1/predict")
@app.post("/api/v1/predict")
@app.post("/api/v1/classify")
async def predict_point(request: Request, payload: Optional[Dict[str, Any]] = Body(None)):
    if payload is None:
        payload = {}
    
    q_params = dict(request.query_params)
    
    lat = float(payload.get("latitude") or payload.get("lat") or q_params.get("latitude") or q_params.get("lat") or 29.46148)
    lon = float(payload.get("longitude") or payload.get("lon") or q_params.get("longitude") or q_params.get("lon") or 76.86364)
    mean_frp = float(payload.get("mean_frp") or payload.get("frp") or q_params.get("mean_frp") or q_params.get("frp") or 25.0)
    max_frp = float(payload.get("max_frp") or mean_frp)
    mean_bright = float(payload.get("mean_brightness") or payload.get("brightness") or 330.0)
    max_bright = float(payload.get("max_brightness") or mean_bright)
    
    active_days = int(payload.get("active_days") or q_params.get("active_days") or 1)
    detection_count = int(payload.get("total_detections") or payload.get("detection_count") or 1)
    obs_span = max(1, int(payload.get("observation_span") or payload.get("observation_span_days") or 1))
    
    state_val = payload.get("state") or q_params.get("state") or "Odisha"
    calculated_persistence = min(100.0, round((active_days / obs_span) * 100, 1))

    fac_type = payload.get("facility_type") or payload.get("nearest_facility_type")
    if fac_type and fac_type.lower() != "none":
        fac_type = fac_type.lower().replace(" ", "_")
    else:
        fac_type = None

    dist_industry = payload.get("distance_industry") or payload.get("distance_to_nearest_industry") or payload.get("min_distance_to_industry_km")
    dist_industry = float(dist_industry) if dist_industry is not None else None

    facilities = osm_service.get_all_facilities()
    features = extract_features_for_point(
        lat=lat, lon=lon, frp=mean_frp, max_frp=max_frp,
        brightness=mean_bright, max_brightness=max_bright,
        detection_count=detection_count, active_days=active_days,
        facilities=facilities, observation_span_days=obs_span,
        override_nearest_type=fac_type,
        override_min_dist=dist_industry
    )
    pred_res = ml_engine.predict_single(features)
    conf = pred_res["confidence_pct"]
    pred_type = pred_res["predicted_event_type"]

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

    return {
        "source_id": payload.get("source_id", f"PRED_{int(lat*1000)}_{int(lon*1000)}"),
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
        "explanation": pred_res["explanation"]
    }

# ----------------- CSV DATA SERVING ----------------- #
def serve_csv_file(filename: str):
    target = DATA_DIR / filename
    if not target.exists():
        target = STATIC_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    with open(target, "rb") as f:
        content = f.read()
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/event_classification_features.csv")
@app.get("/data/event_classification_features.csv")
async def get_event_csv():
    return serve_csv_file("event_classification_features.csv")

@app.get("/source_persistence_features.csv")
@app.get("/data/source_persistence_features.csv")
async def get_persistence_csv():
    return serve_csv_file("source_persistence_features.csv")

@app.get("/predictions.csv")
@app.get("/api/v1/export/report")
async def get_predictions_csv():
    return serve_csv_file("predictions.csv")