# 🛰️ AeroThermal AI: Industrial Fire & Persistent Thermal Source Detection Backend

An end-to-end Geospatial AI Backend system designed for automated detection, spatio-temporal clustering, classification, and GIS map monitoring of **Industrial Fires and Persistent Thermal Sources** (refineries, power plants, mines, petrochemical complexes) vs **Wildfires / Forest Fires** and **Agricultural Stubble Burning**, by fusing **NASA FIRMS**, **OpenStreetMap (OSM)**, and **Copernicus Land Cover** data.

---

## 🎯 Key Features & Capabilities

1. **AI Classification & Segregation (Deliverable i)**:
   - Multi-class Machine Learning Ensemble (Random Forest + Gradient Boosting) trained on 34 spatial, radiative, and temporal persistence features.
   - Segregates thermal detections into 4 distinct categories:
     - `Industrial` (Refinery gas flaring, kiln operations, smelters, petrochemical fires)
     - `Forest/Natural` (Forest wildfires, bushfires, vegetation burns)
     - `Agricultural` (Crop residue / seasonal stubble burning)
     - `Other` (Urban fires, intermittent unidentified thermal anomalies)
   - Outputs class probabilities and explainable diagnostic reasons.

2. **GIS & Map Overlays (Deliverable ii)**:
   - **RFC 7946 GeoJSON Endpoints** for instant integration with Mapbox GL JS, Leaflet, Cesium, OpenLayers, or Google Maps.
   - Dynamic marker color coding (`#ef4444` Industrial, `#10b981` Forest, `#f59e0b` Agricultural, `#6366f1` Other) and radius scaling based on Fire Radiative Power (FRP).
   - OSM Industrial Infrastructure overlay layer with verified refinery, power plant, and mine coordinates.

3. **Spatio-Temporal Aggregation & DBSCAN Clustering**:
   - Groups raw NASA FIRMS (VIIRS/MODIS) satellite detections into persistent thermal sources using spatial adjacency ($\le 1.5$ km) and temporal windowing.
   - Computes recurrence rate, observation span days, detection frequency, gap metrics, and temporal regularity.

4. **Industrial Flare-up & Explosion Anomaly Detection**:
   - Distinguishes between routine operational gas flaring and dangerous flare-up / accidental industrial explosions using dynamic FRP z-score thresholds.

5. **Standalone Interactive Visualizer & Swagger Docs**:
   - Built-in Leaflet GIS map dashboard served directly from the backend at `http://localhost:8000/`.
   - Interactive Swagger / OpenAPI documentation at `http://localhost:8000/docs`.

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.10+ (Python 3.11 / 3.12 / 3.13 supported)

### 2. Start the Backend Server
```bash
# Direct runner
python run.py

# Or specify a custom port
python run.py 8000
```

Once running:
- 🗺️ **Interactive GIS Map Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- 📖 **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🛰️ **Live GeoJSON Map Overlay API**: [http://localhost:8000/api/v1/sources/geojson](http://localhost:8000/api/v1/sources/geojson)

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Health check, model status, and indexed record counts |
| `GET` | `/api/v1/sources` | Filtered list of thermal sources (JSON) |
| `GET` | `/api/v1/sources/geojson` | **Direct GeoJSON Map Overlay** for frontend map layers |
| `GET` | `/api/v1/sources/{source_id}` | Detailed single thermal source profile with history |
| `POST` | `/api/v1/classify` | On-demand single coordinate classification & feature extraction |
| `POST` | `/api/v1/classify/batch` | Batch CSV/JSON classification upload |
| `GET` | `/api/v1/infrastructure/geojson` | OSM Industrial facilities layer for map overlay |
| `GET` | `/api/v1/analytics/summary` | Classification metrics, fire counts, risk breakdowns |
| `GET` | `/api/v1/analytics/timeline` | Time-series daily trend of industrial vs natural fires |
| `POST` | `/api/v1/firms/sync` | Trigger NASA FIRMS data ingestion & clustering |
| `GET` | `/api/v1/alerts` | Urgent industrial fire & flare-up anomaly alerts |
| `GET` | `/api/v1/export/report` | Download classification summary report (CSV / JSON) |

---

## 🤝 Frontend Integration Guide

If your frontend teammate is using **Leaflet**, **Mapbox GL JS**, or **Deck.gl**, they can connect directly to the backend GeoJSON endpoints:

### Example: Adding Thermal Source Layer in Mapbox / Leaflet
```javascript
// Fetch direct GeoJSON overlay from backend
fetch('http://localhost:8000/api/v1/sources/geojson?event_type=Industrial')
  .then(res => res.json())
  .then(geojson => {
    L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: feature.properties.marker_radius || 8,
          fillColor: feature.properties.marker_color || '#ef4444',
          color: '#ffffff',
          weight: 1.5,
          fillOpacity: 0.8
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        layer.bindPopup(`
          <h3>${p.predicted_event_type} (${p.confidence_pct}%)</h3>
          <p><b>Nearest Facility:</b> ${p.nearest_facility_name} (${p.min_distance_to_industry_km} km)</p>
          <p><b>FRP:</b> ${p.max_frp} MW | <b>Active Days:</b> ${p.active_days}</p>
        `);
      }
    }).addTo(map);
  });
```

---

## 🧪 Running Automated Tests

```bash
python -m unittest discover -s tests
```