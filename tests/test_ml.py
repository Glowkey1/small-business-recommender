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
def test_skill_master_alias_map_integrity(engine):
    """Bug 2 Regression: Ensure skill_master.csv columns are not read backwards and aliases contain no commas."""
    # 1. Check raw alias resolution to single canonical name
    assert engine.skill_alias_map.get("ads") == "Advertising", f"Expected 'Advertising', got {engine.skill_alias_map.get('ads')}"
    assert engine.skill_alias_map.get("crm") == "CRM", f"Expected 'CRM', got {engine.skill_alias_map.get('crm')}"
    assert engine.skill_alias_map.get("seo") == "SEO", f"Expected 'SEO', got {engine.skill_alias_map.get('seo')}"
    assert engine.skill_alias_map.get("advertising") == "Advertising"

    # 2. Zero comma-containing values in alias_map
    corrupted = [(k, v) for k, v in engine.skill_alias_map.items() if "," in v]
    assert corrupted == [], f"Found {len(corrupted)} corrupted alias values with commas: {corrupted[:5]}"

    # 3. No catalog business produces a corrupted skill string
    for _, row in engine.df_businesses.iterrows():
        tokens = engine.parse_skills(row.get("core_skills", ""))
        for t in tokens:
            canon = engine.skill_alias_map.get(t.lower(), t)
            assert "," not in canon, f"Business {row.get('business_type')} produced corrupted skill canon: '{canon}'"