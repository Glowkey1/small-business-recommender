import pytest
from app import create_app
from models import db
from models.business import Business

@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        test_biz = Business(
            business_type="Sample Test Agency",
            category="Services",
            startup_cost_display="₱15,000 - ₱30,000",
            min_capital=15000.0,
            core_skills="marketing, design",
            people_needed="2-3 people",
            minimum_requirements="Laptop, internet connection",
            strategies="Focus on client retention",
            risks="Client acquisition cost",
            business_setup="Online / Home-Based",
            experience_required="Beginner"
        )
        db.session.add(test_biz)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_pathway_unknown_business_returns_404(client):
    response = client.get("/pathway/NonexistentRandomBusiness123")
    assert response.status_code == 404
    html = response.get_data(as_text=True)
    assert "Pathway Unavailable" in html

def test_pathway_known_business_renders_successfully(client):
    response = client.get("/pathway/Sample Test Agency")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Sample Test Agency" in html
