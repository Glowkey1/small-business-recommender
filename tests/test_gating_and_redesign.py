import pytest
from app import create_app
from models import db
from models.user import User

@pytest.fixture
def app_instance():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        user = User(username="founder_test", email="founder@example.ph")
        user.set_password("securepassword123")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app_instance):
    return app_instance.test_client()

def test_landing_page_renders_cleanly(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"CREATE FREE ACCOUNT" in res.data

def test_find_route_is_login_gated(client):
    res = client.get("/find", follow_redirects=False)
    assert res.status_code == 302
    assert "/login?next=%2Ffind" in res.headers["Location"]

def test_login_redirects_back_to_find(client):
    res = client.post("/login?next=%2Ffind", data={
        "email": "founder@example.ph",
        "password": "securepassword123"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Find Your Compatible Small Business" in res.data

def test_find_form_has_cascading_region_province_city(client):
    _login(client)
    res = client.get("/find")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "1. Region" in html
    assert "2. Province" in html
    assert "3. City / Municipality" in html
    assert 'id="regionSelect"' in html
    assert 'id="provinceSelect"' in html
    assert 'id="citySelect"' in html
    assert "CALABARZON (Region IV-A)" in html
    assert 'id="locationHierarchy"' in html
    assert "Batangas" in html
    assert "Cavite" in html

def test_pathway_remains_publicly_readable(client):
    res = client.get("/pathway/NonexistentRandom123")
    assert res.status_code == 404
    assert b"Pathway Unavailable" in res.data

def _login(client):
    return client.post("/login", data={
        "email": "founder@example.ph",
        "password": "securepassword123"
    }, follow_redirects=True)

def _submit_recommendation(client):
    from ml.recommendation_engine import HybridBusinessRecommender
    location = HybridBusinessRecommender().market_analyzer.df_market.iloc[0]["adm3_psgc"]
    return client.post("/find", data={
        "capital": "10000",
        "skills": ["Cooking"],
        "experience": "Beginner",
        "available_time": "5-6 hours/day",
        "setup": ["Online"],
        "location": location
    }, follow_redirects=True)

def test_results_page_shows_skill_gaps_capital_and_save(client):
    _login(client)
    res = _submit_recommendation(client)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Skills to build" in html
    assert "Start Small" in html
    assert "Full setup" in html
    assert "Affordable only" in html
    assert "Model Estimate (not ranked)" in html
    assert "save-btn" in html
    assert "Rate this match" not in html
    assert "rating-widget" not in html
    assert "skill-connected" in html
    assert 'data-affordable="false"' in html

def test_back_to_recommendations_reuses_last_results(client):
    _login(client)
    _submit_recommendation(client)
    res = client.get("/recommendations")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Find Your Compatible Small Business" not in html
    assert "View Pathway" in html
    assert "skill-connected" in html


def test_recommendations_without_session_redirects_to_find(client):
    _login(client)
    res = client.get("/recommendations", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/find")


def test_back_to_recommendations_preserves_saved_state(app_instance, client):
    from models.recommendation import Recommendation

    _login(client)
    _submit_recommendation(client)

    with app_instance.app_context():
        user = User.query.filter_by(email="founder@example.ph").first()
        rec = Recommendation.query.filter_by(user_id=user.id).first()
        rec.is_saved = True
        db.session.commit()

    res = client.get("/recommendations")
    assert res.status_code == 200
    assert "Saved" in res.get_data(as_text=True)


def test_save_recommendation_toggles_for_owner(app_instance, client):
    from models.recommendation import Recommendation
    from models.user import User

    _login(client)
    _submit_recommendation(client)

    with app_instance.app_context():
        user = User.query.filter_by(email="founder@example.ph").first()
        rec_id = Recommendation.query.filter_by(user_id=user.id).first().id

    res = client.post(f"/recommendations/{rec_id}/save")
    assert res.status_code == 200
    assert res.get_json() == {"saved": True}

    with app_instance.app_context():
        assert db.session.get(Recommendation, rec_id).is_saved is True

    res = client.post(f"/recommendations/{rec_id}/save")
    assert res.status_code == 200
    assert res.get_json() == {"saved": False}

    with app_instance.app_context():
        assert db.session.get(Recommendation, rec_id).is_saved is False
