from ml.recommendation_engine import BusinessRecommenderEngine
from models import db
from models.recommendation import Recommendation
from models.business import Business

class RecommendationService:
    def __init__(self):
        self.engine = BusinessRecommenderEngine()

    def get_recommendations(self, user, form_data):
        profile = {
            "capital": float(form_data.get("capital", getattr(user, "starting_capital", 10000.0) or 10000.0)),
            "skills": form_data.getlist("skills") if form_data.getlist("skills") else [s.name for s in getattr(user, "skills", [])],
            "experience": form_data.get("experience", getattr(user, "experience_level", "Beginner")),
            "available_time": form_data.get("available_time", getattr(user, "available_time", "4-6 hours/day")),
            "setup": form_data.getlist("setup") if form_data.getlist("setup") else [getattr(user, "preferred_setup", "Online / Home-Based")]
        }

        recs = self.engine.recommend(profile, top_n=5)

        if user and getattr(user, "is_authenticated", False):
            for r in recs:
                b = Business.query.filter_by(business_type=r["business_type"]).first()
                if b:
                    audit = Recommendation(
                        user_id=user.id,
                        business_id=b.id,
                        compatibility_score=r["compatibility_score"]
                    )
                    db.session.add(audit)
            db.session.commit()

        return recs, profile
