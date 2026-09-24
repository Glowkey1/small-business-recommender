import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.test_client() as client:
        yield client

def test_pathway_known_catalog_business_renders_successfully(client):
    """Known catalog business (e.g. ID 1) returns 200 without DB dependency."""
    res = client.get("/pathway/1")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "9-Step Implementation Pathway" in html
    assert "The catalog does not list permit or licensing requirements" in html

def test_pathway_slash_name_redirects_cleanly(client):
    """Business names with '/' redirect 301 to ID URL."""
    res = client.get("/pathway/Hostel / PG", follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Hostel / PG" in html

def test_pathway_unknown_returns_404(client):
    """Unknown pathway returns friendly 404 template."""
    res = client.get("/pathway/9999")
    assert res.status_code == 404
    html = res.get_data(as_text=True)
    assert "Pathway Unavailable" in html

def test_all_catalog_pathways_return_200(client):
    """Verify all business IDs render 200 on fresh startup."""
    from ml.recommendation_engine import HybridBusinessRecommender
    engine = HybridBusinessRecommender()
    for idx, row in engine.df_businesses.iterrows():
        biz_id = int(row["id"])
        res = client.get(f"/pathway/{biz_id}")
        assert res.status_code == 200, f"Pathway for ID {biz_id} failed with {res.status_code}"
