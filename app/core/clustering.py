from typing import List, Dict, Any
from collections import defaultdict
import datetime
from app.core.spatial_engine import haversine_distance

def cluster_firms_hotspots(hotspots: List[Dict[str, Any]], eps_km: float = 1.5) -> List[Dict[str, Any]]:
    """
    Cluster raw NASA FIRMS hotspots into distinct thermal sources using spatial adjacency
    and calculate temporal persistence metrics.
    """
    if not hotspots:
        return []
        
    clusters = []
    visited = set()
    
    for i, h in enumerate(hotspots):
        if i in visited:
            continue
            
        cluster_members = [h]
        visited.add(i)
        
        # Grow cluster with nearby hotspots
        for j, other in enumerate(hotspots):
            if j in visited:
                continue
                
            dist = haversine_distance(
                h.get("latitude", 0.0), h.get("longitude", 0.0),
                other.get("latitude", 0.0), other.get("longitude", 0.0)
            )
            
            if dist <= eps_km:
                visited.add(j)
                cluster_members.append(other)
                
        clusters.append(cluster_members)
        
    # Aggregate cluster statistics into Thermal Sources
    thermal_sources = []
    
    for idx, member_list in enumerate(clusters, start=1):
        total_detections = len(member_list)
        lats = [m.get("latitude", 0.0) for m in member_list]
        lons = [m.get("longitude", 0.0) for m in member_list]
        frps = [float(m.get("frp", 5.0) or 5.0) for m in member_list]
        dates = [m.get("acq_date", "2026-08-20") for m in member_list]
        
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        
        mean_frp = sum(frps) / len(frps)
        max_frp = max(frps)
        
        # Unique active days
        unique_days = sorted(list(set(dates)))
        active_days = len(unique_days)
        
        first_detection = min(dates) if dates else "2026-08-19"
        last_detection = max(dates) if dates else "2026-08-25"
        
        # Date span calculation
        try:
            d_start = datetime.datetime.strptime(first_detection[:10], "%Y-%m-%d")
            d_end = datetime.datetime.strptime(last_detection[:10], "%Y-%m-%d")
            span_days = max(1, (d_end - d_start).days + 1)
        except Exception:
            span_days = max(1, active_days)
            
        recurrence_rate = round(active_days / max(span_days, 7), 4)
        detections_per_span_day = round(total_detections / max(span_days, 1), 2)
        
        # Gaps calculation
        gap_hours_list = []
        if len(unique_days) > 1:
            for d1, d2 in zip(unique_days[:-1], unique_days[1:]):
                try:
                    dt1 = datetime.datetime.strptime(d1[:10], "%Y-%m-%d")
                    dt2 = datetime.datetime.strptime(d2[:10], "%Y-%m-%d")
                    gap_hours_list.append((dt2 - dt1).total_seconds() / 3600.0)
                except Exception:
                    pass
                    
        mean_gap_hours = sum(gap_hours_list) / len(gap_hours_list) if gap_hours_list else 0.0
        
        temporal_regularity = 1.0 if active_days >= 3 and span_days >= 3 else 0.0
        
        source_record = {
            "source_id": f"SOURCE_{idx:04d}",
            "latitude": round(center_lat, 5),
            "longitude": round(center_lon, 5),
            "total_detections": total_detections,
            "active_days": active_days,
            "mean_frp": round(mean_frp, 2),
            "max_frp": round(max_frp, 2),
            "first_detection": f"{first_detection} 00:00:00+00:00",
            "last_detection": f"{last_detection} 00:00:00+00:00",
            "observation_span_days": span_days,
            "recurrence_rate": recurrence_rate,
            "detections_per_span_day": detections_per_span_day,
            "mean_gap_hours": round(mean_gap_hours, 2),
            "temporal_regularity": temporal_regularity,
            "max_active_days_7d": min(active_days, 7),
            "max_active_days_14d": min(active_days, 14),
            "max_active_days_30d": min(active_days, 30),
            "observation_days": span_days
        }
        
        thermal_sources.append(source_record)
        
    return thermal_sources