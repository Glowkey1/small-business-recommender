import re
from flask import Blueprint, render_template, request, session
from flask_login import login_required, current_user
from services.recommendation_service import RecommendationService
from services.skill_service import SkillService
from services.pathway_service import PathwayService
from models import db
from models.recommendation import RecommendationFeedback

rec_bp = Blueprint("rec", __name__)
rec_service = RecommendationService()

@rec_bp.route("/find", methods=["GET", "POST"])
@login_required
def find():
    if request.method == "POST":
        recs, prof = rec_service.get_recommendations(current_user, request.form)
        session["last_recs"] = [
            {
                "id": r["id"],
                "business_type": r["business_type"],
                "compatibility_score": r["compatibility_score"],
                "startup_cost": r["startup_cost"],
                "min_capital": r["min_capital"],
                "matched_skills": r["matched_skills"],
                "skill_gaps": r["skill_gaps"]
            }
            for r in recs
        ]
        session["last_profile"] = prof
        return render_template("user/recommendations.html", recs=recs, profile=prof)

    skills = SkillService.get_all()
    return render_template("user/recommendations_form.html", skills=skills)

@rec_bp.route("/pathway/<business_type>")
def pathway(business_type):
    from models.business import Business

    recs = session.get("last_recs", [])
    prof = session.get("last_profile", {})
    selected = next((r for r in recs if r.get("business_type") == business_type), None)

    if not selected:
        b = Business.query.filter_by(business_type=business_type).first()
        if b:
            from ml.recommendation_engine import BusinessRecommenderEngine
            engine = BusinessRecommenderEngine()
            core_skills = engine.parse_skills(b.core_skills)
            user_skills = set(s.strip().lower() for s in prof.get("skills", []))

            selected = {
                "business_type": b.business_type,
                "startup_cost": b.startup_cost_display,
                "min_capital": b.min_capital,
                "minimum_requirements": b.minimum_requirements,
                "strategies": b.strategies,
                "risks": b.risks,
                "business_setup": b.business_setup,
                "matched_skills": [s for s in core_skills if s.lower() in user_skills],
                "skill_gaps": [s for s in core_skills if s.lower() not in user_skills]
            }
        else:
            return render_template(
                "user/pathway.html",
                roadmap=None,
                business=None,
                profile=prof,
                error=f"Business '{business_type}' does not exist in the active catalog."
            ), 404

    roadmap = PathwayService.create_pathway(selected, prof)
    return render_template("user/pathway.html", roadmap=roadmap, business=selected, profile=prof)

@rec_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    rating = request.form.get("rating")
    is_acc = True if rating == "yes" else False
    uid = current_user.id if getattr(current_user, "is_authenticated", False) else None

    feedback = RecommendationFeedback(user_id=uid, is_accurate=is_acc)
    db.session.add(feedback)
    db.session.commit()
    return "<div style='color: var(--color-brand); font-weight: 700; padding: 10px;'>✓ Salamat! Your feedback has been recorded.</div>"
