from ml.recommendation_engine import BusinessRecommenderEngine

def test_capital_filter():
    engine = BusinessRecommenderEngine()
    recs = engine.recommend({"capital": 1000, "skills": []}, top_n=5)
    assert isinstance(recs, list)
