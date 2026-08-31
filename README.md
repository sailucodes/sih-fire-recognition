---
title: Sih Fire Recognition
emoji: 🧯
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# AI-Based Detection & Classification of Industrial Fires and Persistent Thermal Sources

Geospatial AI Backend using NASA FIRMS, OpenStreetMap (OSM) Infrastructure & Copernicus Land Cover.

## API Endpoints
- `GET /` - Interactive Map Visualizer & GIS Dashboard
- `GET /predict` & `POST /predict` - Real-time AI Thermal Source Classification & Confidence Engine
- `GET /predictions.csv` - Export predictions CSV dataset for Leaflet Map / PapaParse
- `GET /api/v1/health` - System health check & model status
- `GET /api/v1/alerts` - Active industrial fire risk alerts

Developed for Smart India Hackathon (SIH).