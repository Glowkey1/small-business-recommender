import pytest
import pandas as pd
from ml.recommendation_engine import HybridBusinessRecommender
from config import Config

@pytest.fixture(scope="module")
def engine():
    return HybridBusinessRecommender()

def test_calabarzon_location_market_evidence(engine):
    """Test CALABARZON market evidence using Lipa City, Batangas."""
    lipa = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Lipa", case=False)
    ].iloc[0]
    res = engine.market_analyzer.analyze_location_market(lipa["adm3_psgc"], "Bakery")
    assert res["osm_count"] > 0
    assert res["category"] == "Food"
    assert res["location_score"] in [0.75, 0.85, 0.90]
    assert "Lipa City" in res["evidence_text"] or "Lipa" in res["evidence_text"]

def test_lucena_city_missing_population_safe_handling(engine):
    """Test CALABARZON HUC with unlisted PSA population (Lucena City)."""
    lucena = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Lucena", case=False)
    ].iloc[0]
    res = engine.market_analyzer.analyze_location_market(lucena["adm3_psgc"], "Restaurant")
    assert res["population"] is None
    assert "Population data unavailable for this market calculation." in res["evidence_text"]
    assert res["location_score"] is not None

def test_hard_capital_filter_boundaries(engine):
    """Capital scoring test: recommend with capital=1000 returns 5 results with budget_gap and affordable."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend({"capital": 1000, "skills": [], "location": lipa["adm3_psgc"]}, top_n=5)
    assert len(recs) == 5, f"Expected 5 results, got {len(recs)}"
    for r in recs:
        assert "budget_gap" in r
        assert "full_setup_gap" in r
        assert "affordable" in r
        assert r["affordable"] == (r["micro_start_capital"] <= 1000)
        assert r["budget_gap"] == max(0.0, r["micro_start_capital"] - 1000)
        assert r["full_setup_gap"] == max(0.0, r["full_start_capital"] - 1000)

def test_affordable_results_are_preferred_when_enough_exist(engine):
    """With enough start-small-affordable options, unaffordable businesses are excluded."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend({"capital": 50000, "skills": [], "location": lipa["adm3_psgc"]}, top_n=5)
    assert len(recs) == 5
    assert all(r["affordable"] for r in recs)

def test_unsupported_market_category_returns_no_location_score(engine):
    """Categories without density/count columns are not scored as zero-density."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    res = engine.market_analyzer.analyze_location_market(lipa["adm3_psgc"], "Advertising Agency")
    assert res["location_score"] is None
    assert res["data_quality"] == "UNSUPPORTED"
    assert "not available" in res["evidence_text"].lower()

def test_omitted_location_for_online_business(engine):
    """Location is omitted for online/unmapped businesses (score is None)."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    loc_res = engine.market_analyzer.analyze_location_market(lipa["adm3_psgc"], "Freelancing")
    assert loc_res["location_score"] is None
    assert "omitted" in loc_res["evidence_text"].lower()

def test_empty_skills_omitted_from_scoring(engine):
    """Empty skills leaves skills component out of the score (None) and renormalizes weights."""
    recs = engine.recommend({"capital": 20000, "skills": []}, top_n=5)
    assert len(recs) > 0
    assert any("No skills selected" in r["reasons"] for r in recs)
    assert recs[0]["component_scores"]["skills"] is None

def test_skill_selected_results_only_include_connected_businesses(engine):
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend(
        {"capital": 10000, "skills": ["Cooking"], "location": lipa["adm3_psgc"]},
        top_n=5,
    )
    assert recs
    assert all(r["skill_related"] for r in recs)
    assert all(r["matched_skills"] for r in recs)
    assert all("Cooking" in r["related_skills"] for r in recs)


def test_sparse_skill_returns_fewer_than_five(engine):
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend(
        {"capital": 10000, "skills": ["Programming"], "location": lipa["adm3_psgc"]},
        top_n=5,
    )
    assert len(recs) == 1
    assert recs[0]["business_type"] == "App Development Studio"
    assert recs[0]["skill_related"] is True


