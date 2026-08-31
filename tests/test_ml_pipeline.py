import unittest
import os
import sys
from pathlib import Path

# Add root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.spatial_engine import haversine_distance, find_nearest_facilities
from app.core.feature_engineering import extract_features_for_point
from app.core.ml_model import ml_engine
from app.core.anomaly_detector import evaluate_thermal_risk
from app.services.osm_service import osm_service

class TestMLPipeline(unittest.TestCase):
    def test_haversine_distance(self):
        dist = haversine_distance(22.34236, 69.87119, 29.46148, 76.86364)
        self.assertTrue(1000.0 < dist < 1200.0, f"Unexpected distance: {dist}")

    def test_feature_engineering_and_classification(self):
        facilities = osm_service.get_all_facilities()
        
        # Test 1: Coordinate right at Jamnagar Refinery (22.34236, 69.87119)
        features_ind = extract_features_for_point(
            lat=22.34236, lon=69.87119, frp=15.0, detection_count=5, active_days=4, facilities=facilities
        )
        self.assertLessEqual(features_ind["min_distance_to_industry_km"], 0.5)
        pred_ind = ml_engine.predict_single(features_ind)
        self.assertEqual(pred_ind["predicted_event_type"], "Industrial")
        self.assertGreater(pred_ind["confidence_pct"], 50.0)

        # Test 2: Wildfire in natural forest coordinates (10.93393, 78.49468)
        features_for = extract_features_for_point(
            lat=10.93393, lon=78.49468, frp=4.0, detection_count=1, active_days=1, facilities=facilities, landcover_class="Tree cover"
        )
        pred_for = ml_engine.predict_single(features_for)
        self.assertEqual(pred_for["predicted_event_type"], "Forest/Natural")

    def test_anomaly_detection(self):
        risk, is_flare, desc = evaluate_thermal_risk(
            predicted_type="Industrial",
            min_dist_industry_km=0.5,
            mean_frp=120.0,
            max_frp=135.0,
            active_days=1,
            total_detections=3
        )
        self.assertEqual(risk, "Critical")
        self.assertTrue(is_flare)

if __name__ == "__main__":
    unittest.main()