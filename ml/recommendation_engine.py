import os
import re
import sys
import joblib
import logging
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

logger = logging.getLogger(__name__)

class BusinessRecommenderEngine:
    def __init__(self, catalog_path=None, tfidf_path=None):
        self.catalog_path = catalog_path or os.path.join(Config.FINAL_PATH, "final_business_dataset.csv")
        self.tfidf_path = tfidf_path or os.path.join(Config.ML_MODELS_PATH, "tfidf_vectorizer.pkl")
        self.load_engine()

    def load_engine(self):
        if not os.path.exists(self.catalog_path):
            logger.error(f"Catalog missing at {self.catalog_path}")
            self.df = pd.DataFrame()
            self.vectorizer = None
            self.skill_matrix = None
            return

        self.df = pd.read_csv(self.catalog_path)
        self.df["min_capital"] = pd.to_numeric(self.df.get("min_capital", 0.0), errors="coerce").fillna(0.0)
        self.df["core_skills"] = self.df.get("core_skills", "").fillna("").astype(str)

        refit = True
        if os.path.exists(self.tfidf_path):
            try:
                vec = joblib.load(self.tfidf_path)
                vocab = getattr(vec, "vocabulary_", {})
                if vocab and len(vocab) > 20 and not any(" " in term for term in list(vocab.keys())[:30]):
                    self.vectorizer = vec
                    self.skill_matrix = self.vectorizer.transform(self.df["core_skills"])
                    refit = False
            except Exception:
                pass

        if refit:
            self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w-]+\b", stop_words="english")
            self.skill_matrix = self.vectorizer.fit_transform(self.df["core_skills"])
            os.makedirs(os.path.dirname(self.tfidf_path), exist_ok=True)
            joblib.dump(self.vectorizer, self.tfidf_path)

    def parse_skills(self, skills_raw):
        if not skills_raw or pd.isna(skills_raw):
            return []
        tokens = [s.strip().title() for s in re.split(r"[,;\s]+", str(skills_raw)) if len(s.strip()) > 1]
        seen = set()
        deduped = []
        for t in tokens:
            tl = t.lower()
            if tl not in seen:
                seen.add(tl)
                deduped.append(t)
        return deduped

    def recommend(self, user_profile, top_n=5):
        if self.df.empty:
            return []

        user_cap = float(user_profile.get("capital", 0))
        raw_skills = user_profile.get("skills", [])
        if isinstance(raw_skills, str):
            raw_skills = re.split(r"[,;\s]+", raw_skills)
        user_skills_lower = set(s.strip().lower() for s in raw_skills if s.strip())

        user_exp = str(user_profile.get("experience", "Beginner")).strip().lower()
        user_time = str(user_profile.get("available_time", "4-6 hours/day")).strip().lower()
        user_setups = user_profile.get("setup", ["Online / Home-Based"])
        if isinstance(user_setups, str):
            user_setups = [user_setups]
        user_setups_lower = [str(s).strip().lower() for s in user_setups if s]

        # 1. Hard Capital Feasibility Gate
        feasible_mask = self.df["min_capital"] <= user_cap
        feasible_df = self.df[feasible_mask].copy()

        if feasible_df.empty:
            feasible_df = self.df.nsmallest(top_n, "min_capital").copy()

        feasible_submatrix = self.skill_matrix[feasible_df.index]

        # 2. Skill Cosine Similarity
        skill_query = " ".join(user_skills_lower)
        if skill_query.strip() and self.vectorizer is not None:
            user_vec = self.vectorizer.transform([skill_query])
            skill_similarities = cosine_similarity(user_vec, feasible_submatrix).flatten()
        else:
            skill_similarities = np.zeros(len(feasible_df))

        exp_levels = {"beginner": 1, "intermediate": 2, "experienced": 3}
        u_exp_val = exp_levels.get(user_exp, 1)

        results = []
        for idx, (_, row) in enumerate(feasible_df.iterrows()):
            s_score = float(skill_similarities[idx])
            c_score = 1.0 if user_cap >= row["min_capital"] else max(0.2, user_cap / max(row["min_capital"], 1.0))
            b_exp_val = exp_levels.get(str(row.get("experience_level", "Beginner")).strip().lower(), 1)
            e_score = 1.0 if u_exp_val >= b_exp_val else 0.5
            b_setup = str(row.get("business_setup", "")).strip().lower()
            set_score = 1.0 if any(u in b_setup for u in user_setups_lower) else 0.4
            t_score = 1.0 if any(k in user_time for k in ["full", "6+", "4-6"]) else 0.7

            comp = (0.35 * c_score + 0.30 * s_score + 0.15 * e_score + 0.10 * t_score + 0.10 * set_score) * 100

            req_skills = self.parse_skills(row.get("core_skills", ""))
            matched = [s for s in req_skills if s.lower() in user_skills_lower]
            gaps = [s for s in req_skills if s.lower() not in user_skills_lower]

            results.append({
                "id": int(row["id"]),
                "business_type": row["business_type"],
                "category": row.get("category", "General"),
                "startup_cost": row.get("startup_cost", f"₱{row['min_capital']:,.0f}"),
                "min_capital": float(row["min_capital"]),
                "compatibility_score": round(comp, 1),
                "business_setup": row.get("business_setup", "Online / Home-Based"),
                "experience_level": row.get("experience_level", "Beginner"),
                "people_needed": row.get("people_needed", "1 person"),
                "minimum_requirements": row.get("minimum_requirements", ""),
                "strategies": row.get("strategies", ""),
                "risks": row.get("risks", ""),
                "matched_skills": matched,
                "skill_gaps": gaps
            })

        results.sort(key=lambda x: x["compatibility_score"], reverse=True)
        return results[:top_n]
