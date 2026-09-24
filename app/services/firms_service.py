import os
import requests
import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.core.spatial_engine import is_inside_india

def parse_flexible_datetime(val: str, default_time: str = "00:00") -> datetime.datetime:
    """Parse date or datetime string in various standard formats (ISO, space-separated)."""
    s = str(val).strip().replace("Z", "").replace("T", " ")
    parts = s.split()
    if len(parts) == 1:
        date_part = parts[0]
        time_part = default_time
    else:
        date_part = parts[0]
        time_part = parts[1]
    
    # Ensure time has hour and minute
    time_sub = time_part.split(":")
    h = time_sub[0].zfill(2)
    m = time_sub[1].zfill(2) if len(time_sub) > 1 else "00"
    s_clean = f"{date_part} {h}:{m}"
    
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s_clean, fmt)
        except ValueError:
            continue
    return datetime.datetime.fromisoformat(val)

class NASAFIRMSService:
    def __init__(self, api_key: Optional[str] = None):
        # Support both NASA_FIRMS_MAP_KEY and NASA_FIRMS_API_KEY environment variables
        self.api_key = api_key or os.environ.get("NASA_FIRMS_MAP_KEY") or os.environ.get("NASA_FIRMS_API_KEY")
        self._cache: Dict[str, Tuple[float, List[Dict[str, Any]], Dict[str, Any]]] = {}
        self.last_diagnostics: Dict[str, Any] = {}

    def fetch_live_hotspots(
        self,
        country_code: str = "IND",
        days: int = 1,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        api_key: Optional[str] = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch real-time and historical active fire anomalies from NASA FIRMS VIIRS.
        Supports 1-day, 7-day, 30-day presets as well as custom date/time ranges.
        Applies strict India territorial boundary filtering BEFORE returning hotspots.
        Deduplicates records across multi-chunk queries and provides short-term caching.
        """
        key = api_key or self.api_key or os.environ.get("NASA_FIRMS_MAP_KEY") or os.environ.get("NASA_FIRMS_API_KEY") or "5aefcf72ba6e780e0e43e3e841af34cb"
        if not key or key.strip() in ["", "DEMO_KEY"]:
            raise ValueError(
                "NASA FIRMS MAP_KEY is not configured. Please set the 'NASA_FIRMS_MAP_KEY' "
                "(or 'NASA_FIRMS_API_KEY') environment variable with a valid Earthdata MAP_KEY "
                "from https://firms.modaps.eosdis.nasa.gov/api/map_key/."
            )

        clean_key = key.strip()
        now = datetime.datetime.now()
        today = now.date()

        # Parse date and time boundaries
        is_custom_range = bool(start_datetime)
        if is_custom_range:
            start_dt = parse_flexible_datetime(start_datetime, default_time="00:00")
            end_dt = parse_flexible_datetime(end_datetime, default_time="23:59") if end_datetime else now
            if start_dt > end_dt:
                raise ValueError("start_datetime must be before or equal to end_datetime.")
            start_date = start_dt.date()
            end_date = min(today, end_dt.date())
            days_span = max(1, (end_date - start_date).days + 1)
            requested_days = days_span
        else:
            requested_days = max(1, int(days))
            start_date = today - datetime.timedelta(days=requested_days - 1)
            end_date = today
            start_dt = datetime.datetime.combine(start_date, datetime.time.min)
            end_dt = datetime.datetime.combine(end_date, datetime.time.max)

        # Check cache (valid for 5 minutes)
        cache_key = f"{country_code}_{requested_days}_{start_dt.isoformat()}_{end_dt.isoformat()}"
        now_ts = now.timestamp()
        if not force_refresh and cache_key in self._cache:
            cache_ts, cached_data, cached_diag = self._cache[cache_key]
            if now_ts - cache_ts < 300:
                print(f"[FIRMS] Returning {len(cached_data)} cached hotspots for {cache_key} (age: {int(now_ts - cache_ts)}s)")
                self.last_diagnostics = cached_diag
                return cached_data

        # Default bounding box for India: West: 68.0, South: 6.5, East: 97.5, North: 37.5
        bbox = "68,6.5,97.5,37.5"
        raw_csv_texts = []

        if not is_custom_range and requested_days <= 5:
            # Single chunk request for preset 1..5 days
            endpoints = [
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{clean_key}/VIIRS_SNPP_NRT/{bbox}/{requested_days}",
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{clean_key}/VIIRS_NOAA21_NRT/{bbox}/{requested_days}"
            ]
            resp = None
            last_err = None
            for url in endpoints:
                try:
                    r = requests.get(url, timeout=20)
                    if r.status_code == 200 and "latitude" in r.text:
                        resp = r
                        break
                    elif r.status_code == 200 and "Invalid" in r.text:
                        raise ValueError(f"NASA FIRMS rejected MAP_KEY: {r.text.strip()[:100]}")
                    else:
                        last_err = f"NASA API returned HTTP {r.status_code}: {r.text[:120]}"
                except requests.exceptions.RequestException as e:
                    last_err = str(e)
            if resp is None:
                raise RuntimeError(last_err or "Unable to retrieve hotspot data from NASA FIRMS.")
            raw_csv_texts.append(resp.text)
        else:
            # Multi-chunk request for 7 days, 30 days, or custom date range
            # NASA FIRMS allows chunks of 1..5 days anchored by start date:
            # /api/area/csv/[KEY]/[SOURCE]/[BBOX]/[CHUNK_DAYS]/[START_DATE]
            curr = start_date
            while curr <= end_date:
                days_left = (end_date - curr).days + 1
                chunk_days = min(5, days_left)
                url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{clean_key}/VIIRS_SNPP_NRT/{bbox}/{chunk_days}/{curr}"
                try:
                    r = requests.get(url, timeout=25)
                    if r.status_code == 200 and "latitude" in r.text:
                        raw_csv_texts.append(r.text)
                    elif r.status_code == 200 and "Invalid" in r.text:
                        raise ValueError(f"NASA FIRMS rejected MAP_KEY: {r.text.strip()[:100]}")
                    else:
                        print(f"[FIRMS] Chunk {curr} returned HTTP {r.status_code}: {r.text[:80]}")
                except Exception as ce:
                    print(f"[FIRMS] Chunk {curr} exception: {ce}")
                curr += datetime.timedelta(days=chunk_days)

        if not raw_csv_texts:
            raise RuntimeError("Unable to retrieve historical hotspot data from NASA FIRMS.")

        # Parse, time-filter, deduplicate, and apply strict India territorial boundary
        seen_keys = set()
        results = []
        raw_firms_count = 0
        inside_india_count = 0
        outside_india_removed = 0
        outside_time_window_count = 0

        for csv_text in raw_csv_texts:
            lines = csv_text.strip().split("\n")
            if len(lines) < 2:
                continue
            header = [c.strip() for c in lines[0].split(",")]
            for row in lines[1:]:
                vals = [v.strip() for v in row.split(",")]
                if len(vals) == len(header):
                    d = dict(zip(header, vals))
                    try:
                        lat = float(d.get("latitude", 0))
                        lon = float(d.get("longitude", 0))
                        acq_date = d.get("acq_date", today.isoformat())
                        acq_time = d.get("acq_time", "1200")
                        raw_firms_count += 1

                        # Timestamp filtering for exact time window
                        time_str = str(acq_time).strip().zfill(4)
                        try:
                            det_dt = datetime.datetime.strptime(f"{acq_date} {time_str[:2]}:{time_str[2:]}", "%Y-%m-%d %H:%M")
                            if det_dt < start_dt or det_dt > end_dt:
                                outside_time_window_count += 1
                                continue
                        except Exception:
                            pass

                        # Deduplicate across multiple query chunks
                        dedup_key = (round(lat, 4), round(lon, 4), acq_date, acq_time)
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)

                        # Strict India territorial boundary check BEFORE clustering or returning
                        if not is_inside_india(lat, lon):
                            outside_india_removed += 1
                            continue

                        inside_india_count += 1
                        results.append({
                            "latitude": lat,
                            "longitude": lon,
                            "frp": float(d.get("frp", 5.0) or 5.0),
                            "brightness": float(d.get("bright_ti4", 320.0) or 320.0),
                            "acq_date": acq_date,
                            "acq_time": acq_time,
                            "satellite": d.get("satellite", "VIIRS"),
                            "confidence": d.get("confidence", "nominal"),
                            "daynight": d.get("daynight", "D")
                        })
                    except (ValueError, TypeError):
                        continue

        # Save diagnostics and cache
        diagnostics = {
            "raw_firms_count": raw_firms_count,
            "inside_india_count": inside_india_count,
            "outside_india_removed": outside_india_removed,
            "outside_time_window_count": outside_time_window_count,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "calendar_days_covered": requested_days
        }
        self.last_diagnostics = diagnostics
        self._cache[cache_key] = (now_ts, results, diagnostics)
        print(f"[FIRMS] Sync complete: {raw_firms_count} raw NASA detections -> {inside_india_count} inside India ({outside_india_removed} foreign/offshore discarded)")
        return results

    def _generate_simulated_firms_data(self) -> List[Dict[str, Any]]:
        today_str = datetime.date.today().isoformat()
        yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        
        simulated = [
            # 1. Jamnagar Refinery Flaring (Industrial)
            {"latitude": 22.34236, "longitude": 69.87119, "frp": 18.5, "brightness": 352.0, "acq_date": today_str, "acq_time": "0215", "satellite": "VIIRS", "confidence": "high", "daynight": "N"},
            {"latitude": 22.34120, "longitude": 69.85442, "frp": 12.3, "brightness": 344.0, "acq_date": today_str, "acq_time": "1340", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},
            {"latitude": 22.34210, "longitude": 69.87150, "frp": 14.8, "brightness": 348.0, "acq_date": yesterday_str, "acq_time": "0230", "satellite": "VIIRS", "confidence": "high", "daynight": "N"},

            # 2. Panipat Refinery Flaring (Industrial)
            {"latitude": 29.46148, "longitude": 76.86364, "frp": 25.4, "brightness": 361.0, "acq_date": today_str, "acq_time": "0830", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},
            {"latitude": 29.45857, "longitude": 76.86950, "frp": 42.0, "brightness": 378.0, "acq_date": today_str, "acq_time": "1410", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},
            {"latitude": 29.47378, "longitude": 76.85699, "frp": 16.5, "brightness": 350.0, "acq_date": yesterday_str, "acq_time": "0845", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},

            # 3. Jharia Coal Mine Fire (Industrial / Mine)
            {"latitude": 23.75207, "longitude": 86.41506, "frp": 8.5, "brightness": 332.0, "acq_date": today_str, "acq_time": "0720", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},
            {"latitude": 23.76894, "longitude": 86.40264, "frp": 9.2, "brightness": 335.0, "acq_date": today_str, "acq_time": "1315", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},
            {"latitude": 23.73835, "longitude": 86.43285, "frp": 11.0, "brightness": 338.0, "acq_date": yesterday_str, "acq_time": "0710", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},

            # 4. Western Ghats Wildfire (Forest / Natural)
            {"latitude": 10.93393, "longitude": 78.49468, "frp": 45.2, "brightness": 372.0, "acq_date": today_str, "acq_time": "0915", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},
            {"latitude": 10.93510, "longitude": 78.49620, "frp": 38.0, "brightness": 365.0, "acq_date": today_str, "acq_time": "1450", "satellite": "VIIRS", "confidence": "high", "daynight": "D"},

            # 5. Punjab / Haryana Stubble Burning (Agricultural)
            {"latitude": 30.36296, "longitude": 74.23610, "frp": 18.0, "brightness": 346.0, "acq_date": today_str, "acq_time": "1130", "satellite": "VIIRS", "confidence": "nominal", "daynight": "D"},
            {"latitude": 28.71234, "longitude": 76.83447, "frp": 14.5, "brightness": 341.0, "acq_date": today_str, "acq_time": "1200", "satellite": "VIIRS", "confidence": "nominal", "daynight": "D"},

            # 6. Critical Industrial Flare / Explosion Spike
            {"latitude": 15.76939, "longitude": 73.70415, "frp": 135.5, "brightness": 412.0, "acq_date": today_str, "acq_time": "1530", "satellite": "VIIRS", "confidence": "high", "daynight": "D"}
        ]
        return simulated

# Global singleton
firms_service = NASAFIRMSService()