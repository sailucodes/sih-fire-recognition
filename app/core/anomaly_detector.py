from typing import Dict, Any, Tuple

def evaluate_thermal_risk(
    predicted_type: str,
    min_dist_industry_km: float,
    mean_frp: float,
    max_frp: float,
    active_days: int,
    total_detections: int
) -> Tuple[str, bool, str]:
    """
    Evaluate industrial hazard risk and detect sudden flaring surges / industrial fire anomalies.
    Returns (risk_level, is_flare_anomaly, description).
    """
    is_flare_anomaly = False
    
    # Check for intense industrial spike
    if predicted_type == "Industrial":
        if min_dist_industry_km <= 2.0 and max_frp >= 100.0:
            return "Critical", True, "CRITICAL: Extreme thermal output (>100 MW) near critical industrial facility! Potential explosion or major uncontrolled flare."
        elif min_dist_industry_km <= 3.0 and max_frp >= 35.0:
            return "High", True, "HIGH RISK: Severe thermal anomaly detected near refinery/petrochemical plant."
        elif active_days >= 3 or total_detections >= 5:
            return "Medium", False, "MONITORED: Persistent industrial thermal signature (routine flaring / kiln / furnace operations)."
        else:
            return "Low", False, "LOW: Intermittent industrial thermal detection."
            
    elif predicted_type == "Forest/Natural":
        if max_frp >= 50.0:
            return "High", False, "HIGH RISK: Large natural / forest wildfire with high radiative intensity."
        else:
            return "Medium", False, "MODERATE: Natural vegetation / forest surface fire."
            
    elif predicted_type == "Agricultural":
        if max_frp >= 30.0:
            return "Medium", False, "MODERATE: Intensive seasonal crop residue / stubble burning."
        else:
            return "Low", False, "LOW: Routine agricultural burn activity."
            
    else:
        return "Low", False, "LOW: Unclassified or low-intensity thermal source."