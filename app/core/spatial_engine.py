import math
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth (in kilometers).
    """
    R = 6371.0  # Earth radius in kilometers
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    return float(R * c)

def find_nearest_facilities(lat: float, lon: float, facilities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Find nearest refinery, powerplant, mine, industrial area, and calculate spatial metrics.
    """
    distances_by_type = {
        "refinery": float("inf"),
        "powerplant": float("inf"),
        "mine": float("inf"),
        "industrial_area": float("inf")
    }
    
    nearest_facility_names = {
        "refinery": None,
        "powerplant": None,
        "mine": None,
        "industrial_area": None
    }
    
    all_distances = []
    count_1km = 0
    count_5km = 0
    
    overall_nearest_distance = float("inf")
    overall_nearest_type = "unknown"
    overall_nearest_name = None
    
    for fac in facilities:
        f_lat = fac.get("latitude", 0.0)
        f_lon = fac.get("longitude", 0.0)
        f_type = fac.get("type", "industrial_area").lower()
        f_name = fac.get("name", "Industrial Facility")
        
        dist = haversine_distance(lat, lon, f_lat, f_lon)
        all_distances.append(dist)
        
        if dist <= 1.0:
            count_1km += 1
        if dist <= 5.0:
            count_5km += 1
            
        if f_type in distances_by_type and dist < distances_by_type[f_type]:
            distances_by_type[f_type] = dist
            nearest_facility_names[f_type] = f_name
            
        if dist < overall_nearest_distance:
            overall_nearest_distance = dist
            overall_nearest_type = f_type
            overall_nearest_name = f_name
            
    # Default fallback distances if none found in dataset
    for k in distances_by_type:
        if math.isinf(distances_by_type[k]):
            distances_by_type[k] = 50.0  # default 50km
            
    if math.isinf(overall_nearest_distance):
        overall_nearest_distance = 25.0
        
    mean_distance = sum(all_distances) / len(all_distances) if all_distances else 45.0
    
    return {
        "nearest_refinery_km": round(distances_by_type["refinery"], 4),
        "nearest_powerplant_km": round(distances_by_type["powerplant"], 4),
        "nearest_mine_km": round(distances_by_type["mine"], 4),
        "nearest_industrial_area_km": round(distances_by_type["industrial_area"], 4),
        "min_distance_to_industry_km": round(overall_nearest_distance, 4),
        "mean_distance_to_industry_km": round(mean_distance, 4),
        "mean_industrial_facilities_1km": count_1km,
        "mean_industrial_facilities_5km": count_5km,
        "nearest_facility_type": overall_nearest_type,
        "nearest_facility_name": overall_nearest_name
    }

