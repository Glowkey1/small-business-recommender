import pytest
from ml.recommendation_engine import HybridBusinessRecommender
from ml.market_analyzer import PhilippineMarketAnalyzer
from config import Config

@pytest.fixture(scope="module")
def engine():
    return HybridBusinessRecommender()

def test_hard_capital_filter(engine):
    """Unaffordable businesses must be excluded completely."""
    low_profile = {"capital": 5000, "skills": ["Cooking"], "experience": "Beginner", "setup": ["Home-Based"]}
    recs = engine.recommend(low_profile, top_n=10)
    for r in recs:
        assert r["min_capital"] <= 5000, f"Exceeded capital: {r['min_capital']} > 5000"

def test_skill_matching(engine):
    """User with Cooking skill must match businesses requiring Cooking."""
    profile = {"capital": 50000, "skills": ["Cooking"], "experience": "Beginner"}
    recs = engine.recommend(profile, top_n=5)
    has_cooking = any("Cooking" in r["matched_skills"] for r in recs)
    assert has_cooking, "Expected at least one business matching Cooking"

def test_empty_skills_neutral_handling(engine):
    """Selecting zero skills must not crash and should return a neutral score."""
    profile = {"capital": 20000, "skills": [], "experience": "Beginner"}
    recs = engine.recommend(profile, top_n=5)
    assert len(recs) > 0

def test_capital_too_low_empty_result(engine):
    """Entering ₱500 should return empty list if all ideas require more."""
    profile = {"capital": 500, "skills": []}
    recs = engine.recommend(profile, top_n=5)
    assert len(recs) == 0

def test_philippine_location_lookup(engine):
    """Valid municipality must return market evidence."""
    loc_data = engine.market_analyzer.analyze_location_market("Lipa City", "Food")
    assert loc_data["location_score"] > 0
    assert "Lipa City" in loc_data["evidence_text"]

def test_missing_population_safe_handling(engine):
    """Municipality with missing population must not divide by zero."""
    loc_data = engine.market_analyzer.analyze_location_market("Lucena", "Food")
    assert loc_data["location_score"] > 0
    assert "unavailable" in loc_data["evidence_text"].lower() or "density" not in loc_data["evidence_text"].lower()

def test_score_normalization_range(engine):
    """All recommendation scores must be within 0% to 100%."""
    profile = {"capital": 100000, "skills": ["Marketing", "Sales"], "location": "Quezon City"}
    recs = engine.recommend(profile, top_n=5)
    for r in recs:
        assert 0.0 <= r["recommendation_score"] <= 100.0
