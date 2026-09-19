# ml/recommendation_engine.py
import os
import sys
import re
import logging
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config
from ml.skill_normalizer import normalize_skill_name, parse_skills_list
from ml.market_analyzer import PhilippineMarketAnalyzer
from ml.success_model_service import SuccessModelService

logger = logging.getLogger(__name__)

class HybridBusinessRecommender:
    """
    Philippine Hybrid Business Idea Recommendation Engine.
    Executes hard capital gating followed by 7-component scoring:
    Capital (30%), Skills (25%), Experience (10%), Setup (10%),
    Time (5%), Location (10%), and Success Model (10%).
    """
    def __init__(self, catalog_path=None, tfidf_path=None):
        self.weights = Config.RECOMMENDATION_WEIGHTS
        self.catalog_path = Path(catalog_path) if catalog_path else Config.FINAL_BUSINESSES_CSV
        self.tfidf_path = Path(tfidf_path) if tfidf_path else (Config.ML_MODELS_PATH / "tfidf_vectorizer.pkl")
        self.df_businesses = pd.DataFrame()
        self.vectorizer = None
        self.market_analyzer = PhilippineMarketAnalyzer(Config.MUNICIPALITY_MARKET_CSV)
        self.success_service = SuccessModelService(Config.SUCCESS_MODEL_JOBLIB, Config.SUCCESS_METRICS_JSON)
        self.load_catalog()
        self.load_vectorizer()

    def load_catalog(self):
        if not self.catalog_path.exists():
            logger.error(f"Business catalog file missing at: {self.catalog_path}")
            return
        try:
            self.df_businesses = pd.read_csv(self.catalog_path)
            self.df_businesses["min_capital"] = pd.to_numeric(
                self.df_businesses.get("min_capital", 0.0), errors="coerce"
            ).fillna(0.0)
            logger.info(f"Loaded {len(self.df_businesses)} business ideas from catalog.")
        except Exception as e:
            logger.error(f"Failed to read business catalog: {e}")

    def load_vectorizer(self):
        refit = True
        if self.tfidf_path.exists():
            try:
                vec = joblib.load(self.tfidf_path)
                vocab = getattr(vec, "vocabulary_", {})
                if vocab and len(vocab) > 20 and not any(" " in term for term in list(vocab.keys())[:30]):
                    self.vectorizer = vec
                    refit = False
            except Exception:
                pass

        if refit:
            self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w-]+\b", stop_words="english")
            corpus = self.df_businesses["core_skills"].dropna().astype(str) if not self.df_businesses.empty else ["business skills"]
            self.vectorizer.fit(corpus)
            self.tfidf_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.vectorizer, self.tfidf_path)

    def parse_skills(self, skills_raw):
        """Exposes skill parsing for test suite and route helpers."""
        return parse_skills_list(skills_raw)

    def calculate_capital_score(self, user_cap: float, min_cap: float) -> float:
        if user_cap < min_cap:
            return 0.0
        ratio = user_cap / max(min_cap, 1.0)
        if ratio >= 1.5:
            return 1.0
        return round(0.70 + 0.30 * ((ratio - 1.0) / 0.5), 3)

    def calculate_skill_score(self, user_skills: list, core_skills_str: str) -> tuple:
        biz_skills = self.parse_skills(core_skills_str)
        if not biz_skills:
            return 0.60, [], []
        if not user_skills:
            return 0.50, [], biz_skills

        user_norm = set(normalize_skill_name(s).lower() for s in user_skills if s)
        matched = []
        gaps = []

        for bs in biz_skills:
            if bs.lower() in user_norm or any(u in bs.lower() or bs.lower() in u for u in user_norm):
                matched.append(bs)
            else:
                gaps.append(bs)

        score = len(matched) / len(biz_skills)
        return round(score, 3), matched, gaps

    def calculate_experience_score(self, user_exp: str, biz_exp: str) -> float:
        levels = {"beginner": 1, "intermediate": 2, "experienced": 3}
        u_val = levels.get(str(user_exp).lower().strip(), 1)
        b_val = levels.get(str(biz_exp).lower().strip(), 1)
        if u_val >= b_val:
            return 1.0
        if u_val == 1 and b_val == 2:
            return 0.65
        if u_val == 1 and b_val == 3:
            return 0.35
        return 0.70

    def calculate_setup_score(self, user_setups: list, biz_setup: str) -> float:
        if not user_setups:
            return 0.70
        b_set = str(biz_setup).lower().strip()
        user_norm = [str(u).lower().strip() for u in user_setups]

        for u in user_norm:
            if u in b_set or b_set in u:
                return 1.0
        if any("home" in u or "online" in u for u in user_norm) and ("online" in b_set or "home" in b_set):
            return 0.85
        return 0.40

    def calculate_time_score(self, available_time: str, biz_setup: str, people_needed: str) -> float:
        t_str = str(available_time).lower()
        b_set = str(biz_setup).lower()
        staff_str = str(people_needed).lower()
        is_high_complexity = "commercial" in b_set or "store" in b_set or "staff" in staff_str

        if "full" in t_str or "7-8" in t_str:
            return 1.0
        if "5-6" in t_str:
            return 0.90
        if "3-4" in t_str:
            return 0.75 if is_high_complexity else 0.95
        return 0.40 if is_high_complexity else 0.80

    def recommend(self, user_profile: dict, top_n: int = 5) -> list:
        if self.df_businesses.empty:
            return []

        user_cap = float(user_profile.get("capital", 0))
        user_skills = user_profile.get("skills", [])
        user_exp = str(user_profile.get("experience", "Beginner"))
        available_time = str(user_profile.get("available_time", "5-6 hours/day"))
        user_setups = user_profile.get("setup", ["Online / Home-Based"])
        if isinstance(user_setups, str):
            user_setups = [user_setups]
        municipality = user_profile.get("location", "")

        # STEP 1: HARD CAPITAL FEASIBILITY FILTER
        feasible_mask = self.df_businesses["min_capital"] <= user_cap
        feasible_df = self.df_businesses[feasible_mask].copy()

        if feasible_df.empty:
            return []

        results = []
        w = self.weights

        for _, row in feasible_df.iterrows():
            biz_dict = row.to_dict()

            s_cap = self.calculate_capital_score(user_cap, float(row["min_capital"]))
            s_skill, matched, gaps = self.calculate_skill_score(user_skills, str(row.get("core_skills", "")))
            s_exp = self.calculate_experience_score(user_exp, str(row.get("experience_level", "Beginner")))
            s_setup = self.calculate_setup_score(user_setups, str(row.get("business_setup", "")))
            s_time = self.calculate_time_score(available_time, str(row.get("business_setup", "")), str(row.get("people_needed", "")))

            loc_result = self.market_analyzer.analyze_location_market(
                municipality, str(row.get("category", "General")), str(row.get("business_type", ""))
            )
            s_loc = loc_result["location_score"]
            s_succ = self.success_service.predict_success_score(user_profile, biz_dict)

            final_score = (
                (s_cap * w["capital"]) +
                (s_skill * w["skills"]) +
                (s_exp * w["experience"]) +
                (s_setup * w["setup"]) +
                (s_time * w["time"]) +
                (s_loc * w["location"]) +
                (s_succ * w["success"])
            )

            rec_score_pct = round(final_score * 100, 1)

            reasons = []
            if s_cap >= 0.8:
                reasons.append(f"Comfortably matches starting capital (₱{user_cap:,.0f} vs ₱{row['min_capital']:,.0f} req.)")
            if s_skill >= 0.5 and matched:
                reasons.append(f"Matches {len(matched)} of your skills: {', '.join(matched[:3])}")
            elif not user_skills:
                reasons.append("Beginner-friendly skill entry profile")
            if s_exp >= 0.8:
                reasons.append(f"Suitable for {user_exp} experience level")
            if s_setup >= 0.8:
                reasons.append(f"Aligned with preferred setup: {row.get('business_setup')}")
            if s_loc >= 0.7:
                reasons.append("Supported by Philippine location market evidence")
            if s_succ >= 0.65:
                reasons.append("Strong operational fit under the trained success model")

            results.append({
                "id": int(row["id"]),
                "business_type": row["business_type"],
                "category": row.get("category", "General"),
                "startup_cost": row.get("startup_cost", f"₱{row['min_capital']:,.0f}"),
                "min_capital": float(row["min_capital"]),
                # Both keys provided for backwards compatibility across tests & templates
                "recommendation_score": rec_score_pct,
                "compatibility_score": rec_score_pct,
                "business_setup": row.get("business_setup", "Online / Home-Based"),
                "experience_level": row.get("experience_level", "Beginner"),
                "people_needed": row.get("people_needed", "1 person"),
                "minimum_requirements": row.get("minimum_requirements", ""),
                "strategies": row.get("strategies", ""),
                "risks": row.get("risks", ""),
                "matched_skills": matched,
                "skill_gaps": gaps,
                "location_evidence": loc_result["evidence_text"],
                "reasons": reasons[:4],
                "component_scores": {
                    "capital": round(s_cap * 100, 1),
                    "skills": round(s_skill * 100, 1),
                    "experience": round(s_exp * 100, 1),
                    "setup": round(s_setup * 100, 1),
                    "time": round(s_time * 100, 1),
                    "location": round(s_loc * 100, 1),
                    "success_model": round(s_succ * 100, 1)
                }
            })

        results.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return results[:top_n]

# Backwards compatibility alias for older test fixtures & routes
BusinessRecommenderEngine = HybridBusinessRecommender