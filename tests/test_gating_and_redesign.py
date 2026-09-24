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

def test_pathway_remains_publicly_readable(client):
    res = client.get("/pathway/NonexistentRandom123")
    assert res.status_code == 404
    assert b"Pathway Unavailable" in res.data
