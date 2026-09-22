import re
import pytest
from app import create_app
from models import db
from models.user import User

@pytest.fixture
def app_instance():
    app = create_app()
    app.config["TESTING"] = False  # Enable real CSRF checks
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()
        u = User(username="sec_user", email="sec@test.ph")
        u.set_password("securepassword123")
        db.session.add(u)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

def test_csrf_protection_on_all_forms_when_not_testing(app_instance):
    """Bug 1 Regression: Ensure login, register, and profile succeed with CSRF tokens in production mode."""
    app_instance.config["TESTING"] = False

    with app_instance.test_client() as client:
        # A. Register form GET and POST
        res_get_reg = client.get("/register")
        assert res_get_reg.status_code == 200
        match_reg = re.search(r'name="csrf_token"\s+value="([^"]+)"', res_get_reg.get_data(as_text=True))
        assert match_reg, "templates/auth/register.html missing CSRF token input field"
        token_reg = match_reg.group(1)

        res_post_reg = client.post("/register", data={
            "username": "live_user_1",
            "email": "live1@test.ph",
            "password": "validpassword123",
            "confirm_password": "validpassword123",
            "csrf_token": token_reg
        }, follow_redirects=False)
        assert res_post_reg.status_code in [200, 302], f"Register failed with status {res_post_reg.status_code}"

        # B. Logout and Login form GET and POST
        client.get("/logout")
        res_get_login = client.get("/login")
        assert res_get_login.status_code == 200
        match_login = re.search(r'name="csrf_token"\s+value="([^"]+)"', res_get_login.get_data(as_text=True))
        assert match_login, "templates/auth/login.html missing CSRF token input field"
        token_login = match_login.group(1)

        res_post_login = client.post("/login", data={
            "email": "live1@test.ph",
            "password": "validpassword123",
            "csrf_token": token_login
        }, follow_redirects=False)
        assert res_post_login.status_code == 302, f"Login failed with status {res_post_login.status_code}"

        # C. Profile form GET and POST
        res_get_prof = client.get("/profile")
        assert res_get_prof.status_code == 200
        match_prof = re.search(r'name="csrf_token"\s+value="([^"]+)"', res_get_prof.get_data(as_text=True))
        assert match_prof, "templates/user/profile.html missing CSRF token input field"
        token_prof = match_prof.group(1)

        res_post_prof = client.post("/profile", data={
            "capital": "15000",
            "experience": "Intermediate",
            "available_time": "5-6 hours/day",
            "preferred_setup": "Online / Home-Based",
            "csrf_token": token_prof
        }, follow_redirects=False)
        assert res_post_prof.status_code in [200, 302], f"Profile POST failed with status {res_post_prof.status_code}"