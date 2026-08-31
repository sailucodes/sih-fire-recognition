from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
    title="NASA FIRMS & OSM AI-Based Industrial Fire Detection Backend",
    version="1.0.0",
    description="Geospatial AI REST & GeoJSON backend for the automatic identification, classification, and monitoring of Industrial Fires vs Wildfires and Agricultural Burns."
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
    return "<h1>AeroThermal AI Map Visualizer</h1>"

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

@app.get("/api/v1/sources")
async def list_sources(
    event_type: Optional[str] = None,
    min_frp: Optional[float] = None,
    is_persistent: Optional[bool] = None,
    risk_level: Optional[str] = None,
    limit: int = 200
):
    sources = storage_service.list_sources(
        event_type=event_type,
        min_frp=min_frp,
        is_persistent=is_persistent,
        risk_level=risk_level,
        limit=limit
    )
    return {"count": len(sources), "sources": sources}

@app.get("/api/v1/sources/geojson")
async def get_sources_geojson(
    event_type: Optional[str] = None,
    min_frp: Optional[float] = None,
    is_persistent: Optional[bool] = None,
    risk_level: Optional[str] = None,
    min_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    max_lon: Optional[float] = None
):
    return storage_service.get_geojson(
        event_type=event_type,
        min_frp=min_frp,
        is_persistent=is_persistent,
        risk_level=risk_level,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon
    )

@app.get("/api/v1/sources/{source_id}")
async def get_source_detail(source_id: str):
    source = storage_service.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    return source

@app.post("/api/v1/classify")
async def classify_point(payload: Dict[str, Any] = Body(...)):
    lat = float(payload.get("latitude", 0.0))
    lon = float(payload.get("longitude", 0.0))
    frp = float(payload.get("frp", 10.0))
    active_days = int(payload.get("active_days", 1))
    detection_count = int(payload.get("detection_count", 1))
    landcover_class = payload.get("landcover_class", None)

    facilities = osm_service.get_all_facilities()
    features = extract_features_for_point(
        lat=lat, lon=lon, frp=frp,
        detection_count=detection_count,
        active_days=active_days,
        facilities=facilities,
        landcover_class=landcover_class
    )
    pred_res = ml_engine.predict_single(features)
    risk_level, is_flare_anomaly, risk_desc = evaluate_thermal_risk(
        pred_res["predicted_event_type"],
        features["min_distance_to_industry_km"],
        frp, frp, active_days, detection_count
    )

    return {
        "latitude": lat,
        "longitude": lon,
        "predicted_event_type": pred_res["predicted_event_type"],
        "confidence_pct": pred_res["confidence_pct"],
        "probabilities": pred_res["probabilities"],
        "is_persistent_thermal_source": active_days >= 3,
        "is_flare_anomaly": is_flare_anomaly,
        "risk_level": risk_level,
        "risk_description": risk_desc,
        "nearest_facility_type": features["nearest_facility_type"],
        "nearest_facility_name": features["nearest_facility_name"],
        "nearest_facility_distance_km": features["min_distance_to_industry_km"],
        "landcover_class": features["landcover_class"],
        "explanation": pred_res["explanation"]
    }

@app.get("/api/v1/infrastructure/geojson")
async def get_infrastructure_geojson():
    return osm_service.get_geojson()

@app.get("/api/v1/analytics/summary")
async def get_analytics_summary():
    return storage_service.get_analytics_summary()

@app.get("/api/v1/analytics/timeline")
async def get_analytics_timeline():
    return {"timeline": storage_service.get_timeline()}

@app.get("/api/v1/alerts")
async def get_alerts():
    alerts = storage_service.get_alerts()
    return {"count": len(alerts), "alerts": alerts}

@app.post("/api/v1/firms/sync")
async def sync_firms_data(country: str = "IND", days: int = 1):
    raw_hotspots = firms_service.fetch_live_hotspots(country_code=country, days=days)
    clusters = cluster_firms_hotspots(raw_hotspots, eps_km=1.5)
    facilities = osm_service.get_all_facilities()
    synced = []

    for c in clusters:
        features = extract_features_for_point(
            lat=c["latitude"], lon=c["longitude"], frp=c["mean_frp"],
            detection_count=c["total_detections"], active_days=c["active_days"],
            facilities=facilities, observation_span_days=c["observation_span_days"]
        )
        pred = ml_engine.predict_single(features)
        risk, is_flare, r_desc = evaluate_thermal_risk(
            pred["predicted_event_type"], features["min_distance_to_industry_km"],
            c["mean_frp"], c["max_frp"], c["active_days"], c["total_detections"]
        )
        c["event_type"] = pred["predicted_event_type"]
        c["predicted_event_type"] = pred["predicted_event_type"]
        c["confidence_pct"] = pred["confidence_pct"]
        c["risk_level"] = risk
        c["risk_description"] = r_desc
        c["is_flare_anomaly"] = is_flare
        c["is_persistent"] = c["active_days"] >= 3
        c["nearest_facility_type"] = features["nearest_facility_type"]
        c["nearest_facility_name"] = features["nearest_facility_name"]
        c["min_distance_to_industry_km"] = features["min_distance_to_industry_km"]
        c["landcover_class"] = features["landcover_class"]
        storage_service.save_new_source(c)
        synced.append(c)

    return {
        "status": "success",
        "message": f"Successfully ingested {len(raw_hotspots)} FIRMS hotspots and updated {len(synced)} clusters.",
        "clusters_count": len(synced)
    }