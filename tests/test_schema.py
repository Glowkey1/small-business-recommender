from app import create_app
from models import db
import sqlalchemy as sa

def test_all_recommendation_tables_created():
    app = create_app(test_config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })

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

        removed_tables = {
            "recommendation_runs",
            "recommendation_items",
            "recommendation_ratings",
        }
        assert not (removed_tables & table_names)
