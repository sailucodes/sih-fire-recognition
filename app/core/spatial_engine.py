import math
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