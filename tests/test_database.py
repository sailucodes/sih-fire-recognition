import unittest
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.db.database import db_manager
from app.services.auth_service import auth_service
from app.services.storage_service import storage_service
from app.services.alert_dispatcher_service import alert_dispatcher_service
from app.api.router import router

class TestSQLiteDatabaseIntegration(unittest.TestCase):
    def test_database_file_and_schema_initialization(self):
        self.assertTrue(os.path.exists(db_manager.db_path), "Database file thermal_intel.db must exist on disk.")
        self.assertGreaterEqual(db_manager.count_sources(), 563, "Database must have at least 563 baseline sources indexed.")
        self.assertGreaterEqual(db_manager.count_users(), 2, "Database must have at least 2 default seeded users.")

    def test_user_authentication_flow(self):
        # 1. Test seeded admin login
        admin_login = auth_service.login("admin@sih.gov.in", "Admin@123")
        self.assertTrue(admin_login["success"])
        self.assertEqual(admin_login["user"]["role"], "National Authority")
        self.assertTrue("token" in admin_login)

        # 2. Test user registration
        test_email = f"test_officer_{os.getpid()}@ndma.gov.in"
        reg_res = auth_service.register(test_email, "Password@123", name="Regional Officer", role="State Emergency Analyst")
        self.assertTrue(reg_res["success"])
        
        # 3. Test duplicate registration prevention
        dup_res = auth_service.register(test_email, "OtherPassword@123")
        self.assertFalse(dup_res["success"])

        # 4. Test login with newly registered user
        user_login = auth_service.login(test_email, "Password@123")
        self.assertTrue(user_login["success"])
        self.assertEqual(user_login["user"]["name"], "Regional Officer")

        # 5. Test token verification
        verified_user = auth_service.verify_token(user_login["token"])
        self.assertIsNotNone(verified_user)
        self.assertEqual(verified_user["email"].lower(), test_email.lower())

    def test_thermal_source_sqlite_persistence(self):
        source_id = f"TEST_SOURCE_{os.getpid()}"
        source_obj = {
            "source_id": source_id,
            "state": "Odisha",
            "latitude": 20.9517,
            "longitude": 85.0985,
            "event_type": "Industrial",
            "predicted_event_type": "Industrial",
            "confidence": 92.5,
            "confidence_pct": 92.5,
            "persistence_score": 85.0,
            "sih_alert_severity": "CRITICAL",
            "total_detections": 12,
            "active_days": 5,
            "observation_span_days": 7,
            "mean_frp": 45.0,
            "max_frp": 62.0,
            "mean_brightness": 365.0,
            "max_brightness": 380.0,
            "nearest_facility_name": "Paradeep Refinery Complex",
            "nearest_facility_type": "refinery",
            "min_distance_to_industry_km": 0.8,
            "landcover_class": "Industrial",
            "is_persistent": True,
            "is_flare_anomaly": False,
            "risk_level": "Critical",
            "risk_description": "Persistent high FRP anomaly within 1km of oil refinery.",
            "marker_color": "#e63946"
        }

        # Save via storage service
        saved_id = storage_service.save_new_source(source_obj)
        self.assertEqual(saved_id, source_id)

        # Query directly from SQLite
        db_record = db_manager.get_source(source_id)
        self.assertIsNotNone(db_record)
        self.assertEqual(db_record["source_id"], source_id)
        self.assertEqual(db_record["state"], "Odisha")
        self.assertEqual(db_record["predicted_event_type"], "Industrial")
        self.assertEqual(db_record["sih_alert_severity"], "CRITICAL")
        self.assertAlmostEqual(db_record["confidence_pct"], 92.5)

    def test_alert_dispatch_sqlite_persistence(self):
        initial_count = db_manager.count_dispatches()
        res = alert_dispatcher_service.dispatch_brief(
            state="Jharkhand",
            critical_count=3,
            high_count=8,
            officer_email="commander.ranchi@ndma.gov.in"
        )
        self.assertTrue(res["success"])
        new_count = db_manager.count_dispatches()
        self.assertEqual(new_count, initial_count + 1)

        dispatches = db_manager.list_dispatches(limit=5)
        self.assertGreater(len(dispatches), 0)
        self.assertEqual(dispatches[0]["jurisdiction"], "Jharkhand")
        self.assertEqual(dispatches[0]["critical_events_count"], 3)

    def test_health_check_sqlite_reporting(self):
        status, _, content = router.handle_request("GET", "/api/v1/health", {}, b"")
        self.assertEqual(status, 200)
        health = json.loads(content.decode("utf-8"))
        self.assertEqual(health["status"], "healthy")
        self.assertIn("SQLite", health.get("database_engine", ""))
        self.assertGreaterEqual(health.get("sqlite_thermal_sources_count", 0), 563)
        self.assertGreaterEqual(health.get("sqlite_users_count", 0), 2)

if __name__ == "__main__":
    unittest.main()
