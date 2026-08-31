import unittest
import json
import os
import sys
from pathlib import Path

# Add root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.api.router import router

class TestAPIRoutes(unittest.TestCase):
    def test_health_endpoint(self):
        status, headers, content = router.handle_request("GET", "/api/v1/health", {}, b"")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertEqual(data["status"], "healthy")
        self.assertIn("Industrial", data["model_classes"])

    def test_sources_and_geojson_endpoints(self):
        status, _, content = router.handle_request("GET", "/api/v1/sources", {"limit": ["10"]}, b"")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertGreater(data["count"], 0)

        status, _, content_geo = router.handle_request("GET", "/api/v1/sources/geojson", {"event_type": ["Industrial"]}, b"")
        self.assertEqual(status, 200)
        geojson = json.loads(content_geo.decode("utf-8"))
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertIsInstance(geojson["features"], list)
        if len(geojson["features"]) > 0:
            first = geojson["features"][0]
            self.assertEqual(first["type"], "Feature")
            self.assertEqual(first["geometry"]["type"], "Point")
            self.assertEqual(first["properties"]["predicted_event_type"], "Industrial")

    def test_on_demand_classification(self):
        payload = json.dumps({
            "latitude": 29.46148,
            "longitude": 76.86364,
            "frp": 25.0,
            "active_days": 3
        }).encode("utf-8")
        status, _, content = router.handle_request("POST", "/api/v1/classify", {}, payload)
        self.assertEqual(status, 200)
        res = json.loads(content.decode("utf-8"))
        self.assertEqual(res["predicted_event_type"], "Industrial")
        self.assertIn("probabilities", res)

    def test_analytics_and_alerts(self):
        status, _, content = router.handle_request("GET", "/api/v1/analytics/summary", {}, b"")
        self.assertEqual(status, 200)
        analytics = json.loads(content.decode("utf-8"))
        self.assertIn("total_thermal_sources", analytics)
        self.assertIn("industrial_percentage", analytics)

        status_alt, _, content_alt = router.handle_request("GET", "/api/v1/alerts", {}, b"")
        self.assertEqual(status_alt, 200)
        alerts = json.loads(content_alt.decode("utf-8"))
        self.assertIsInstance(alerts["alerts"], list)

if __name__ == "__main__":
    unittest.main()