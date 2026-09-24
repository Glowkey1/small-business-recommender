from ml.recommendation_engine import BusinessRecommenderEngine

def test_capital_filter():
    engine = BusinessRecommenderEngine()
    recs = engine.recommend({"capital": 1000, "skills": []}, top_n=5)
    assert len(recs) == 5, f"Expected 5 results, got {len(recs)}"
    for r in recs:
        assert "budget_gap" in r
        assert "affordable" in r
        assert r["affordable"] == (r["min_capital"] <= 1000)
        assert r["budget_gap"] == max(0.0, r["min_capital"] - 1000)
