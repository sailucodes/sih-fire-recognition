import time
import json
import os
from pathlib import Path
from typing import Dict, Any, List

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DISPATCH_LOG_FILE = DATA_DIR / "dispatched_alerts.json"

class AlertDispatcherService:
    def __init__(self):
        self.dispatches: List[Dict[str, Any]] = []
        self._load_dispatches()

    def _load_dispatches(self):
        if os.path.exists(DISPATCH_LOG_FILE):
            try:
                with open(DISPATCH_LOG_FILE, "r", encoding="utf-8") as f:
                    self.dispatches = json.load(f)
            except Exception:
                self.dispatches = []

    def _save_dispatches(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DISPATCH_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.dispatches, f, indent=2)

    def dispatch_brief(self, state: str = "National", critical_count: int = 0, high_count: int = 0, officer_email: str = "authority@ndma.gov.in") -> Dict[str, Any]:
        dispatch_id = f"NDMA-SIH-2026-{len(self.dispatches) + 1:04d}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC")

        record = {
            "dispatch_id": dispatch_id,
            "timestamp": timestamp,
            "target_agency": "National Disaster Management Authority (NDMA) & State EOC",
            "jurisdiction": state,
            "summary": f"Urgent Incident Brief: {critical_count} Critical & {high_count} High-Risk Anomalies detected in {state}.",
            "dispatched_by": officer_email,
            "critical_events_count": critical_count,
            "high_events_count": high_count,
            "status": "DISPATCHED_TO_NDMA_DESK",
            "priority": "P1-CRITICAL" if critical_count > 0 else "P2-ELEVATED",
            "recommended_action": "Deploy State Rapid Action Fire Squads & verify industrial perimeter."
        }

        self.dispatches.insert(0, record)
        self._save_dispatches()

        return {
            "success": True,
            "dispatch_id": dispatch_id,
            "message": f"Dispatched Urgent Incident Brief ({critical_count} Critical Anomalies in {state}) to NDMA Desk.",
            "record": record
        }

    def list_dispatches(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.dispatches[:limit]

alert_dispatcher_service = AlertDispatcherService()
