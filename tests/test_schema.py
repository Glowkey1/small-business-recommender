from app import create_app
from models import db
import sqlalchemy as sa

def test_all_eight_tables_created():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()
        inspector = sa.inspect(db.engine)
        table_names = set(inspector.get_table_names())

        expected_tables = {
            "users", "skills", "user_skills", "businesses",
            "categories", "recommendations", "recommendation_feedback",
            "business_pathways", "model_metrics"
        }
        missing = expected_tables - table_names
        assert not missing, f"Tables missing: {missing}"
