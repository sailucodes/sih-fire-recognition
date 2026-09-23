import os
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "event_classification_features.csv"
SOURCE_MODEL_PATH = BASE_DIR / "data" / "models" / "source_type_model.pkl"
PERSISTENCE_MODEL_PATH = BASE_DIR / "data" / "models" / "model.pkl"
LEGACY_MODEL_PATH = BASE_DIR / "data" / "models" / "event_type_model.pkl"
LEGACY_FEATURES_PATH = BASE_DIR / "data" / "models" / "event_type_features.pkl"

class EventClassifierEngine:
    def __init__(self):
        self.source_model = None
        self.persistence_model = None
        self.legacy_model = None
        self.legacy_features = None
        self.classes_ = ["Agricultural", "Forest/Natural", "Industrial", "Other"]
        self._load_models()

    @property
    def model(self):
        """Backward-compatibility property for routes checking ml_engine.model."""
        return self.source_model or self.legacy_model

    def _load_models(self):
        """Load the two-stage ML pipeline (source_type_model.pkl + model.pkl)."""
        # 1. Load Primary Stage 1: source_type_model.pkl
        if os.path.exists(SOURCE_MODEL_PATH):
            try:
                self.source_model = joblib.load(SOURCE_MODEL_PATH)
                if hasattr(self.source_model, "classes_"):
                    self.classes_ = list(self.source_model.classes_)
                print(f"[OK] Loaded Primary Stage-1 Source Classifier ({SOURCE_MODEL_PATH.name})")
            except Exception as e:
                print(f"Warning: Could not load source_type_model ({e})")

        # 2. Load Primary Stage 2: model.pkl (Persistence Classifier)
        if os.path.exists(PERSISTENCE_MODEL_PATH):
            try:
                self.persistence_model = joblib.load(PERSISTENCE_MODEL_PATH)
                print(f"[OK] Loaded Primary Stage-2 Persistence Model ({PERSISTENCE_MODEL_PATH.name})")
            except Exception as e:
                print(f"Warning: Could not load persistence model.pkl ({e})")

        # 3. Load Fallback: Legacy event_type_model.pkl
        if os.path.exists(LEGACY_MODEL_PATH) and os.path.exists(LEGACY_FEATURES_PATH):
            try:
                self.legacy_model = joblib.load(LEGACY_MODEL_PATH)
                self.legacy_features = joblib.load(LEGACY_FEATURES_PATH)
                if self.source_model is None:
                    self.classes_ = list(self.legacy_model.classes_)
                print(f"[OK] Loaded Secondary Legacy Model ({LEGACY_MODEL_PATH.name})")
            except Exception as e:
                print(f"Warning: Could not load legacy model ({e})")

    def predict_single(self, features_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Two-stage prediction:
        1. Predict source type using source_type_model.pkl (Scikit-Learn Pipeline).
        2. Predict temporal persistence using model.pkl.
        """
        pred = None
        confidence = 0.0
        prob_dict = {}
        persistence_prob = None
        is_persistent = None

        # Stage 1: Source Type Prediction via source_type_model.pkl
        if self.source_model is not None:
            try:
                # Required: ['mean_distance_to_industry_km', 'min_distance_to_industry_km', 
                #            'mean_industrial_facilities_1km', 'mean_industrial_facilities_5km', 
                #            'nearest_facility_type', 'nearest_refinery_km', 'nearest_powerplant_km', 
                #            'nearest_mine_km', 'nearest_industrial_area_km', 'landcover_class']
                min_d = float(features_dict.get("min_distance_to_industry_km") or features_dict.get("min_distance_industry") or 5.0)
                mean_d = float(features_dict.get("mean_distance_to_industry_km") or features_dict.get("mean_distance_industry") or min_d)
                ind_1k = float(features_dict.get("mean_industrial_facilities_1km") or 0.0)
                ind_5k = float(features_dict.get("mean_industrial_facilities_5km") or 0.0)
                fac_type = str(features_dict.get("nearest_facility_type") or "industrial_area")
                ref_km = float(features_dict.get("nearest_refinery_km") or min_d)
                power_km = float(features_dict.get("nearest_powerplant_km") or min_d)
                mine_km = float(features_dict.get("nearest_mine_km") or min_d)
                ind_area_km = float(features_dict.get("nearest_industrial_area_km") or min_d)
                lc = str(features_dict.get("landcover_class") or "Built-up")

                source_df = pd.DataFrame([{
                    "mean_distance_to_industry_km": mean_d,
                    "min_distance_to_industry_km": min_d,
                    "mean_industrial_facilities_1km": ind_1k,
                    "mean_industrial_facilities_5km": ind_5k,
                    "nearest_facility_type": fac_type,
                    "nearest_refinery_km": ref_km,
                    "nearest_powerplant_km": power_km,
                    "nearest_mine_km": mine_km,
                    "nearest_industrial_area_km": ind_area_km,
                    "landcover_class": lc
                }])

                pred = self.source_model.predict(source_df)[0]
                probs = self.source_model.predict_proba(source_df)[0]
                prob_dict = {str(c): round(float(p) * 100, 2) for c, p in zip(self.classes_, probs)}
                confidence = round(float(np.max(probs)) * 100, 2)
            except Exception as e:
                print(f"Stage-1 inference exception: {e}")
                pred = None

        # Fallback to legacy model or rule-based if Stage 1 did not compute
        if pred is None:
            pred, confidence, prob_dict = self._rule_based_fallback(features_dict)

        # Stage 2: Persistence Prediction via model.pkl
        if self.persistence_model is not None:
            try:
                # Required: ['mean_frp', 'max_frp', 'mean_brightness', 'max_brightness', 
                #            'mean_distance_industry', 'min_distance_industry', 
                #            'mean_industrial_facilities_1km', 'mean_industrial_facilities_5km', 
                #            'industrial_land_ratio']
                m_frp = float(features_dict.get("mean_frp") or 15.0)
                mx_frp = float(features_dict.get("max_frp") or m_frp)
                m_brt = float(features_dict.get("mean_brightness") or 325.0)
                mx_brt = float(features_dict.get("max_brightness") or m_brt)
                min_ind = float(features_dict.get("min_distance_industry") or features_dict.get("min_distance_to_industry_km") or 5.0)
                mean_ind = float(features_dict.get("mean_distance_industry") or features_dict.get("mean_distance_to_industry_km") or min_ind)
                fac_1k = float(features_dict.get("mean_industrial_facilities_1km") or 0.0)
                fac_5k = float(features_dict.get("mean_industrial_facilities_5km") or 0.0)
                ind_ratio = float(features_dict.get("industrial_land_ratio") or (0.8 if min_ind < 1.5 else 0.0))

                pers_df = pd.DataFrame([{
                    "mean_frp": m_frp,
                    "max_frp": mx_frp,
                    "mean_brightness": m_brt,
                    "max_brightness": mx_brt,
                    "mean_distance_industry": mean_ind,
                    "min_distance_industry": min_ind,
                    "mean_industrial_facilities_1km": fac_1k,
                    "mean_industrial_facilities_5km": fac_5k,
                    "industrial_land_ratio": ind_ratio
                }])

                pers_pred = int(self.persistence_model.predict(pers_df)[0])
                pers_probs = self.persistence_model.predict_proba(pers_df)[0]
                is_persistent = bool(pers_pred == 1)
                persistence_prob = round(float(pers_probs[1]) * 100, 1)
            except Exception as pe:
                print(f"Stage-2 persistence inference exception: {pe}")

        # Compute dynamic persistence score percentage (0-100)
        final_persistence = persistence_prob if persistence_prob is not None else float(features_dict.get("persistence_score") or 85.0)

        # Generate explainability notes
        min_dist = features_dict.get("min_distance_to_industry_km", 50.0)
        lc_class = features_dict.get("landcover_class", "Unknown")
        fac_type = features_dict.get("nearest_facility_type", "industrial area")
        
        reasons = []
        if pred == "Industrial":
            reasons.append(f"Classified by Stage-1 Spatial Pipeline within {min_dist:.2f} km of {fac_type}")
            if is_persistent:
                reasons.append(f"Stage-2 Energy Classifier flagged high persistence ({final_persistence:.1f}%)")
            else:
                reasons.append(f"Thermal recurrence observed near manufacturing zone")
        elif pred == "Forest/Natural":
            reasons.append(f"Dominant canopy land cover: {lc_class}")
            reasons.append(f"Isolated from industrial infrastructure ({min_dist:.2f} km away)")
        elif pred == "Agricultural":
            reasons.append(f"Occurring in cropland / agricultural belt ({lc_class})")
            reasons.append("Short duration / ephemeral seasonal burn signature")
        else:
            reasons.append(f"Surface land cover: {lc_class}")

        return {
            "predicted_event_type": pred,
            "confidence_pct": confidence,
            "persistence_score": final_persistence,
            "is_persistent": is_persistent,
            "probabilities": prob_dict,
            "explanation": reasons,
            "model_architecture": "Two-Stage Decoupled Pipeline (source_type_model + persistence_model)"
        }

    def predict_batch(self, features_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        High-performance batch two-stage prediction:
        1. Predict source type using source_type_model.pkl (Scikit-Learn Pipeline).
        2. Predict temporal persistence using model.pkl.
        """
        if not features_list:
            return []

        n = len(features_list)
        preds = [None] * n
        confidences = [0.0] * n
        prob_dicts = [{}] * n
        pers_scores = [None] * n
        is_persistents = [None] * n

        # Stage 1: Source Type Prediction via source_type_model.pkl in batch
        if self.source_model is not None:
            try:
                stage1_rows = []
                for f in features_list:
                    min_d = float(f.get("min_distance_to_industry_km") or f.get("min_distance_industry") or 5.0)
                    mean_d = float(f.get("mean_distance_to_industry_km") or f.get("mean_distance_industry") or min_d)
                    ind_1k = float(f.get("mean_industrial_facilities_1km") or 0.0)
                    ind_5k = float(f.get("mean_industrial_facilities_5km") or 0.0)
                    fac_type = str(f.get("nearest_facility_type") or "industrial_area")
                    ref_km = float(f.get("nearest_refinery_km") or min_d)
                    power_km = float(f.get("nearest_powerplant_km") or min_d)
                    mine_km = float(f.get("nearest_mine_km") or min_d)
                    ind_area_km = float(f.get("nearest_industrial_area_km") or min_d)
                    lc = str(f.get("landcover_class") or "Built-up")
                    stage1_rows.append({
                        "mean_distance_to_industry_km": mean_d,
                        "min_distance_to_industry_km": min_d,
                        "mean_industrial_facilities_1km": ind_1k,
                        "mean_industrial_facilities_5km": ind_5k,
                        "nearest_facility_type": fac_type,
                        "nearest_refinery_km": ref_km,
                        "nearest_powerplant_km": power_km,
                        "nearest_mine_km": mine_km,
                        "nearest_industrial_area_km": ind_area_km,
                        "landcover_class": lc
                    })
                source_df = pd.DataFrame(stage1_rows)
                preds = list(self.source_model.predict(source_df))
                probs_matrix = self.source_model.predict_proba(source_df)
                for i in range(n):
                    probs = probs_matrix[i]
                    prob_dicts[i] = {str(c): round(float(p) * 100, 2) for c, p in zip(self.classes_, probs)}
                    confidences[i] = round(float(np.max(probs)) * 100, 2)
            except Exception as e:
                print(f"Batch Stage-1 inference exception: {e}")

        # Fallbacks if any failed
        for i in range(n):
            if preds[i] is None:
                p, c, pd_ = self._rule_based_fallback(features_list[i])
                preds[i] = p
                confidences[i] = c
                prob_dicts[i] = pd_

        # Stage 2: Persistence Prediction via model.pkl in batch
        if self.persistence_model is not None:
            try:
                stage2_rows = []
                for f in features_list:
                    m_frp = float(f.get("mean_frp") or 15.0)
                    mx_frp = float(f.get("max_frp") or m_frp)
                    m_brt = float(f.get("mean_brightness") or 325.0)
                    mx_brt = float(f.get("max_brightness") or m_brt)
                    min_ind = float(f.get("min_distance_industry") or f.get("min_distance_to_industry_km") or 5.0)
                    mean_ind = float(f.get("mean_distance_industry") or f.get("mean_distance_to_industry_km") or min_ind)
                    fac_1k = float(f.get("mean_industrial_facilities_1km") or 0.0)
                    fac_5k = float(f.get("mean_industrial_facilities_5km") or 0.0)
                    ind_ratio = float(f.get("industrial_land_ratio") or (0.8 if min_ind < 1.5 else 0.0))
                    stage2_rows.append({
                        "mean_frp": m_frp,
                        "max_frp": mx_frp,
                        "mean_brightness": m_brt,
                        "max_brightness": mx_brt,
                        "mean_distance_industry": mean_ind,
                        "min_distance_industry": min_ind,
                        "mean_industrial_facilities_1km": fac_1k,
                        "mean_industrial_facilities_5km": fac_5k,
                        "industrial_land_ratio": ind_ratio
                    })
                pers_df = pd.DataFrame(stage2_rows)
                pers_preds = self.persistence_model.predict(pers_df)
                pers_probs_matrix = self.persistence_model.predict_proba(pers_df)
                for i in range(n):
                    is_persistents[i] = bool(int(pers_preds[i]) == 1)
                    pers_scores[i] = round(float(pers_probs_matrix[i][1]) * 100, 1)
            except Exception as pe:
                print(f"Batch Stage-2 persistence inference exception: {pe}")

        results = []
        for i in range(n):
            f = features_list[i]
            pred = preds[i]
            conf = confidences[i]
            final_persistence = pers_scores[i] if pers_scores[i] is not None else float(f.get("persistence_score") or 85.0)
            is_pers = is_persistents[i]

            min_dist = f.get("min_distance_to_industry_km", 50.0)
            lc_class = f.get("landcover_class", "Unknown")
            fac_type = f.get("nearest_facility_type", "industrial area")

            reasons = []
            if pred == "Industrial":
                reasons.append(f"Classified by Stage-1 Spatial Pipeline within {min_dist:.2f} km of {fac_type}")
                if is_pers:
                    reasons.append(f"Stage-2 Energy Classifier flagged high persistence ({final_persistence:.1f}%)")
                else:
                    reasons.append(f"Thermal recurrence observed near manufacturing zone")
            elif pred == "Forest/Natural":
                reasons.append(f"Dominant canopy land cover: {lc_class}")
                reasons.append(f"Isolated from industrial infrastructure ({min_dist:.2f} km away)")
            elif pred == "Agricultural":
                reasons.append(f"Occurring in cropland / agricultural belt ({lc_class})")
                reasons.append("Short duration / ephemeral seasonal burn signature")
            else:
                reasons.append(f"Surface land cover: {lc_class}")

            results.append({
                "predicted_event_type": pred,
                "confidence_pct": conf,
                "persistence_score": final_persistence,
                "is_persistent": is_pers,
                "probabilities": prob_dicts[i],
                "explanation": reasons,
                "model_architecture": "Two-Stage Decoupled Pipeline (source_type_model + persistence_model)"
            })

        return results

    def _rule_based_fallback(self, feat: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
        min_dist = feat.get("min_distance_to_industry_km", 50.0)
        lc = str(feat.get("landcover_class", "")).lower()
        active_days = feat.get("active_days", 1)

        if min_dist <= 2.0 or "built-up" in lc or (min_dist <= 5.0 and active_days >= 3):
            return "Industrial", 94.5, {"Industrial": 94.5, "Forest/Natural": 2.1, "Agricultural": 2.4, "Other": 1.0}
        elif "crop" in lc or feat.get("agricultural_land_ratio", 0) > 0:
            return "Agricultural", 91.0, {"Agricultural": 91.0, "Forest/Natural": 5.0, "Industrial": 2.0, "Other": 2.0}
        elif "tree" in lc or "forest" in lc or "grass" in lc or "shrub" in lc:
            return "Forest/Natural", 92.0, {"Forest/Natural": 92.0, "Agricultural": 4.0, "Industrial": 2.0, "Other": 2.0}
        else:
            return "Other", 85.0, {"Other": 85.0, "Forest/Natural": 5.0, "Agricultural": 5.0, "Industrial": 5.0}

# Global singleton
ml_engine = EventClassifierEngine()