import re
from flask import Blueprint, render_template, request, session, redirect, url_for
from flask_login import login_required, current_user
from config import Config
from ml.recommendation_engine import HybridBusinessRecommender
from ml.validation import validate_recommendation_input
from models import db
from models.recommendation import Recommendation, RecommendationFeedback
from models.business import Business

rec_bp = Blueprint("rec", __name__)
engine = HybridBusinessRecommender()

@rec_bp.route("/api/locations", methods=["GET"])
def api_locations():
    return engine.market_analyzer.get_location_hierarchy()

@rec_bp.route("/find", methods=["GET", "POST"])
@login_required
def find():
    if request.method == "POST":
        clean_profile, errors = validate_recommendation_input(
            request.form, engine.market_analyzer, engine.selectable_skills
        )

        if errors:
            hierarchy = engine.market_analyzer.get_location_hierarchy()
            return render_template(
                "user/recommendations_form.html",
                skills=engine.selectable_skills,
                hierarchy=hierarchy,
                form_data=request.form,
                errors=errors
            ), 400

        recs = engine.recommend(clean_profile, top_n=5)

        if current_user.is_authenticated:
            try:
                for r in recs:
                    rec_row = Recommendation(
                        user_id=current_user.id,
                        business_id=r["business_id"],
                        compatibility_score=r["recommendation_score"]
                    )
                    db.session.add(rec_row)
                db.session.commit()
            except Exception:
                db.session.rollback()

        session["last_profile"] = clean_profile

        return render_template(
            "user/recommendations.html",
            recs=recs,
            profile=clean_profile
        )

    saved_data = {}
    if current_user.is_authenticated:
        saved_data["capital"] = current_user.starting_capital
        saved_data["experience"] = current_user.experience_level
        saved_data["available_time"] = current_user.available_time
        saved_data["setup"] = [current_user.preferred_setup] if current_user.preferred_setup else ["Online / Home-Based"]
        saved_data["skills"] = [s.name for s in current_user.skills]
    elif "last_profile" in session:
        saved_data = session["last_profile"]

    hierarchy = engine.market_analyzer.get_location_hierarchy()
    return render_template(
        "user/recommendations_form.html",
        skills=engine.selectable_skills,
        hierarchy=hierarchy,
        form_data=saved_data,
        errors=[]
    )

@rec_bp.route("/pathway/<int:biz_id>")
def pathway(biz_id):
    match = engine.df_businesses[engine.df_businesses["id"] == biz_id]
    if match.empty:
        return render_template("user/pathway.html", business=None, error="Pathway Unavailable"), 404

    b = match.iloc[0].to_dict()
    prof = session.get("last_profile", {})

    s_score, matched, gaps = engine.calculate_skill_score(
        prof.get("skills", []), str(b.get("core_skills", ""))
    )

    steps = [
        {"step": 1, "title": "Check Requirements", "action": f"Review minimum catalog requirements: {b.get('minimum_requirements', 'Standard operational tools')}."},
        {"step": 2, "title": "Prepare Capital", "action": f"The catalog estimates ₱{float(b.get('min_capital', 0)):,.0f} for a full start. You can begin with less and scale up."},
        {"step": 3, "title": "Prepare Skills", "action": f"Matching skills identified: {', '.join(matched) or 'None'}. Priority competencies to acquire: {', '.join(gaps) or 'All core skills present!'}"},
        {"step": 4, "title": "Choose Setup", "action": f"Establish the business setup: {b.get('business_setup', 'Online / Home-Based')}."},
        {"step": 5, "title": "Prepare Equipment / Resources", "action": f"Acquire necessary resources for {b.get('people_needed', '1 person')}."},
        {"step": 6, "title": "Prepare Marketing", "action": "Develop customer outreach and launch marketing materials."},
        {"step": 7, "title": "Start Operations", "action": "Commence initial business operations and fulfillment."},
        {"step": 8, "title": "Monitor Risks", "action": f"Implement safeguards against catalog-documented risks: {b.get('risks', 'Market competition')}."},
        {"step": 9, "title": "Improve the Business", "action": f"Deploy core growth strategy: {b.get('strategies', 'Maintain cost discipline')}."}
    ]

    return render_template(
        "user/pathway.html",
        business=b,
        steps=steps,
        matched_skills=matched,
        skill_gaps=gaps,
        profile=prof
    )

@rec_bp.route("/pathway/<path:business_type>")
def pathway_by_name(business_type):
    clean_name = str(business_type).strip().lower()
    match = engine.df_businesses[
        engine.df_businesses["business_type"].astype(str).str.strip().str.lower() == clean_name
    ]
    if match.empty:
        return render_template("user/pathway.html", business=None, error="Pathway Unavailable"), 404

    biz_id = int(match.iloc[0]["id"])
    return redirect(url_for("rec.pathway", biz_id=biz_id), code=301)

@rec_bp.route("/feedback", methods=["POST"])
@login_required
def submit_feedback():
    rating = request.form.get("rating")
    is_acc = True if rating == "yes" else False
    uid = current_user.id if current_user.is_authenticated else None

    feedback = RecommendationFeedback(user_id=uid, is_accurate=is_acc)
    db.session.add(feedback)
    db.session.commit()
    return "<div style='color: var(--color-brand); font-weight: 700; padding: 10px;'>✓ Salamat! Your feedback has been recorded.</div>"
