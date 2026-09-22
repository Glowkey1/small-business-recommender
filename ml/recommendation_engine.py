import os
import sys
import re
import logging
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config, validate_weights
from ml.skill_normalizer import normalize_skill_name, parse_skills_list, GENERIC_STOP_FRAGMENTS
from ml.market_analyzer import PhilippineMarketAnalyzer
from ml.success_model_service import SuccessModelService

logger = logging.getLogger(__name__)

def combine_scores(component_scores: dict, weights: dict) -> float:
    active_weights_sum = sum(weights[k] for k, v in component_scores.items() if v is not None)
    if active_weights_sum <= 0:
        return 0.50
    score_sum = sum(v * weights[k] for k, v in component_scores.items() if v is not None)
    return score_sum / active_weights_sum

class HybridBusinessRecommender:
    def __init__(self, catalog_path=None, tfidf_path=None):
        self.weights = Config.RECOMMENDATION_WEIGHTS
        validate_weights(self.weights)

        self.catalog_path = Path(catalog_path) if catalog_path else Config.FINAL_BUSINESSES_CSV
        self.tfidf_path = Path(tfidf_path) if tfidf_path else (Config.ML_MODELS_PATH / "tfidf_vectorizer.pkl")

        self.df_businesses = pd.DataFrame()
        self.vectorizer = None
        self.skill_alias_map = {}
        self.selectable_skills = []

        self.market_analyzer = PhilippineMarketAnalyzer(Config.MUNICIPALITY_MARKET_CSV)
        self.success_service = SuccessModelService(Config.SUCCESS_MODEL_JOBLIB, Config.SUCCESS_METRICS_JSON)

        self._load_skill_master()
        self.load_catalog()
        self.load_vectorizer()

    def _load_skill_master(self):
        if Config.SKILL_MASTER_CSV.exists():
            try:
                df_sm = pd.read_csv(Config.SKILL_MASTER_CSV)
                name_col = "skill_name" if "skill_name" in df_sm.columns else df_sm.columns[0]
                terms_col = "source_terms" if "source_terms" in df_sm.columns else (df_sm.columns[1] if len(df_sm.columns) > 1 else None)

                for _, r in df_sm.iterrows():
                    canonical = str(r[name_col]).strip()
                    if not canonical:
                        continue
                    # 1. Map canonical to itself
                    self.skill_alias_map[canonical.lower()] = canonical

                    # 2. Split comma-separated source terms and map each raw term to the canonical name
                    if terms_col and pd.notna(r[terms_col]):
                        for raw_term in str(r[terms_col]).split(","):
                            raw_term = raw_term.strip().lower()
                            if raw_term:
                                self.skill_alias_map[raw_term] = canonical
                logger.info(f"Loaded {len(self.skill_alias_map)} clean skill aliases from skill_master.csv.")
            except Exception as e:
                logger.error(f"Error loading skill master: {e}")
    def load_catalog(self):
        if not self.catalog_path.exists():
            return
        try:
            self.df_businesses = pd.read_csv(self.catalog_path)
            self.df_businesses["min_capital"] = pd.to_numeric(
                self.df_businesses.get("min_capital", 0.0), errors="coerce"
            ).fillna(0.0)

            # Build filtered master skills
            master_set = set()
            for _, r in self.df_businesses.iterrows():
                tokens = parse_skills_list(r.get("core_skills", ""))
                for t in tokens:
                    canon = self.skill_alias_map.get(t.lower(), t)
                    if canon.lower() not in GENERIC_STOP_FRAGMENTS and len(canon) > 2:
                        master_set.add(canon)
            self.selectable_skills = sorted(list(master_set))
        except Exception as e:
            logger.error(f"Failed to load business catalog: {e}")

    def load_vectorizer(self):
        if self.tfidf_path.exists():
            try:
                vec = joblib.load(self.tfidf_path)
                vocab = getattr(vec, "vocabulary_", {})
                if vocab and len(vocab) > 20 and not any(" " in term for term in list(vocab.keys())[:30]):
                    self.vectorizer = vec
                    return
            except Exception:
                pass
        self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w-]+\b", stop_words="english")
        corpus = self.df_businesses["core_skills"].dropna().astype(str) if not self.df_businesses.empty else ["skills"]
        self.vectorizer.fit(corpus)

    def parse_skills(self, skills_raw):
        return parse_skills_list(skills_raw)

    def calculate_capital_score(self, user_cap: float, min_cap: float) -> float:
        if user_cap < min_cap:
            return 0.0
        ratio = user_cap / max(min_cap, 1.0)
        if ratio >= 1.5:
            return 1.0
        return round(0.70 + 0.30 * ((ratio - 1.0) / 0.5), 3)

    def calculate_skill_score(self, user_skills: list, core_skills_str: str) -> tuple:
        biz_tokens = parse_skills_list(core_skills_str)
        if not biz_tokens:
            return 0.60, [], []

        biz_canonical = []
        for t in biz_tokens:
            canon = self.skill_alias_map.get(t.lower(), t)
            if canon.lower() not in GENERIC_STOP_FRAGMENTS:
                biz_canonical.append(canon)

        if not biz_canonical:
            biz_canonical = biz_tokens

        if not user_skills:
            return 0.50, [], biz_canonical

        user_norm_set = set(self.skill_alias_map.get(s.lower(), s).lower() for s in user_skills if s)

        matched = []
        gaps = []
        for bs in biz_canonical:
            if bs.lower() in user_norm_set:
                matched.append(bs)
            else:
                gaps.append(bs)

        score = len(matched) / len(biz_canonical)
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
        def tag_setup(s: str) -> set:
            sl = s.lower()
            tags = set()
            if "online" in sl: tags.add("online")
            if "home" in sl: tags.add("home")
            if "store" in sl or "shop" in sl or "commercial" in sl: tags.add("store")
            if "service" in sl or "mobile" in sl: tags.add("mobile")
            return tags

        biz_tags = tag_setup(str(biz_setup))
        user_tags = set()
        for u in user_setups:
            user_tags.update(tag_setup(str(u)))

        if not user_tags:
            return 0.70

        if user_tags & biz_tags:
            return 1.0
        if ("online" in user_tags and "home" in biz_tags) or ("home" in user_tags and "online" in biz_tags):
            return 0.85
        if ("store" in user_tags and "mobile" in biz_tags) or ("mobile" in user_tags and "store" in biz_tags):
            return 0.55
        return 0.40

    def calculate_time_score(self, available_time: str, biz_setup: str, people_needed: str) -> float:
        t_str = str(available_time).lower()
        b_set = str(biz_setup).lower()
        staff_str = str(people_needed).lower()
        is_complex = "commercial" in b_set or "store" in b_set or "staff" in staff_str

        if "full" in t_str or "7-8" in t_str:
            return 1.0
        if "5-6" in t_str:
            return 0.90
        if "3-4" in t_str:
            return 0.75 if is_complex else 0.95
        return 0.40 if is_complex else 0.80

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
        psgc = user_profile.get("location", "")

        feasible_df = self.df_businesses[self.df_businesses["min_capital"] <= user_cap].copy()
        if feasible_df.empty:
            return []

        eligible_records = [r.to_dict() for _, r in feasible_df.iterrows()]
        success_scores = self.success_service.predict_success_scores(user_profile, eligible_records)

        results = []
        for idx, row in enumerate(eligible_records):
            s_cap = self.calculate_capital_score(user_cap, float(row["min_capital"]))
            s_skill, matched, gaps = self.calculate_skill_score(user_skills, str(row.get("core_skills", "")))
            s_exp = self.calculate_experience_score(user_exp, str(row.get("experience_level", "Beginner")))
            s_setup = self.calculate_setup_score(user_setups, str(row.get("business_setup", "")))
            s_time = self.calculate_time_score(available_time, str(row.get("business_setup", "")), str(row.get("people_needed", "")))

            loc_result = self.market_analyzer.analyze_location_market(psgc, str(row.get("business_type", "")))
            s_loc = loc_result["location_score"]
            s_succ = success_scores[idx]

            components = {
                "capital": s_cap,
                "skills": s_skill,
                "experience": s_exp,
                "setup": s_setup,
                "time": s_time,
                "location": s_loc,
                "success": s_succ
            }

            final_score = combine_scores(components, self.weights)
            rec_score_pct = round(final_score * 100, 1)

            reasons = []
            reasons.append(f"Within your starting capital (₱{user_cap:,.0f} vs ₱{row['min_capital']:,.0f} minimum)")

            if user_skills:
                if matched:
                    reasons.append(f"Matches {len(matched)} of your selected skills: {', '.join(matched[:3])}")
            else:
                reasons.append("No skills selected")

            if s_exp == 1.0:
                reasons.append(f"Suitable for {user_exp} experience level")
            else:
                reasons.append(f"Rated {row.get('experience_level')}; expect a learning curve")

            if s_setup >= 0.85:
                reasons.append(f"Compatible with your preferred setup: {row.get('business_setup')}")

            if s_loc is not None:
                reasons.append("Has relevant market presence in your location")

            if s_succ is not None:
                reasons.append(f"Model-based success score {int(round(s_succ * 100))}% (one component of the ranking)")

            results.append({
                "id": int(row["id"]),
                "business_id": int(row["id"]),
                "business_type": row["business_type"],
                "category": row.get("category", "General"),
                "market_category": loc_result["category"],
                "startup_cost": row.get("startup_cost", f"₱{row['min_capital']:,.0f}"),
                "min_capital": float(row["min_capital"]),
                "people_needed": row.get("people_needed", "1 person"),
                "business_setup": row.get("business_setup", "Online / Home-Based"),
                "experience_level": row.get("experience_level", "Beginner"),
                "minimum_requirements": row.get("minimum_requirements", ""),
                "strategies": row.get("strategies", ""),
                "risks": row.get("risks", ""),
                "matched_skills": matched,
                "skill_gaps": gaps,
                "location_evidence": loc_result["evidence_text"],
                "reasons": reasons[:6],
                "raw_final_score": final_score,
                "recommendation_score": rec_score_pct,
                "compatibility_score": rec_score_pct,
                "success_model_score": round(s_succ * 100, 1) if s_succ is not None else None,
                "component_scores": {
                    "capital": round(s_cap * 100, 1),
                    "skills": round(s_skill * 100, 1),
                    "experience": round(s_exp * 100, 1),
                    "setup": round(s_setup * 100, 1),
                    "time": round(s_time * 100, 1),
                    "location": round(s_loc * 100, 1) if s_loc is not None else None,
                    "success": round(s_succ * 100, 1) if s_succ is not None else None
                }
            })

        results.sort(
            key=lambda x: (-x["raw_final_score"], -x["component_scores"]["skills"], x["business_type"])
        )
        return results[:top_n]

BusinessRecommenderEngine = HybridBusinessRecommender
