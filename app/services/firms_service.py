import os
import requests
import datetime
from typing import List, Dict, Any, Optional

class NASAFIRMSService:
    def __init__(self, api_key: Optional[str] = None):
        # Support both NASA_FIRMS_MAP_KEY and NASA_FIRMS_API_KEY environment variables
        self.api_key = api_key or os.environ.get("NASA_FIRMS_MAP_KEY") or os.environ.get("NASA_FIRMS_API_KEY")

    def fetch_live_hotspots(self, country_code: str = "IND", days: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch real-time active fire anomalies from NASA FIRMS VIIRS / MODIS.
        Requires a valid NASA FIRMS MAP_KEY via environment variable or constructor.
        Does NOT silently fall back to simulated data when key is missing or request fails.
        """
        api_key = self.api_key or os.environ.get("NASA_FIRMS_MAP_KEY") or os.environ.get("NASA_FIRMS_API_KEY")
        if not api_key or api_key.strip() in ["", "DEMO_KEY"]:
            raise ValueError(
                "NASA FIRMS MAP_KEY is not configured. Please set the 'NASA_FIRMS_MAP_KEY' "
                "(or 'NASA_FIRMS_API_KEY') environment variable with a valid Earthdata MAP_KEY "
                "from https://firms.modaps.eosdis.nasa.gov/api/map_key/."
            )

        url = f"https://firms.modaps.eosdis.nasa.gov/api/country/csv/{api_key.strip()}/VIIRS_SNPP_NRT/{country_code}/{days}"
        try:
            resp = requests.get(url, timeout=15)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to connect to NASA FIRMS API ({url}): {e}")

        if resp.status_code != 200:
            raise RuntimeError(
                f"NASA FIRMS API returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        if "latitude" not in resp.text:
            raise RuntimeError(
                f"Invalid response from NASA FIRMS API. Expected CSV with 'latitude', got: {resp.text[:200]}"
            )

        lines = resp.text.strip().split("\n")
        header = [c.strip() for c in lines[0].split(",")]
        results = []
        for row in lines[1:]:
            vals = [v.strip() for v in row.split(",")]
            if len(vals) == len(header):
                d = dict(zip(header, vals))
                results.append({
                    "latitude": float(d.get("latitude", 0)),
                    "longitude": float(d.get("longitude", 0)),
                    "frp": float(d.get("frp", 5.0) or 5.0),
                    "brightness": float(d.get("bright_ti4", 320.0) or 320.0),
                    "acq_date": d.get("acq_date", datetime.date.today().isoformat()),
                    "acq_time": d.get("acq_time", "1200"),
                    "satellite": "VIIRS",
                    "confidence": d.get("confidence", "nominal"),
                    "daynight": d.get("daynight", "D")
                })

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