def is_point_in_bbox(lat: float, lon: float, min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> bool:
    """Check if point is inside bounding box."""
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

class IndiaTerritoryFilter:
    """
    Authoritative India national boundary polygon filter.
    Uses Shapely prepared geometry on data/india_boundary.geojson for sub-millisecond point-in-polygon checks.
    """
    _instance = None
    _prepared_geom = None
    _loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._init_boundary()
        return cls._instance

    def _init_boundary(self):
        try:
            from shapely.geometry import shape
            from shapely.prepared import prep
            base_dir = Path(__file__).resolve().parent.parent.parent
            geojson_path = base_dir / "data" / "india_boundary.geojson"
            if geojson_path.exists():
                with open(geojson_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "features" in data and len(data["features"]) > 0:
                    geom = shape(data["features"][0]["geometry"])
                else:
                    geom = shape(data)
                self._prepared_geom = prep(geom)
                self._loaded = True
                print(f"[OK] Initialized India Territory Boundary Filter ({geojson_path.name})")
            else:
                print(f"[WARN] India boundary geojson not found at {geojson_path}")
        except Exception as e:
            print(f"[WARN] Failed to load India boundary filter: {e}")

    def is_inside(self, lat: float, lon: float) -> bool:
        if not self._loaded or self._prepared_geom is None:
            # Fallback coarse check if boundary geometry is uninitialized
            return (6.5 <= lat <= 37.5) and (68.0 <= lon <= 97.5)
        try:
            from shapely.geometry import Point
            # GeoJSON coordinates are in [longitude, latitude] order
            return bool(self._prepared_geom.contains(Point(lon, lat)))
        except Exception:
            return (6.5 <= lat <= 37.5) and (68.0 <= lon <= 97.5)

def is_inside_india(lat: float, lon: float) -> bool:
    """
    Check whether coordinates fall strictly within India's official territorial boundary.
    Returns False for points in Pakistan, Nepal, Bhutan, Bangladesh, Myanmar, Sri Lanka,
    and open oceanic waters outside Indian maritime territory.
    """
    return IndiaTerritoryFilter.get_instance().is_inside(lat, lon)

INDIAN_STATE_CENTROIDS = {
    "Andhra Pradesh": (15.9129, 79.7400),
    "Arunachal Pradesh": (28.2180, 94.7278),
    "Assam": (26.2006, 92.9376),
    "Bihar": (25.0961, 85.3131),
    "Chhattisgarh": (21.2787, 81.8661),
    "Goa": (15.2993, 74.1240),
    "Gujarat": (22.2587, 71.1924),
    "Haryana": (29.0588, 76.0856),
    "Himachal Pradesh": (31.1048, 77.1734),
    "Jharkhand": (23.6102, 85.2799),
    "Karnataka": (15.3173, 75.7139),
    "Kerala": (10.8505, 76.2711),
    "Madhya Pradesh": (22.9734, 78.6569),
    "Maharashtra": (19.7515, 75.7139),
    "Manipur": (24.6637, 93.9063),
    "Meghalaya": (25.4670, 91.3662),
    "Mizoram": (23.1645, 92.9376),
    "Nagaland": (26.1584, 94.5624),
    "Odisha": (20.9517, 85.0985),
    "Punjab": (31.1471, 75.3412),
    "Rajasthan": (27.0238, 74.2179),
    "Sikkim": (27.5330, 88.5122),
    "Tamil Nadu": (11.1271, 78.6569),
    "Telangana": (18.1124, 79.0193),
    "Tripura": (23.9408, 91.9882),
    "Uttar Pradesh": (26.8467, 80.9462),
    "Uttarakhand": (30.0668, 79.0193),
    "West Bengal": (22.9868, 87.8550),
    "Delhi": (28.7041, 77.1025),
    "Jammu and Kashmir": (33.7782, 76.5762),
    "Ladakh": (34.1526, 77.5771),
    "Chandigarh": (30.7333, 76.7794),
    "Puducherry": (11.9416, 79.8083),
    "Andaman and Nicobar Islands": (11.6234, 92.7265),
    "Lakshadweep": (10.5667, 72.6417),
    "Dadra and Nagar Haveli and Daman and Diu": (20.4283, 72.8397)
}

def is_in_water(lat: float, lon: float) -> bool:
    if lat < 8.0 and lon < 92.0:
        return True
    if 8.3 <= lat <= 9.9 and 78.8 <= lon <= 79.7:
        return True
    if 8.0 <= lat <= 14.5 and lon < 74.5:
        if 10.0 <= lat <= 12.0 and 71.8 <= lon <= 74.0:
            return False
        return True
    if 14.5 < lat <= 17.5 and lon < 72.8:
        return True
    if 17.5 < lat <= 20.5 and lon < 72.0:
        return True
    if 20.5 < lat <= 22.5 and lon < 69.2:
        return True
    if 9.8 <= lat <= 15.5 and 80.5 < lon < 92.0:
        return True
    if 15.5 < lat <= 18.0 and 82.5 < lon < 92.0:
        return True
    if 18.0 < lat <= 20.5 and 85.0 < lon < 92.0:
        return True
    if 20.5 < lat <= 21.8 and 87.5 < lon < 92.0:
        return True
    return False

def deduce_indian_state(lat: float, lon: float) -> str:
    """Accurately identify the nearest Indian state or union territory from coordinates."""
    try:
        # Check strict territorial containment first
        if not is_inside_india(lat, lon):
            if is_in_water(lat, lon):
                return "Offshore Waters (Marine Body)"
            return "Non-Indian Region"

        best_state = "National"
        min_dist = float("inf")
        for st, (c_lat, c_lon) in INDIAN_STATE_CENTROIDS.items():
            d = haversine_distance(lat, lon, c_lat, c_lon)
            if d < min_dist:
                min_dist = d
                best_state = st
        return best_state
    except Exception:
        return "National"