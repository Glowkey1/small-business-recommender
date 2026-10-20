import os
import sys
import re
import json
import hashlib
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
from ml.skill_fields import SKILL_SYNONYM_MERGES, canonical_skill
from ml.skill_catalog import catalog_alias_map, catalog_skill_graph, catalog_skill_names
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

def safe_capital_value(value, fallback: float) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return fallback
    if not np.isfinite(amount) or amount < 0:
        return fallback
    return amount

class HybridBusinessRecommender:
    def __init__(self, catalog_path=None, tfidf_path=None):
        self.weights = self._load_weights()

        self.catalog_path = Path(catalog_path) if catalog_path else Config.FINAL_BUSINESSES_CSV
        self.tfidf_path = Path(tfidf_path) if tfidf_path else (Config.ML_MODELS_PATH / "tfidf_vectorizer.pkl")

        self.df_businesses = pd.DataFrame()
        self.vectorizer = None
        self.skill_alias_map = {}
        self.selectable_skills = []
        self.catalog_skills = []
        self.skill_related_by_name = {}
        self.skill_related_by_target = {}
        self.business_skill_map = {}

        self.market_analyzer = PhilippineMarketAnalyzer(Config.MUNICIPALITY_MARKET_CSV)
        self.success_service = SuccessModelService(Config.SUCCESS_MODEL_JOBLIB, Config.SUCCESS_METRICS_JSON)

        self._load_skill_master()
        self._load_skill_catalog()
        self.load_catalog()
        self.load_vectorizer()

    def _load_weights(self):
        path = Config.RECOMMENDATION_WEIGHTS_JSON
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                weights = payload.get("weights", payload)
                if not isinstance(weights, dict):
                    raise ValueError("weights payload must be a dictionary")
                expected = set(Config.RECOMMENDATION_WEIGHTS)
                if set(weights) != expected:
                    raise ValueError("weight keys do not match the recommender schema")
                weights = {key: float(value) for key, value in weights.items()}
                validate_weights(weights)
                logger.info("Loaded tuned recommendation weights from %s", path)
                return weights
            except Exception as exc:
                logger.error(
                    "Could not load tuned recommendation weights from %s: %s. "
                    "Using baseline weights.",
                    path,
                    exc,
                )
        return dict(Config.RECOMMENDATION_WEIGHTS)

    def _load_skill_master(self):
        if not Config.SKILL_MASTER_CSV.exists():
            return
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

            for alias, name in list(self.skill_alias_map.items()):
                self.skill_alias_map[alias] = canonical_skill(name)
            for old, new in SKILL_SYNONYM_MERGES.items():
                self.skill_alias_map[old.lower()] = canonical_skill(new)

            logger.info(f"Loaded {len(self.skill_alias_map)} clean skill aliases from skill_master.csv.")
        except Exception as e:
            logger.error(f"Error loading skill master: {e}")

    def _load_skill_catalog(self):
        try:
            self.catalog_skills = catalog_skill_names()
            for alias, target in catalog_alias_map().items():
                if alias and alias not in self.skill_alias_map:
                    self.skill_alias_map[alias] = target

            graph = catalog_skill_graph()
            self.skill_related_by_name = graph.get("by_name", {})
            self.skill_related_by_target = graph.get("by_target", {})
            self.business_skill_map = graph.get("business_skills", {})

            logger.info(
                f"Loaded {len(self.catalog_skills)} selectable skills and "
                f"{len(self.business_skill_map)} business skill links from skill_catalog.csv."
            )
        except Exception as e:
            logger.error(f"Error loading skill catalog: {e}")
            self.catalog_skills = []
            self.skill_related_by_name = {}
            self.skill_related_by_target = {}
            self.business_skill_map = {}

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
            master_set.update(self.catalog_skills)
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

    def artifact_version(self, k=5):
        payload = json.dumps(
            {
                "weights": self.weights,
                "k": k,
                "catalog_rows": len(self.df_businesses),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

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

    def _skill_target(self, skill):
        return canonical_skill(self.skill_alias_map.get(str(skill).lower(), str(skill)))

    def _biz_skill_targets(self, core_skills_str: str, business_id=None) -> list:
        if business_id is not None:
            mapped = self.business_skill_map.get(int(business_id))
            if mapped:
                return sorted(mapped, key=str.lower)

        biz_tokens = parse_skills_list(core_skills_str)
        if not biz_tokens:
            return []

        biz_canonical = []
        for t in biz_tokens:
            canon = self.skill_alias_map.get(t.lower(), t)
            if canon.lower() not in GENERIC_STOP_FRAGMENTS and "," not in canon:
                biz_canonical.append(canon)

        return biz_canonical or biz_tokens

    def _combined_skill_score(self, user_skills: list, biz_canonical: list, core_skills_str: str) -> tuple:
        if not biz_canonical:
            return (0.60, [], []) if user_skills else (None, [], [])
        if not user_skills:
            return None, [], biz_canonical

        user_target_set = {self._skill_target(s).lower() for s in user_skills if s}
        matched = [bs for bs in biz_canonical if bs.lower() in user_target_set]
        gaps = [bs for bs in biz_canonical if bs.lower() not in user_target_set]

        exact_ratio = len(matched) / len(biz_canonical) if biz_canonical else 0.0

        # Partial credit via cosine similarity from TF-IDF vectorizer
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

    def calculate_skill_score(self, user_skills: list, core_skills_str: str) -> tuple:
        biz_canonical = self._biz_skill_targets(core_skills_str)
        return self._combined_skill_score(user_skills, biz_canonical, core_skills_str)

    def skill_related_ids(self, skill) -> set:
        key = str(skill).strip().lower()
        ids = set(self.skill_related_by_name.get(key, set()))
        target = self._skill_target(skill).lower()
        ids.update(self.skill_related_by_target.get(target, set()))
        return ids

    def skill_match_details(self, user_skills: list, business_id: int, core_skills_str: str) -> dict:
        if not user_skills:
            return {
                "score": None,
                "matched": [],
                "matched_targets": [],
                "gaps": [],
                "related": [],
            }

        business_id = int(business_id)
        biz_canonical = self._biz_skill_targets(core_skills_str, business_id)
        score, matched_targets, gaps = self._combined_skill_score(
            user_skills, biz_canonical, core_skills_str
        )

        related = [
            s for s in user_skills
            if s and business_id in self.skill_related_ids(s)
        ]

        matched_target_lower = {m.lower() for m in matched_targets}
        for target in (self._skill_target(s) for s in related):
            if target.lower() not in matched_target_lower:
                matched_targets.append(target)
                matched_target_lower.add(target.lower())

        matched = [
            s for s in user_skills
            if s and self._skill_target(s).lower() in matched_target_lower
        ]
        for s in related:
            if s not in matched:
                matched.append(s)

        gaps = [g for g in gaps if g.lower() not in matched_target_lower]

        return {
            "score": score,
            "matched": matched,
            "matched_targets": matched_targets,
            "gaps": gaps,
            "related": related,
        }

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

    @staticmethod
    def _diversity_features(candidate: dict) -> tuple:
        category = str(candidate.get("market_category") or candidate.get("category") or "").strip().lower()
        setup = str(candidate.get("business_setup", "")).strip().lower()
        skills = {
            str(s).strip().lower()
            for s in list(candidate.get("matched_skills", [])) + list(candidate.get("skill_gaps", []))
            if s
        }
        return category, setup, skills

    def select_diverse_top_n(self, candidates: list, top_n: int = 5) -> list:
        if len(candidates) <= top_n:
            return list(candidates)

        selected = []
        pool = list(candidates)
        relevance_weight = 0.80

        while pool and len(selected) < top_n:
            best_idx = 0
            best_effective_score = -1e9
            best_raw_score = -1e9
            best_skill_score = -1e9

            for i, cand in enumerate(pool):
                raw_score = cand["raw_final_score"]
                skill_score = cand["component_scores"]["skills"] or 0.0
                max_similarity = 0.0

                if selected:
                    cat, setup, skills = self._diversity_features(cand)
                    for chosen in selected:
                        chosen_cat, chosen_setup, chosen_skills = self._diversity_features(chosen)
                        category_match = 1.0 if cat and cat == chosen_cat else 0.0
                        setup_match = 1.0 if setup and setup == chosen_setup else 0.0
                        union = skills | chosen_skills
                        skill_overlap = len(skills & chosen_skills) / len(union) if union else 0.0
                        similarity = 0.5 * category_match + 0.3 * skill_overlap + 0.2 * setup_match
                        max_similarity = max(max_similarity, similarity)

                effective_score = relevance_weight * raw_score - (1 - relevance_weight) * max_similarity

                if (effective_score > best_effective_score + 1e-9) or (
                    np.isclose(effective_score, best_effective_score, atol=1e-9)
                    and (raw_score > best_raw_score + 1e-9 or (
                        np.isclose(raw_score, best_raw_score, atol=1e-9)
                        and (skill_score > best_skill_score + 1e-9 or (
                            np.isclose(skill_score, best_skill_score, atol=1e-9)
                            and cand["business_type"] < pool[best_idx]["business_type"]
                        ))
                    ))
                ):
                    best_effective_score = effective_score
                    best_raw_score = raw_score
                    best_skill_score = skill_score
                    best_idx = i

            selected.append(pool.pop(best_idx))

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
            micro_cap = safe_capital_value(row.get("micro_start_capital"), min_cap)
            full_cap = safe_capital_value(row.get("full_start_capital"), min_cap)
            budget_gap = max(0.0, micro_cap - user_cap)
            full_setup_gap = max(0.0, full_cap - user_cap)
            affordable = (budget_gap == 0.0)

            s_cap = self.calculate_capital_score(user_cap, micro_cap)
            skill_info = self.skill_match_details(
                user_skills, int(row["id"]), str(row.get("core_skills", ""))
            )
            s_skill = skill_info["score"]
            matched = skill_info["matched"]
            gaps = skill_info["gaps"]
            related_skills = skill_info["related"]
            skill_related = bool(matched)
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
                reasons.append(f"Start-small cost fits your ₱{user_cap:,.0f} budget (₱{micro_cap:,.0f} to begin)")
            else:
                reasons.append(f"Start-small estimate is ₱{micro_cap:,.0f}; you are ₱{budget_gap:,.0f} short, so begin with the smallest version and reinvest.")
            if full_setup_gap > 0:
                reasons.append(f"Full setup budget is ₱{full_cap:,.0f} (₱{full_setup_gap:,.0f} beyond your current funds)")

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

            if s_loc is not None and s_loc >= 0.75:
                reasons.append("Has relevant market presence in your location")

            results.append({
                "id": int(row["id"]),
                "business_id": int(row["id"]),
                "business_type": row["business_type"],
                "category": row.get("category", "General"),
                "market_category": loc_result["category"],
                "startup_cost": row.get("startup_cost", f"₱{min_cap:,.0f}"),
                "min_capital": min_cap,
                "micro_start_capital": micro_cap,
                "full_start_capital": full_cap,
                "start_small_description": row.get("start_small_description", ""),
                "budget_gap": budget_gap,
                "full_setup_gap": full_setup_gap,
                "affordable": affordable,
                "people_needed": row.get("people_needed", "1 person"),
                "business_setup": row.get("business_setup", "Online / Home-Based"),
                "experience_level": row.get("experience_level", "Beginner"),
                "minimum_requirements": row.get("minimum_requirements", ""),
                "strategies": row.get("strategies", ""),
                "risks": row.get("risks", ""),
                "matched_skills": matched,
                "skill_gaps": gaps,
                "related_skills": related_skills,
                "skill_related": skill_related,
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

        if user_skills:
            # Strict skill mode: only return businesses connected to a selected skill.
            pool = [r for r in results if r["skill_related"]]
            if not pool:
                return []
        else:
            # Prefer start-small-affordable options; fall back to the closest matches
            affordable_results = [r for r in results if r["affordable"]]
            pool = affordable_results if len(affordable_results) >= top_n else results

        # Diverse top-N selection (MMR)
        top_results = self.select_diverse_top_n(pool, top_n=top_n)

        # Re-sort final top-5 descending by score so highest recommendation is first
        top_results.sort(
            key=lambda x: (-x["raw_final_score"], -x["component_scores"]["skills"] if x["component_scores"]["skills"] is not None else 0, x["business_type"])
        )
        return top_results

BusinessRecommenderEngine = HybridBusinessRecommender
