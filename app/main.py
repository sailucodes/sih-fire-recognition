from fastapi import FastAPI, Query, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.services.storage_service import storage_service, detect_state_for_coordinates
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

# ----------------- NASA FIRMS SYNC ENDPOINT ----------------- #
@app.get("/api/v1/firms/sync")
@app.post("/api/v1/firms/sync")
@app.get("/firms/sync")
@app.post("/firms/sync")
async def sync_firms(country: str = Query("IND"), days: int = Query(1), key: Optional[str] = Query(None)):
    import time
    t0 = time.time()
    try:
        raw_hotspots = firms_service.fetch_live_hotspots(country_code=country, days=days, api_key=key)
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "error": str(e),
            "message": "NASA FIRMS live synchronization could not proceed."
        })
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

    from app.db.database import db_manager
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

    return {
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
    }

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