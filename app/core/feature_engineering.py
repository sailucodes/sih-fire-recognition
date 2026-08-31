from typing import Dict, Any, List
from app.core.spatial_engine import find_nearest_facilities

LANDCOVER_MAP = {
    10: ("Tree cover", 0.0, 1.0, 0.0),
    20: ("Shrubland", 0.0, 0.0, 0.0),
    30: ("Grassland", 0.0, 0.0, 0.0),
    40: ("Cropland", 0.0, 0.0, 1.0),
    50: ("Built-up", 1.0, 0.0, 0.0),
    60: ("Bare / sparse vegetation", 1.0, 0.0, 0.0),
    80: ("Permanent water bodies", 0.0, 0.0, 0.0),
    90: ("Herbaceous wetland", 0.0, 0.0, 0.0),
    95: ("Mangroves", 1.0, 1.0, 0.0),
}

def infer_landcover(lat: float, lon: float, nearest_facility_dist_km: float, explicit_class: str = None) -> Dict[str, Any]:
    if explicit_class:
        for code, (c_name, ind_r, for_r, ag_r) in LANDCOVER_MAP.items():
            if c_name.lower() in explicit_class.lower():
                return {
                    "landcover_code": code,
                    "landcover_class": c_name,
                    "industrial_land_ratio": ind_r,
                    "forest_land_ratio": for_r,
                    "agricultural_land_ratio": ag_r
                }
                
    if nearest_facility_dist_km <= 1.0:
        return {
            "landcover_code": 50,
            "landcover_class": "Built-up",
            "industrial_land_ratio": 1.0,
            "forest_land_ratio": 0.0,
            "agricultural_land_ratio": 0.0
        }
    elif nearest_facility_dist_km <= 3.0:
        return {
            "landcover_code": 60,
            "landcover_class": "Bare / sparse vegetation",
            "industrial_land_ratio": 1.0,
            "forest_land_ratio": 0.0,
            "agricultural_land_ratio": 0.0
        }
    else:
        return {
            "landcover_code": 40,
            "landcover_class": "Cropland",
            "industrial_land_ratio": 0.0,
            "forest_land_ratio": 0.0,
            "agricultural_land_ratio": 1.0
        }

def extract_features_for_point(
    lat: float,
    lon: float,
    frp: float = 5.0,
    max_frp: float = None,
    brightness: float = 330.0,
    max_brightness: float = None,
    detection_count: int = 1,
    active_days: int = 1,
    facilities: List[Dict[str, Any]] = None,
    landcover_class: str = None,
    observation_span_days: int = 1,
    override_nearest_type: str = None,
    override_min_dist: float = None,
    facilities_1km: int = None,
    facilities_5km: int = None
) -> Dict[str, Any]:
    if facilities is None:
        facilities = []
        
    spatial_features = find_nearest_facilities(lat, lon, facilities)
    
    min_dist = override_min_dist if override_min_dist is not None else spatial_features["min_distance_to_industry_km"]
    fac_type = override_nearest_type if override_nearest_type else spatial_features["nearest_facility_type"]
    cnt_1km = facilities_1km if facilities_1km is not None else spatial_features["mean_industrial_facilities_1km"]
    cnt_5km = facilities_5km if facilities_5km is not None else spatial_features["mean_industrial_facilities_5km"]
    peak_frp = max_frp if max_frp is not None else frp

    lc_info = infer_landcover(lat, lon, min_dist, landcover_class)
    
    observation_days = max(1, observation_span_days)
    recurrence_rate = round(active_days / max(observation_days, 7), 4)
    detections_per_span_day = round(detection_count / max(observation_days, 1), 2)
    
    features = {
        "latitude": lat,
        "longitude": lon,
        "nearest_refinery_km": min_dist if fac_type == "refinery" else spatial_features["nearest_refinery_km"],
        "nearest_powerplant_km": min_dist if fac_type == "powerplant" else spatial_features["nearest_powerplant_km"],
        "nearest_mine_km": min_dist if fac_type == "mine" else spatial_features["nearest_mine_km"],
        "nearest_industrial_area_km": min_dist if fac_type == "industrial_area" else spatial_features["nearest_industrial_area_km"],
        "min_distance_to_industry_km": min_dist,
        "mean_distance_to_industry_km": spatial_features["mean_distance_to_industry_km"],
        "mean_industrial_facilities_1km": cnt_1km,
        "mean_industrial_facilities_5km": cnt_5km,
        "landcover_code": lc_info["landcover_code"],
        "landcover_class": lc_info["landcover_class"],
        "industrial_land_ratio": lc_info["industrial_land_ratio"],
        "forest_land_ratio": lc_info["forest_land_ratio"],
        "agricultural_land_ratio": lc_info["agricultural_land_ratio"],
        "nearest_facility_type": fac_type,
        "nearest_facility_name": spatial_features.get("nearest_facility_name"),
        "total_detections": detection_count,
        "active_days": active_days,
        "mean_frp": frp,
        "max_frp": peak_frp,
        "mean_brightness": brightness,
        "max_brightness": max_brightness if max_brightness is not None else brightness,
        "observation_span_days": observation_days,
        "recurrence_rate": recurrence_rate,
        "detections_per_span_day": detections_per_span_day,
        "mean_gap_hours": 0.0 if active_days == 1 else 12.0,
        "std_gap_hours": 0.0,
        "median_gap_hours": 0.0,
        "min_gap_hours": 0.0,
        "max_gap_hours": 24.0 if active_days > 1 else 0.0,
        "temporal_regularity": 1.0 if active_days >= 3 else 0.0,
        "max_active_days_7d": min(active_days, 7),
        "max_active_days_14d": min(active_days, 14),
        "max_active_days_30d": min(active_days, 30),
        "observation_days": observation_days
    }
    
    return features