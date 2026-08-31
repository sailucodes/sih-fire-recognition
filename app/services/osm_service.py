import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
INFRA_PATH = BASE_DIR / "data" / "industrial_infrastructure.json"

class OSMInfrastructureService:
    def __init__(self):
        self.facilities: List[Dict[str, Any]] = []
        self._load_facilities()

    def _load_facilities(self):
        if os.path.exists(INFRA_PATH):
            with open(INFRA_PATH, "r", encoding="utf-8") as f:
                self.facilities = json.load(f)
            print(f"[OK] Loaded {len(self.facilities)} OSM industrial infrastructure facilities")
        else:
            self.facilities = []

    def get_all_facilities(self) -> List[Dict[str, Any]]:
        return self.facilities

    def get_geojson(self) -> Dict[str, Any]:
        """Convert infrastructure into GeoJSON FeatureCollection for Map Overlays."""
        features = []
        for fac in self.facilities:
            f_type = fac.get("type", "industrial_area")
            # Assign map styling colors
            color_map = {
                "refinery": "#d90429",
                "powerplant": "#f77f00",
                "mine": "#6c757d",
                "industrial_area": "#7209b7"
            }
            marker_color = color_map.get(f_type, "#3a0ca3")

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [fac["longitude"], fac["latitude"]]
                },
                "properties": {
                    "id": fac["id"],
                    "name": fac["name"],
                    "type": f_type,
                    "state": fac.get("state", ""),
                    "country": fac.get("country", "India"),
                    "risk_category": fac.get("risk_category", "Industrial"),
                    "capacity": fac.get("capacity", "N/A"),
                    "marker_color": marker_color
                }
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

# Global singleton
osm_service = OSMInfrastructureService()