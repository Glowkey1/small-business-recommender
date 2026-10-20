from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from flask_login import login_required, current_user
from config import Config
from ml.recommendation_engine import HybridBusinessRecommender
from ml.skill_fields import build_skill_groups, canonical_skill
from ml.validation import validate_recommendation_input
from models import db
from models.recommendation import Recommendation, RecommendationFeedback

rec_bp = Blueprint("rec", __name__)
engine = HybridBusinessRecommender()
skill_groups = build_skill_groups(engine.selectable_skills)
catalog_count = len(engine.df_businesses)
market_count = len(engine.market_analyzer.df_market)
region_count = (
    engine.market_analyzer.df_market["region_psgc"].nunique()
    if "region_psgc" in engine.market_analyzer.df_market.columns else 0
)

def coverage_context():
    return {
        "catalog_count": catalog_count,
        "market_count": market_count,
        "region_count": region_count,
    }

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
            form_data = {
                key: request.form.getlist(key) if key in ("skills", "setup") else request.form.get(key, "")
                for key in request.form.keys()
            }
            return render_template(
                "user/recommendations_form.html",
                skill_groups=skill_groups,
                hierarchy=hierarchy,
                form_data=form_data,
                errors=errors,
                **coverage_context()
            ), 400

        session["last_profile"] = clean_profile
        return redirect(url_for("rec.results"))

    preferred = current_user.preferred_setup or ""
    if preferred == "Online / Home-Based":
        saved_setups = ["Online", "Home-Based"]
    elif preferred in Config.ALLOWED_SETUPS:
        saved_setups = [preferred]
    else:
        saved_setups = ["Online"]

    saved_data = {
        "capital": current_user.starting_capital or 10000,
        "experience": current_user.experience_level if current_user.experience_level in Config.ALLOWED_EXPERIENCE else "Beginner",
        "available_time": current_user.available_time if current_user.available_time in Config.ALLOWED_TIMES else "5-6 hours/day",
        "setup": saved_setups,
        "skills": [canonical_skill(s.name) for s in current_user.skills],
    }

    hierarchy = engine.market_analyzer.get_location_hierarchy()
    return render_template(
        "user/recommendations_form.html",
        skill_groups=skill_groups,
        hierarchy=hierarchy,
        form_data=saved_data,
        errors=[],
        **coverage_context()
    )

def _annotate_saved(recs, user_id, create_missing=False):
    created = False
    for r in recs:
        existing = (
            Recommendation.query
            .filter_by(user_id=user_id, business_id=r["business_id"])
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
            .first()
        )
        if not existing and create_missing:
            existing = Recommendation(
                user_id=user_id,
                business_id=r["business_id"],
                compatibility_score=r["recommendation_score"]
            )
            db.session.add(existing)
            db.session.flush()
            created = True
        if existing:
            r["recommendation_id"] = existing.id
            r["is_saved"] = bool(existing.is_saved)
    if created:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            for r in recs:
                r.pop("recommendation_id", None)
                r.pop("is_saved", None)
    return recs

@rec_bp.route("/recommendations")
@login_required
def results():
    profile = session.get("last_profile")
    if not profile:
        return redirect(url_for("rec.find"))
    recs = engine.recommend(dict(profile), top_n=5)
    _annotate_saved(recs, current_user.id, create_missing=True)
    return render_template("user/recommendations.html", recs=recs, profile=profile)

@rec_bp.route("/recommendations/<int:rec_id>/save", methods=["POST"])
@login_required
def toggle_save(rec_id):
    rec = Recommendation.query.filter_by(id=rec_id, user_id=current_user.id).first_or_404()
    rec.is_saved = not bool(rec.is_saved)
    db.session.commit()
    return jsonify({"saved": bool(rec.is_saved)})

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
