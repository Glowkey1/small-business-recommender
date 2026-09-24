import pytest
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
