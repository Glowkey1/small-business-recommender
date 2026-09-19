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

class SuccessModelService:
    """Manages the 12-feature mapping layer and Logistic Regression predictions."""
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
        else:
            logger.warning(f"Success model not found at {self.model_path}. Fallback active.")

        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, "r", encoding="utf-8") as f:
                    import json
                    self.metrics = json.load(f)
            except Exception:
                pass

    def map_user_business_features(self, user_profile: dict, business_item: dict) -> pd.DataFrame:
        """
        Maps user profile and business requirements into the 12 numeric training features:
        1. initial_capital: 1 if capital >= min_capital, else 0
        2. internet_usage: 1 if Online/Home-based setup or tech skills present
        3. marketing_effort: integer 1-5 rating based on user marketing skill & core requirements
        4. business_plan: 1 (always guided by the structured pathway)
        5. financial_record_keeping: 1 if user has finance skills or business requires costing
        6. partnership: 1 if business requires multi-person staff
        7. industry_experience: 1 (Beginner), 3 (Intermediate), 5 (Experienced)
        8. professional_advice: 1 if business requires licensing/permits
        9. age, education, parent_business_experience, owner_gender: dataset baselines (35, 2, 0, 1)
        """
        user_cap = float(user_profile.get("capital", 0))
        min_cap = float(business_item.get("min_capital", 0))
        user_skills = [str(s).lower() for s in user_profile.get("skills", [])]
        user_exp = str(user_profile.get("experience", "Beginner")).lower()
        biz_setup = str(business_item.get("business_setup", "")).lower()
        reqs = str(business_item.get("minimum_requirements", "")).lower()

        initial_cap = 1 if user_cap >= min_cap else 0
        internet = 1 if ("online" in biz_setup or any(s in ["social media", "marketing", "technology", "design"] for s in user_skills)) else 0
        has_mktg = any(s in ["marketing", "sales", "social media"] for s in user_skills)
        marketing = 4 if has_mktg else 2
        bus_plan = 1
        fin_records = 1 if (any(s in ["accounting", "bookkeeping", "finance"] for s in user_skills) or "costing" in str(business_item.get("core_skills", "")).lower()) else 0
        partnership = 1 if ("people_needed" in business_item and "solo" not in str(business_item["people_needed"]).lower()) else 0

        if "experienced" in user_exp:
            exp_val = 5
        elif "intermediate" in user_exp:
            exp_val = 3
        else:
            exp_val = 1

        prof_advice = 1 if any(k in reqs for k in ["license", "certified", "compliance", "regulatory"]) else 0

        feature_dict = {
            "age": 35,
            "education": 2,
            "initial_capital": initial_cap,
            "financial_record_keeping": fin_records,
            "internet_usage": internet,
            "business_plan": bus_plan,
            "marketing_effort": marketing,
            "partnership": partnership,
            "parent_business_experience": 0,
            "industry_experience": exp_val,
            "owner_gender": 1,
            "professional_advice": prof_advice
        }

        return pd.DataFrame([feature_dict])[FEATURE_COLUMNS]

    def predict_success_score(self, user_profile: dict, business_item: dict) -> float:
        if self.model is None:
            return 0.50
        try:
            X_input = self.map_user_business_features(user_profile, business_item)
            if hasattr(self.model, "predict_proba"):
                prob = float(self.model.predict_proba(X_input)[0][1])
                return round(prob, 4)
            return 0.75 if int(self.model.predict(X_input)[0]) == 1 else 0.35
        except Exception as e:
            logger.error(f"Inference error in success model: {e}")
            return 0.50
