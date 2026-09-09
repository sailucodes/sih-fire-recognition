import unittest
import json
from app.services.auth_service import auth_service
from app.services.language_service import language_service
from app.services.voice_service import voice_service
from app.services.alert_dispatcher_service import alert_dispatcher_service
from app.services.storage_service import storage_service
from app.api.router import router

class TestV2BackendFeatures(unittest.TestCase):

    def test_authentication(self):
        # Test Default Admin Login
        login_res = auth_service.login("admin@sih.gov.in", "Admin@123")
        self.assertTrue(login_res["success"])
        self.assertIn("token", login_res)

        # Test New Registration (Idempotent)
        import time
        test_email = f"test_officer_{int(time.time()*1000)}@gov.in"
        reg_res = auth_service.register(test_email, "Password@123", "Odisha EOC Officer")
        self.assertTrue(reg_res["success"])
        self.assertIn("token", reg_res)

        # Test Token Verification
        user = auth_service.verify_token(reg_res["token"])
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], test_email)

    def test_voice_nlp_intents(self):
        # English State Intent
        res_en = voice_service.process_voice_command("show odisha thermal hotspots", "en-US")
        self.assertEqual(res_en["intent"], "FILTER_STATE")
        self.assertEqual(res_en["params"]["state"], "Odisha")

        # Hindi State Intent
        res_hi = voice_service.process_voice_command("ओडिशा दिखाओ", "hi-IN")
        self.assertEqual(res_hi["intent"], "FILTER_STATE")
        self.assertEqual(res_hi["params"]["state"], "Odisha")

        # Telugu State Intent
        res_te = voice_service.process_voice_command("ఒడిశా చూపించు", "te-IN")
        self.assertEqual(res_te["intent"], "FILTER_STATE")
        self.assertEqual(res_te["params"]["state"], "Odisha")

        # Fire Classification Intent
        res_fire = voice_service.process_voice_command("filter industrial fires", "en-US")
        self.assertEqual(res_fire["intent"], "FILTER_TYPE")
        self.assertEqual(res_fire["params"]["event_type"], "Industrial")

        # Dispatch Alert Intent
        res_alert = voice_service.process_voice_command("send alert to ndma", "en-US")
        self.assertEqual(res_alert["intent"], "DISPATCH_ALERT")

    def test_multilingual_translations(self):
        langs = language_service.get_supported_languages()
        self.assertIn("hi-IN", langs["languages"])
        self.assertIn("te-IN", langs["languages"])

        trans_te = language_service.get_translations("te-IN")
        self.assertEqual(trans_te["lang"], "te-IN")
        self.assertIn("appHeading", trans_te["translations"])

    def test_alert_dispatcher(self):
        disp = alert_dispatcher_service.dispatch_brief("Odisha", critical_count=5, high_count=12)
        self.assertTrue(disp["success"])
        self.assertTrue(disp["dispatch_id"].startswith("NDMA-SIH-2026-"))
        self.assertGreaterEqual(len(alert_dispatcher_service.list_dispatches()), 1)

    def test_dual_csv_and_prediction(self):
        # Test Event Classification CSV
        code, headers, body = router.handle_request("GET", "/event_classification_features.csv", {}, b"")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/csv")
        self.assertIn(b"source_id", body)

        # Test Source Persistence CSV
        code, headers, body = router.handle_request("GET", "/source_persistence_features.csv", {}, b"")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/csv")
        self.assertIn(b"persistence_score", body)

        # Test Prediction API with State and Persistence
        payload = json.dumps({
            "latitude": 29.4614,
            "longitude": 76.8636,
            "mean_frp": 45.0,
            "state": "Odisha",
            "active_days": 10,
            "observation_span": 20
        }).encode("utf-8")

        code, headers, body = router.handle_request("POST", "/predict", {}, payload)
        self.assertEqual(code, 200)
        resp = json.loads(body.decode("utf-8"))
        self.assertEqual(resp["predicted_event_type"], "Industrial")
        self.assertGreaterEqual(resp["confidence_pct"], 70.0)
        self.assertEqual(resp["state"], "Odisha")
        self.assertEqual(resp["persistence_score"], 50.0)

if __name__ == "__main__":
    unittest.main()
