import pytest
from ml.recommendation_engine import BusinessRecommenderEngine

@pytest.fixture(scope="module")
def engine():
    return BusinessRecommenderEngine()

def test_tfidf_vocabulary_does_not_swallow_whitespace(engine):
    vocab = getattr(engine.vectorizer, "vocabulary_", {})
    assert len(vocab) > 50, f"Vocabulary too small: {len(vocab)}"
    assert not any(" " in term for term in list(vocab.keys())[:50]), "Tokens contain swallowed spaces!"
    vec = engine.vectorizer.transform(["marketing creativity sales"])
    assert vec.nnz > 0, "Transform on standard skills produced zero features"

def test_skill_splitting_and_matching(engine):
    parsed = engine.parse_skills("Marketing creativity sales")
    assert "Marketing" in parsed
    assert "Creativity" in parsed
    assert "Sales" in parsed
    assert len(parsed) == 3

def test_recommender_produces_differentiated_scores(engine):
    user_low = {"capital": 5000, "skills": ["Cooking", "Baking"], "experience": "Beginner", "setup": ["Home-Based"]}
    user_high = {"capital": 150000, "skills": ["Web", "Development", "Graphic", "Design"], "experience": "Experienced", "setup": ["Online"]}

    recs_low = engine.recommend(user_low, top_n=5)
    recs_high = engine.recommend(user_high, top_n=5)

    assert len(recs_low) > 0
    assert len(recs_high) > 0
    scores_low = [r["compatibility_score"] for r in recs_low]
    assert not all(s == 69.0 for s in scores_low), "Still producing universal 69.0!"
    assert recs_low[0]["business_type"] != recs_high[0]["business_type"]
