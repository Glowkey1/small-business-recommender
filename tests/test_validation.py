import pytest
from app import create_app
from models import db
from models.user import User

@pytest.fixture
def app_instance():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})

    with app.app_context():
        db.create_all()
        u = User(username="validator_user", email="val@test.ph")
        u.set_password("validpassword123")
        db.session.add(u)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app_instance):
    c = app_instance.test_client()
    c.post("/login", data={"email": "val@test.ph", "password": "validpassword123"}, follow_redirects=True)
    return c

def test_validation_non_numeric_capital(client):
    res = client.post("/find", data={"capital": "abc", "location": "1380400000", "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Please enter a valid numeric starting capital" in res.data

def test_validation_negative_capital(client):
    res = client.post("/find", data={"capital": "-500", "location": "1380400000", "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Starting capital must be a non-negative number" in res.data

def test_validation_unknown_skill(client):
    res = client.post("/find", data={"capital": "10000", "skills": ["FakeAlienSkill99"], "location": "1380400000", "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Unrecognized skill" in res.data

def test_validation_invalid_location_psgc(client):
    res = client.post("/find", data={"capital": "10000", "location": "9999999999", "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"selected municipality PSGC code is invalid" in res.data

def test_validation_empty_setup(client):
    res = client.post("/find", data={"capital": "10000", "location": "1380400000"}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Please select at least one preferred business setup" in res.data
