# apply_changes.py
"""
Single-run script applying all changes:
1. config.py: Updated RECOMMENDATION_WEIGHTS (includes team: 0.06, sum = 1.0).
2. ml/recommendation_engine.py:
   - Skills: Omitted (None) when no skills selected, renormalizing remaining weights.
   - Success model: Min-max scaled across candidates for ranking, raw percentage in reasons.
   - Team size: Added calculate_team_score() using parse_people_needed and experience.
   - Skill matching: Blends exact match (75%) with TF-IDF cosine similarity (25%).
   - Variety: select_diverse_top_n() re-ranks near-ties to prevent near-clones without altering scores.
3. templates/user/recommendations.html: Adds tip when no skills are selected; shows team size in breakdown.
4. tests/test_hybrid_recommender.py: Updated empty skills test, added weights sum test and determinism test.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent

print("=" * 75)
print("Applying score separation, team size, diversity, and test updates...")
print("=" * 75)

UPDATES = {}

# ======================================================================
# 1. config.py (Weights with team size component summing to 1.0)
# ======================================================================
UPDATES["config.py"] = r'''import os
import re
import secrets
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

SQLITE_PATH = (INSTANCE_DIR / "app.db").as_posix()
ENV_DB_URL = os.getenv("DATABASE_URL")

def resolve_db_uri():
    env_url = os.getenv("DATABASE_URL")
    default_uri = f"sqlite:///{SQLITE_PATH}"
    if not env_url or not env_url.strip():
        return default_uri
    env_url = env_url.strip()
    if not env_url.startswith("sqlite:///"):
        return env_url
    path_part = env_url[len("sqlite:///"):]
    if os.path.isabs(path_part) or re.match(r"^[A-Za-z]:[/\\]", path_part):
        return env_url
    abs_path = (BASE_DIR / path_part).as_posix()
    return f"sqlite:///{abs_path}"

_env_secret = os.getenv("SECRET_KEY")
if not _env_secret:
    logging.warning("SECRET_KEY unset in environment. Generating ephemeral 32-byte session secret.")
    _env_secret = secrets.token_hex(32)

def validate_weights(weights: dict):
    total = sum(weights.values())
    if not (0.999 <= total <= 1.001):
        raise ValueError(f"Recommendation weights must sum to 1.0, got {total}")

class Config:
    SECRET_KEY = _env_secret
    SQLALCHEMY_DATABASE_URI = resolve_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    RAW_D1_PATH = DATA_DIR / "raw" / "dataset_1"
    RAW_D2_PATH = DATA_DIR / "raw" / "dataset_2"
    PROCESSED_PATH = DATA_DIR / "processed"
    FINAL_PATH = DATA_DIR / "final"
    MODELS_DIR = BASE_DIR / "models"
    ML_MODELS_PATH = BASE_DIR / "ml" / "models"

    FINAL_BUSINESSES_CSV = FINAL_PATH / "final_business_dataset.csv"
    FINAL_SKILLS_CSV = FINAL_PATH / "final_skill_dataset.csv"
    SKILL_MASTER_CSV = FINAL_PATH / "skill_master.csv"
    MUNICIPALITY_MARKET_CSV = PROCESSED_PATH / "municipality_market_features.csv"
    BUSINESSES_PSA_CSV = PROCESSED_PATH / "businesses_with_psa_population.csv"
    DATASET_1_CLEANED_CSV = PROCESSED_PATH / "dataset_1_cleaned.csv"
    CATEGORY_MAP_CSV = FINAL_PATH / "business_market_category_map.csv"
    PSGC_NAMES_CSV = PROCESSED_PATH / "psgc_region_province_names.csv"

    SUCCESS_MODEL_JOBLIB = MODELS_DIR / "success_model.joblib"
    SUCCESS_METRICS_JSON = MODELS_DIR / "model_metrics.json"

    MAX_CAPITAL = 100_000_000.0
    ALLOWED_EXPERIENCE = ["Beginner", "Intermediate", "Experienced"]
    ALLOWED_TIMES = [
        "1-2 hours/day", "3-4 hours/day", "5-6 hours/day", "7-8 hours/day", "Full-time"
    ]
    ALLOWED_SETUPS = ["Online", "Home-Based", "Physical Store", "Service / Mobile"]

    LOCATION_SCORES = {
        "zero": 0.60,
        "low": 0.75,
        "mid": 0.90,
        "high": 0.85,
        "very_high": 0.75,
        "missing_pop_high": 0.85,
        "missing_pop_low": 0.75
    }

    RECOMMENDATION_WEIGHTS = {
        "capital": 0.26,
        "skills": 0.25,
        "experience": 0.10,
        "setup": 0.10,
        "time": 0.05,
        "location": 0.10,
        "success": 0.08,
        "team": 0.06
    }
'''

# ======================================================================
# 2. ml/recommendation_engine.py
# ======================================================================
UPDATES["ml/recommendation_engine.py"] = r'''import os
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
from config import Config, validate_weights
from ml.skill_normalizer import normalize_skill_name, parse_skills_list, GENERIC_STOP_FRAGMENTS
from ml.market_analyzer import PhilippineMarketAnalyzer
from ml.success_model_service import SuccessModelService

logger = logging.getLogger(__name__)

def parse_people_needed(text):
    if pd.isna(text) or text is None:
        return (1, 1)
    cleaned = str(text).strip().lower()
    if "solo" in cleaned or cleaned in {"1", "single", "individual"}:
        return (1, 1)
    m_range = re.search(r"(\d+)\s*[-–—to]+\s*(\d+)", cleaned)
    if m_range:
        return (int(m_range.group(1)), int(m_range.group(2)))
    m_plus = re.search(r"(\d+)\s*\+", cleaned)
    if m_plus:
        n = int(m_plus.group(1))
        return (n, int(n * 2))
    m_single = re.search(r"\b(\d+)\b", cleaned)
    if m_single:
        n = int(m_single.group(1))
        return (n, n)
    return (1, 1)

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
                    self.skill_alias_map[canonical.lower()] = canonical

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

            master_set = set()
            for _, r in self.df_businesses.iterrows():
                tokens = parse_skills_list(r.get("core_skills", ""))
                for t in tokens:
                    canon = self.skill_alias_map.get(t.lower(), t)
                    if canon.lower() not in GENERIC_STOP_FRAGMENTS and len(canon) > 2 and "," not in canon:
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
        if min_cap <= 0:
            return 1.0
        if user_cap >= min_cap:
            ratio = user_cap / min_cap
            if ratio >= 1.5:
                return 1.0
            return round(0.70 + 0.30 * ((ratio - 1.0) / 0.5), 3)
        return round(0.70 * (user_cap / min_cap), 3)

    def calculate_skill_score(self, user_skills: list, core_skills_str: str) -> tuple:
        biz_tokens = parse_skills_list(core_skills_str)
        if not biz_tokens:
            return (0.60, [], []) if user_skills else (None, [], [])

        biz_canonical = []
        for t in biz_tokens:
            canon = self.skill_alias_map.get(t.lower(), t)
            if canon.lower() not in GENERIC_STOP_FRAGMENTS and "," not in canon:
                biz_canonical.append(canon)

        if not biz_canonical:
            biz_canonical = biz_tokens

        # Omit skills component if no skills selected (renormalizes other weights)
        if not user_skills:
            return None, [], biz_canonical

        user_norm_set = set(self.skill_alias_map.get(s.lower(), s).lower() for s in user_skills if s)

        matched = []
        gaps = []
        for bs in biz_canonical:
            if bs.lower() in user_norm_set:
                matched.append(bs)
            else:
                gaps.append(bs)

        exact_ratio = len(matched) / len(biz_canonical) if biz_canonical else 0.0

        # Partial credit using TF-IDF cosine similarity
        tfidf_sim = 0.0
        if self.vectorizer is not None:
            try:
                user_str = " ".join(user_skills)
                user_vec = self.vectorizer.transform([user_str])
                biz_vec = self.vectorizer.transform([str(core_skills_str)])
                cos_val = cosine_similarity(user_vec, biz_vec)[0][0]
                if not np.isnan(cos_val):
                    tfidf_sim = float(cos_val)
            except Exception:
                tfidf_sim = 0.0

        if exact_ratio >= 1.0:
            combined_skill = 1.0
        else:
            combined_skill = 0.75 * exact_ratio + 0.25 * min(1.0, tfidf_sim)

        return round(combined_skill, 3), matched, gaps

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

    def calculate_team_score(self, user_exp: str, people_needed_str: str) -> float:
        range_p = parse_people_needed(people_needed_str)
        avg_p = (range_p[0] + range_p[1]) / 2.0
        u_exp = str(user_exp).lower().strip()

        if "experienced" in u_exp:
            if avg_p > 6: return 1.0
            if avg_p > 3: return 1.0
            if avg_p > 1: return 0.90
            return 0.80
        elif "intermediate" in u_exp:
            if avg_p <= 1: return 0.85
            if avg_p <= 3: return 1.0
            if avg_p <= 6: return 0.80
            return 0.50
        else:
            if avg_p <= 1: return 1.0
            if avg_p <= 3: return 0.70
            if avg_p <= 6: return 0.40
            return 0.20

    def select_diverse_top_n(self, candidates: list, top_n: int = 5) -> list:
        if len(candidates) <= top_n:
            return candidates

        selected = []
        selected_signatures = []
        pool = candidates.copy()
        PENALTY = 0.02

        while pool and len(selected) < top_n:
            best_idx = 0
            best_effective_score = -1e9

            for i, cand in enumerate(pool):
                raw_score = cand["raw_final_score"]
                sig = (
                    cand["min_capital"],
                    str(cand.get("business_setup", "")).strip().lower(),
                    str(cand.get("experience_level", "")).strip().lower()
                )

                shares_profile = sum(1 for s in selected_signatures if s == sig)
                penalty = shares_profile * PENALTY
                effective_score = raw_score - penalty

                skill_score = cand["component_scores"]["skills"] if cand["component_scores"]["skills"] is not None else 0.0
                best_cand = pool[best_idx]
                best_skill = best_cand["component_scores"]["skills"] if best_cand["component_scores"]["skills"] is not None else 0.0

                if (effective_score > best_effective_score) or (
                    np.isclose(effective_score, best_effective_score, atol=1e-5) and
                    (raw_score > best_cand["raw_final_score"] or
                     (np.isclose(raw_score, best_cand["raw_final_score"], atol=1e-5) and
                      (skill_score > best_skill or
                       (np.isclose(skill_score, best_skill, atol=1e-5) and
                        cand["business_type"] < best_cand["business_type"]))))
                ):
                    best_effective_score = effective_score
                    best_idx = i

            chosen = pool.pop(best_idx)
            chosen_sig = (
                chosen["min_capital"],
                str(chosen.get("business_setup", "")).strip().lower(),
                str(chosen.get("experience_level", "")).strip().lower()
            )
            selected.append(chosen)
            selected_signatures.append(chosen_sig)

        return selected

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

        eligible_records = [r.to_dict() for _, r in self.df_businesses.iterrows()]
        raw_success_scores = self.success_service.predict_success_scores(user_profile, eligible_records)

        # Min-max scaling across candidate set for ranking differentiation
        valid_succ = [s for s in raw_success_scores if s is not None]
        if valid_succ:
            min_s, max_s = min(valid_succ), max(valid_succ)
            if max_s > min_s:
                ranked_success_scores = [round((s - min_s) / (max_s - min_s), 4) if s is not None else None for s in raw_success_scores]
            else:
                ranked_success_scores = [0.50 if s is not None else None for s in raw_success_scores]
        else:
            ranked_success_scores = [None] * len(raw_success_scores)

        results = []
        for idx, row in enumerate(eligible_records):
            min_cap = float(row.get("min_capital", 0.0))
            budget_gap = max(0.0, min_cap - user_cap)
            affordable = (budget_gap == 0.0)

            s_cap = self.calculate_capital_score(user_cap, min_cap)
            s_skill, matched, gaps = self.calculate_skill_score(user_skills, str(row.get("core_skills", "")))
            s_exp = self.calculate_experience_score(user_exp, str(row.get("experience_level", "Beginner")))
            s_setup = self.calculate_setup_score(user_setups, str(row.get("business_setup", "")))
            s_time = self.calculate_time_score(available_time, str(row.get("business_setup", "")), str(row.get("people_needed", "")))
            s_team = self.calculate_team_score(user_exp, str(row.get("people_needed", "")))

            loc_result = self.market_analyzer.analyze_location_market(psgc, str(row.get("business_type", "")))
            s_loc = loc_result["location_score"]
            s_succ_ranked = ranked_success_scores[idx]
            s_succ_raw = raw_success_scores[idx]

            components = {
                "capital": s_cap,
                "skills": s_skill,
                "experience": s_exp,
                "setup": s_setup,
                "time": s_time,
                "location": s_loc,
                "success": s_succ_ranked,
                "team": s_team
            }

            final_score = combine_scores(components, self.weights)
            rec_score_pct = round(final_score * 100, 1)

            reasons = []
            if affordable:
                reasons.append(f"Within your starting capital (₱{user_cap:,.0f} vs ₱{min_cap:,.0f} minimum)")
            else:
                reasons.append(f"Catalog estimates ₱{min_cap:,.0f} for a full start; you are ₱{budget_gap:,.0f} short, so begin small and grow.")

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

            if s_succ_raw is not None:
                reasons.append(f"Model-based success score {int(round(s_succ_raw * 100))}% (one component of the ranking)")

            results.append({
                "id": int(row["id"]),
                "business_id": int(row["id"]),
                "business_type": row["business_type"],
                "category": row.get("category", "General"),
                "market_category": loc_result["category"],
                "startup_cost": row.get("startup_cost", f"₱{min_cap:,.0f}"),
                "min_capital": min_cap,
                "budget_gap": budget_gap,
                "affordable": affordable,
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
                "success_model_score": round(s_succ_raw * 100, 1) if s_succ_raw is not None else None,
                "component_scores": {
                    "capital": round(s_cap * 100, 1),
                    "skills": round(s_skill * 100, 1) if s_skill is not None else None,
                    "experience": round(s_exp * 100, 1),
                    "setup": round(s_setup * 100, 1),
                    "time": round(s_time * 100, 1),
                    "location": round(s_loc * 100, 1) if s_loc is not None else None,
                    "success": round(s_succ_ranked * 100, 1) if s_succ_ranked is not None else None,
                    "team": round(s_team * 100, 1)
                }
            })

        # Re-rank near-ties to ensure diverse top-5 candidate profiles
        return self.select_diverse_top_n(results, top_n=top_n)

BusinessRecommenderEngine = HybridBusinessRecommender
'''

# ======================================================================
# 3. templates/user/recommendations.html (Tips, badges, breakdown)
# ======================================================================
UPDATES["templates/user/recommendations.html"] = r'''{% extends "base.html" %}
{% block title %}Top Recommendations — SmallBiz Match{% endblock %}

{% block content %}
<div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 24px; flex-wrap: wrap; gap: 16px;">
  <div>
    <span class="mono-tag">FEASIBILITY MATCHES // ₱{{ "{:,.2f}".format(profile.capital) }} CAPITAL</span>
    <h2>Recommended Business Ideas</h2>
    <p class="subtitle" style="margin-bottom: 0;">
      Location: <strong>{{ profile.location_display or 'Philippine Dataset' }}</strong> · Experience: <strong>{{ profile.experience }}</strong>
    </p>
  </div>
  <a href="/find" class="btn btn-secondary btn-sm">Adjust Filters</a>
</div>

{% if not profile.skills or profile.skills | length == 0 %}
  <div class="alert alert-info" style="font-size: 13.5px; margin-bottom: 16px; border-left: 6px solid var(--color-brand);">
    <strong>Tip:</strong> Select your skills so similar businesses can be separated.
  </div>
{% endif %}

<div class="alert alert-info" style="font-size: 13.5px;">
  <strong>Notice:</strong> Recommendation Score is a weighted match of your inputs, not a probability of success. Time compatibility is estimated from the business setup and operational complexity.
</div>

{% for r in recs %}
  <div class="business-card">
    <div class="biz-cost-col">
      <div class="biz-cost-label">Required Capital</div>
      <div class="biz-cost-val">₱{{ "{:,.0f}".format(r.min_capital) }}</div>
      <div style="font-size: 12px; color: var(--color-ink-muted); margin-top: 4px;">{{ r.startup_cost }}</div>
    </div>

    <div class="biz-main-col">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
        <h3 style="margin: 0;">{{ r.business_type }}</h3>
        <span class="badge">{{ r.category }}</span>
        {% if r.market_category %}
          <span class="badge" style="background: #fdf3e7; color: var(--color-accent); border-color: var(--color-accent);">OSM: {{ r.market_category }}</span>
        {% endif %}
        {% if not r.affordable %}
          <span class="badge" style="background: #fff3cd; color: #856404; border-color: #ffeeba;">Start small — budget gap ₱{{ "{:,.0f}".format(r.budget_gap) }}</span>
        {% endif %}
      </div>
      <div class="biz-meta">
        Setup: <strong>{{ r.business_setup }}</strong> · Required Staff: <strong>{{ r.people_needed }}</strong> · Level: <strong>{{ r.experience_level }}</strong>
      </div>

      <div style="margin: 6px 0;">
        {% if r.matched_skills %}
          <div class="skills-match">✓ Matching Skills: {{ r.matched_skills | join(', ') }}</div>
        {% else %}
          <div style="font-size: 13px; color: var(--color-ink-muted);">No skills selected</div>
        {% endif %}
      </div>

      <div style="font-size: 13px; color: var(--color-ink-muted); margin: 6px 0; background: var(--color-surface-soft); padding: 8px 10px; border-left: 3px solid var(--color-brand);">
        <strong>Market Evidence:</strong> {{ r.location_evidence }}
      </div>

      <div style="margin-top: 8px;">
        <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--color-ink-muted); font-family: var(--font-mono);">Why Recommended:</span>
        <ul style="font-size: 13px; color: var(--color-ink); margin-left: 18px; margin-top: 2px;">
          {% for reason in r.reasons %}
            <li>{{ reason }}</li>
          {% endfor %}
        </ul>
      </div>

      <details style="margin-top: 10px; font-size: 13px;">
        <summary style="cursor: pointer; font-weight: 600; color: var(--color-brand); min-height: 44px; display: inline-flex; align-items: center;">View Score Breakdown</summary>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; margin-top: 8px; padding: 10px; background: var(--color-surface-soft);">
          <div>Capital: <strong>{{ r.component_scores.capital }}%</strong></div>
          <div>Skills: <strong>{{ r.component_scores.skills ~ '%' if r.component_scores.skills is not none else 'Omitted (No skills)' }}</strong></div>
          <div>Experience: <strong>{{ r.component_scores.experience }}%</strong></div>
          <div>Setup: <strong>{{ r.component_scores.setup }}%</strong></div>
          <div>Time: <strong>{{ r.component_scores.time }}%</strong></div>
          <div>Location: <strong>{{ r.component_scores.location ~ '%' if r.component_scores.location is not none else 'Not available' }}</strong></div>
          <div>Success Model: <strong>{{ r.component_scores.success ~ '%' if r.component_scores.success is not none else 'Not available' }}</strong></div>
          <div>Team Size: <strong>{{ r.component_scores.team }}%</strong></div>
        </div>
      </details>
    </div>

    <div class="biz-score-col">
      <div>
        <div class="score-num">{{ r.recommendation_score }}%</div>
        <div class="score-lbl">Recommendation Score</div>
      </div>
      <a href="{{ url_for('rec.pathway', biz_id=r.id) }}" class="btn btn-primary btn-sm btn-block">View Pathway</a>
    </div>
  </div>
{% else %}
  <div class="card card-editorial" style="border-left: 6px solid var(--color-accent);">
    <h3>No business recommendations available.</h3>
    <p style="margin-top: 8px;">
      Try adjusting your skills, location, or setup preferences.
    </p>
    <a href="/find" class="btn btn-primary" style="margin-top: 16px;">Adjust Inputs</a>
  </div>
{% endfor %}

<div class="card card-editorial" id="feedback-card" style="text-align: center; margin-top: 40px; background: var(--color-surface-soft);">
  <h4 style="margin-bottom: 6px;">User satisfaction (poll)</h4>
  <p style="font-size: 14px; color: var(--color-ink-muted); margin-bottom: 16px;">
    Are these business ideas feasible with your funds and aligned with your local market?
  </p>
  <div style="display: flex; justify-content: center; gap: 14px; flex-wrap: wrap;">
    <button onclick="sendFeedback('yes')" class="btn btn-primary btn-sm">👍 Yes, Realistic Match</button>
    <button onclick="sendFeedback('no')" class="btn btn-secondary btn-sm">👎 Not a Good Fit</button>
  </div>
</div>

<script>
function sendFeedback(choice) {
  const formData = new FormData();
  formData.append('rating', choice);
  formData.append('csrf_token', '{{ csrf_token() }}');
  fetch('/feedback', {
    method: 'POST',
    headers: { 'X-CSRF-Token': '{{ csrf_token() }}' },
    body: formData
  })
  .then(res => res.text())
  .then(html => { document.getElementById('feedback-card').innerHTML = html; });
}
</script>
{% endblock %}
'''

# ======================================================================
# 4. tests/test_hybrid_recommender.py (Updated test suite)
# ======================================================================
UPDATES["tests/test_hybrid_recommender.py"] = r'''import pytest
import pandas as pd
from ml.recommendation_engine import HybridBusinessRecommender
from ml.market_analyzer import PhilippineMarketAnalyzer
from config import Config

@pytest.fixture(scope="module")
def engine():
    return HybridBusinessRecommender()

def test_quezon_city_food_count_and_market_evidence(engine):
    """Task 1 Test: Quezon City/Food must return osm_count 3974 and distinct tier scores."""
    qc = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Quezon", case=False)
    ].iloc[0]
    res = engine.market_analyzer.analyze_location_market(qc["adm3_psgc"], "Bakery")
    assert res["osm_count"] == 3974, f"Expected 3974 Food POIs in Quezon City, got {res['osm_count']}"
    assert res["category"] == "Food"
    assert res["location_score"] in [0.75, 0.85, 0.90]
    assert "Mapped businesses in the available OpenStreetMap data: 3974 Food businesses in Quezon City" in res["evidence_text"]

def test_iloilo_city_missing_population_safe_handling(engine):
    """Task 1 Test: Iloilo City has no 2024 PSA population; must use raw count without crashing."""
    iloilo = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Iloilo", case=False)
    ].iloc[0]
    res = engine.market_analyzer.analyze_location_market(iloilo["adm3_psgc"], "Restaurant")
    assert res["population"] is None
    assert "Population data unavailable for this market calculation." in res["evidence_text"]
    assert res["location_score"] is not None

def test_hard_capital_filter_boundaries(engine):
    """Capital scoring test: recommend with capital=1000 returns 5 results with budget_gap and affordable."""
    recs = engine.recommend({"capital": 1000, "skills": []}, top_n=5)
    assert len(recs) == 5, f"Expected 5 results, got {len(recs)}"
    for r in recs:
        assert "budget_gap" in r
        assert "affordable" in r
        assert r["affordable"] == (r["min_capital"] <= 1000)
        assert r["budget_gap"] == max(0.0, r["min_capital"] - 1000)

def test_omitted_location_for_online_business(engine):
    """Task 2 Test: Location is omitted for online/unmapped businesses (score is None)."""
    qc = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Quezon", case=False)
    ].iloc[0]
    loc_res = engine.market_analyzer.analyze_location_market(qc["adm3_psgc"], "Freelancing")
    assert loc_res["location_score"] is None
    assert "omitted" in loc_res["evidence_text"].lower()

def test_empty_skills_omitted_from_scoring(engine):
    """Empty skills must leave the skills component out of the score (None) and renormalize remaining weights."""
    recs = engine.recommend({"capital": 20000, "skills": []}, top_n=5)
    assert len(recs) > 0
    assert any("No skills selected" in r["reasons"] for r in recs)
    assert recs[0]["component_scores"]["skills"] is None

def test_score_range_and_deterministic_sort(engine):
    """Recommendation scores strictly 0-100% and deterministically sorted."""
    qc = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Quezon", case=False)
    ].iloc[0]
    recs = engine.recommend({"capital": 50000, "skills": ["Marketing"], "location": qc["adm3_psgc"]}, top_n=5)
    for i in range(len(recs) - 1):
        assert recs[i]["raw_final_score"] >= recs[i+1]["raw_final_score"]
        assert 0.0 <= recs[i]["recommendation_score"] <= 100.0

def test_no_numeric_or_blank_business_type():
    """Verify that no business_type in final_business_dataset.csv is blank, 'nan', or all digits."""
    df = pd.read_csv(Config.FINAL_BUSINESSES_CSV)
    assert not df.empty, "Catalog should not be empty"
    for b_type in df["business_type"]:
        s = str(b_type).strip()
        assert s != "", "business_type should not be blank"
        assert s.lower() != "nan", "business_type should not be 'nan'"
        assert not s.isdigit(), f"business_type should not be numeric digits, got '{s}'"

def test_recommendation_weights_sum_to_one():
    """Verify that Config.RECOMMENDATION_WEIGHTS sums exactly to 1.0."""
    total = sum(Config.RECOMMENDATION_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6, f"Weights must sum to 1.0, got {total}"

def test_recommender_determinism_identical_runs(engine):
    """Verify two runs with identical inputs produce identical output."""
    profile = {
        "capital": 25000,
        "skills": ["Marketing", "Sales"],
        "experience": "Intermediate",
        "available_time": "5-6 hours/day",
        "setup": ["Online", "Home-Based"],
        "location": "1380400000"
    }
    run1 = engine.recommend(profile, top_n=5)
    run2 = engine.recommend(profile, top_n=5)

    assert len(run1) == len(run2) == 5
    for r1, r2 in zip(run1, run2):
        assert r1["id"] == r2["id"]
        assert r1["business_type"] == r2["business_type"]
        assert r1["recommendation_score"] == r2["recommendation_score"]
        assert r1["raw_final_score"] == r2["raw_final_score"]
'''

# ----------------------------------------------------------------------
# Apply all updates
# ----------------------------------------------------------------------
count = 0
for rel_path, content in UPDATES.items():
    p = ROOT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    count += 1
    print(f"  ✓ Patched ({count}/{len(UPDATES)}): {rel_path}")

print("\n" + "=" * 75)
print("🎉 All updates applied successfully!")
print("=" * 75)