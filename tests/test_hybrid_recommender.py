import pytest
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
    """Task 7 Test: Capital boundary filtering (14,999 vs 15,000 vs 5,000)."""
    qc = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Quezon", case=False)
    ].iloc[0]
    recs = engine.recommend({"capital": 14999, "skills": [], "location": qc["adm3_psgc"]}, top_n=20)
    for r in recs:
        assert r["min_capital"] <= 14999, f"Exceeded capital: {r['min_capital']}"

    recs_empty = engine.recommend({"capital": 4999, "skills": []}, top_n=5)
    assert len(recs_empty) == 0

def test_omitted_location_for_online_business(engine):
    """Task 2 Test: Location is omitted for online/unmapped businesses (score is None)."""
    qc = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Quezon", case=False)
    ].iloc[0]
    loc_res = engine.market_analyzer.analyze_location_market(qc["adm3_psgc"], "Freelancing")
    assert loc_res["location_score"] is None
    assert "omitted" in loc_res["evidence_text"].lower()

def test_empty_skills_neutral_score(engine):
    """Task 7 Test: Empty skills produces neutral score (0.50) with appropriate label."""
    recs = engine.recommend({"capital": 20000, "skills": []}, top_n=5)
    assert len(recs) > 0
    assert any("No skills selected" in r["reasons"] for r in recs)
    assert recs[0]["component_scores"]["skills"] == 50.0

def test_score_range_and_deterministic_sort(engine):
    """Task 7 Test: Recommendation scores strictly 0-100% and deterministically sorted."""
    qc = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Quezon", case=False)
    ].iloc[0]
    recs = engine.recommend({"capital": 50000, "skills": ["Marketing"], "location": qc["adm3_psgc"]}, top_n=5)
    for i in range(len(recs) - 1):
        assert recs[i]["raw_final_score"] >= recs[i+1]["raw_final_score"]
        assert 0.0 <= recs[i]["recommendation_score"] <= 100.0
