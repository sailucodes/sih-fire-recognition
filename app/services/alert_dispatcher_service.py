import time
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from app.db.database import db_manager

class AlertDispatcherService:
    def __init__(self):
        self.dispatches: List[Dict[str, Any]] = []
        self._load_dispatches()

    def _load_dispatches(self):
        self.dispatches = db_manager.list_dispatches(limit=100)

    def dispatch_brief(self, state: str = "National", critical_count: int = 0, high_count: int = 0, officer_email: str = "authority@ndma.gov.in") -> Dict[str, Any]:
        count = db_manager.count_dispatches()
        dispatch_id = f"NDMA-SIH-2026-{count + 1:04d}"
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

        db_manager.insert_dispatch(record)
        self.dispatches.insert(0, record)

        return {
            "success": True,
            "dispatch_id": dispatch_id,
            "message": f"Dispatched Urgent Incident Brief ({critical_count} Critical Anomalies in {state}) to NDMA Desk.",
            "record": record
        }

    def list_dispatches(self, limit: int = 50) -> List[Dict[str, Any]]:
        return db_manager.list_dispatches(limit=limit)

alert_dispatcher_service = AlertDispatcherService()

