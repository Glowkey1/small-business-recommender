import pytest
from app import create_app
from models import db

@pytest.fixture
def app():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_register_empty_password_fails_cleanly(client):
    res = client.post("/register", data={
        "username": "tester",
        "email": "tester@example.com",
        "password": "",
        "confirm_password": ""
    }, follow_redirects=True)
    assert res.status_code == 400
    assert b"Password must be at least 6 characters long" in res.data