def test_over_budget_skill_match_is_included(engine):
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend(
        {"capital": 10000, "skills": ["Programming"], "location": lipa["adm3_psgc"]},
        top_n=5,
    )
    assert recs[0]["affordable"] is False
    assert recs[0]["budget_gap"] > 0


def test_catalog_links_resolve_selected_skill_aliases(engine):
    assert 53 in engine.skill_related_ids("Menu Development")
    recs = engine.recommend(
        {"capital": 200000, "skills": ["Menu Development"]},
        top_n=5,
    )
    assert recs
    assert all(r["skill_related"] for r in recs)


def test_unmatched_skill_returns_no_results(engine):
    assert engine.recommend({"capital": 10000, "skills": ["NotARealSkill"]}, top_n=5) == []


def test_results_include_micro_and_full_capital(engine):
    """Every result exposes micro and full start capital for the results page."""
    recs = engine.recommend({"capital": 50000, "skills": ["Cooking"]}, top_n=5)
    assert len(recs) > 0
    for r in recs:
        assert "micro_start_capital" in r
        assert "full_start_capital" in r
        assert r["micro_start_capital"] >= 0
        assert r["full_start_capital"] >= 0
        assert r["micro_start_capital"] <= r["full_start_capital"]

def test_score_range_and_deterministic_sort(engine):
    """Recommendation scores strictly 0-100% and deterministically sorted."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend({"capital": 50000, "skills": ["Marketing"], "location": lipa["adm3_psgc"]}, top_n=5)
    for i in range(len(recs) - 1):
        assert recs[i]["raw_final_score"] >= recs[i+1]["raw_final_score"]
        assert 0.0 <= recs[i]["recommendation_score"] <= 100.0

def test_no_numeric_or_blank_business_type():
    """Verify that no business_type in catalog is blank, 'nan', or all digits."""
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

def test_mmr_selects_diverse_categories(engine):
    """MMR re-ranking prefers a different market category over a near-duplicate."""
    def candidate(name, category, score):
        return {
            "business_type": name,
            "category": category,
            "market_category": category,
            "business_setup": "Online",
            "matched_skills": ["Cooking"],
            "skill_gaps": [],
            "raw_final_score": score,
            "component_scores": {"skills": 80.0},
        }

    candidates = [
        candidate("A1", "Food", 0.90),
        candidate("A2", "Food", 0.895),
        candidate("B1", "Retail", 0.89),
        candidate("B2", "Retail", 0.885),
    ]
    picked = engine.select_diverse_top_n(candidates, top_n=2)
    assert [c["business_type"] for c in picked] == ["A1", "B1"]

def test_removed_skills_map_to_retained_matches(engine):
    """Pruned form skills still match via aliases instead of appearing as gaps."""
    from ml.skill_fields import canonical_skill
    assert canonical_skill("Menu") == "Cooking"
    assert canonical_skill("Recipe") == "Cooking"
    assert "Menu" not in engine.selectable_skills
    assert "Recipe" not in engine.selectable_skills
    assert "Cooking" in engine.selectable_skills

def test_success_model_not_weighted_in_ranking():
    """The success model remains advisory until it is validated."""
    assert Config.RECOMMENDATION_WEIGHTS["success"] == 0.0

def test_recommender_determinism_identical_runs(engine):
    """Verify two runs with identical inputs produce identical output."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    profile = {
        "capital": 25000,
        "skills": ["Marketing", "Sales"],
        "experience": "Intermediate",
        "available_time": "5-6 hours/day",
        "setup": ["Online", "Home-Based"],
        "location": lipa["adm3_psgc"]
    }
    run1 = engine.recommend(profile, top_n=5)
    run2 = engine.recommend(profile, top_n=5)

    assert len(run1) == len(run2)
    assert 0 < len(run1) <= 5
    for r1, r2 in zip(run1, run2):
        assert r1["id"] == r2["id"]
        assert r1["business_type"] == r2["business_type"]
        assert r1["recommendation_score"] == r2["recommendation_score"]
        assert r1["raw_final_score"] == r2["raw_final_score"]
