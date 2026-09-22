import json
import logging
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "age", "education", "initial_capital", "financial_record_keeping",
    "internet_usage", "business_plan", "marketing_effort", "partnership",
    "parent_business_experience", "industry_experience", "owner_gender",
    "professional_advice"
]

TRAINING_MEDIANS = {
    "age": 35.0,
    "education": 3.0,
    "parent_business_experience": 0.0,
    "owner_gender": 1.0,
    "professional_advice": 4.0
}

TRAINING_BOUNDS = {
    "age": (18.0, 60.0),
    "education": (1.0, 5.0),
    "initial_capital": (0.0, 1.0),
    "financial_record_keeping": (0.0, 1.0),
    "internet_usage": (0.0, 1.0),
    "business_plan": (0.0, 1.0),
    "marketing_effort": (1.0, 7.0),
    "partnership": (0.0, 1.0),
    "parent_business_experience": (0.0, 1.0),
    "industry_experience": (0.0, 20.0),
    "owner_gender": (0.0, 1.0),
    "professional_advice": (1.0, 7.0)
}

class SuccessModelService:
    def __init__(self, model_path: Path, metrics_path: Path):
        self.model_path = model_path
        self.metrics_path = metrics_path
        self.model = None
        self.metrics = {}
        self._load()

    def _load(self):
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded Success Prediction Model from: {self.model_path}")
            except Exception as e:
                logger.error(f"Error loading success model: {e}")
                self.model = None
        else:
            self.model = None

        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, "r", encoding="utf-8") as f:
                    self.metrics = json.load(f)
            except Exception:
                pass

    def map_features(self, user_profile: dict, business_item: dict) -> dict:
        user_cap = float(user_profile.get("capital", 0))
        min_cap = float(business_item.get("min_capital", 0))
        user_skills = [str(s).lower() for s in user_profile.get("skills", [])]
        user_exp = str(user_profile.get("experience", "Beginner")).lower()
        biz_setup = str(business_item.get("business_setup", "")).lower()

        initial_cap = 1.0 if user_cap >= min_cap else 0.0
        internet = 1.0 if ("online" in biz_setup or any(s in ["social media", "marketing", "technology", "design"] for s in user_skills)) else 0.0
        mktg = 5.0 if any(s in ["marketing", "sales", "social media"] for s in user_skills) else 2.0
        bus_plan = 1.0
        fin_records = 1.0 if (any(s in ["accounting", "bookkeeping", "finance"] for s in user_skills) or "costing" in str(business_item.get("core_skills", "")).lower()) else 0.0
        partnership = 1.0 if ("people_needed" in business_item and "solo" not in str(business_item["people_needed"]).lower()) else 0.0

        if "experienced" in user_exp:
            exp_val = 5.0
        elif "intermediate" in user_exp:
            exp_val = 3.0
        else:
            exp_val = 1.0

        row = {
            "age": TRAINING_MEDIANS["age"],
            "education": TRAINING_MEDIANS["education"],
            "initial_capital": initial_cap,
            "financial_record_keeping": fin_records,
            "internet_usage": internet,
            "business_plan": bus_plan,
            "marketing_effort": mktg,
            "partnership": partnership,
            "parent_business_experience": TRAINING_MEDIANS["parent_business_experience"],
            "industry_experience": exp_val,
            "owner_gender": TRAINING_MEDIANS["owner_gender"],
            "professional_advice": TRAINING_MEDIANS["professional_advice"]
        }

        for k, (low, high) in TRAINING_BOUNDS.items():
            row[k] = float(np.clip(row[k], low, high))

        return row

    def predict_success_scores(self, user_profile: dict, businesses: list) -> list:
        if self.model is None or not businesses:
            return [None] * len(businesses)

        try:
            rows = [self.map_features(user_profile, b) for b in businesses]
            df_in = pd.DataFrame(rows)[FEATURE_COLUMNS]
            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(df_in)[:, 1]
                return [round(float(p), 4) for p in probs]
            preds = self.model.predict(df_in)
            return [0.75 if int(p) == 1 else 0.35 for p in preds]
        except Exception as e:
            logger.error(f"Inference error in success model batch: {e}")
            return [None] * len(businesses)
