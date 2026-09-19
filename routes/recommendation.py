from flask import Blueprint, render_template, request, session, jsonify
from flask_login import login_required, current_user
from ml.recommendation_engine import HybridBusinessRecommender
from models import db
from models.recommendation import RecommendationFeedback
from models.business import Business

rec_bp = Blueprint("rec", __name__)
engine = HybridBusinessRecommender()

@rec_bp.route("/api/locations", methods=["GET"])
def api_locations():
    """Returns sorted list of Philippine municipalities for the frontend dropdown."""
    locs = engine.market_analyzer.get_locations()
    return jsonify({"locations": locs})

@rec_bp.route("/find", methods=["GET", "POST"])
@login_required
def find():
    if request.method == "POST":
        capital = float(request.form.get("capital", 0))
        skills = request.form.getlist("skills")
        experience = request.form.get("experience", "Beginner")
        available_time = request.form.get("available_time", "5-6 hours/day")
        setups = request.form.getlist("setup") or ["Online / Home-Based"]
        location = request.form.get("location", "").strip()

        user_profile = {
            "capital": capital,
            "skills": skills,
            "experience": experience,
            "available_time": available_time,
            "setup": setups,
            "location": location
        }

        recs = engine.recommend(user_profile, top_n=5)

        # Store minimal metadata in session to avoid 4KB cookie overflow
        session["last_recs"] = [
            {
                "id": r["id"],
                "business_type": r["business_type"],
                "category": r["category"],
                "recommendation_score": r["recommendation_score"],
                "startup_cost": r["startup_cost"],
                "min_capital": r["min_capital"],
                "matched_skills": r["matched_skills"],
                "skill_gaps": r["skill_gaps"]
            }
            for r in recs
        ]
        session["last_profile"] = user_profile

        return render_template("user/recommendations.html", recs=recs, profile=user_profile)

    # Standardized skills from skill_master.csv / catalog
    skills_list = []
    from config import Config
    import pandas as pd
    if Config.SKILL_MASTER_CSV.exists():
        df_s = pd.read_csv(Config.SKILL_MASTER_CSV)
        col = df_s.columns[0]
        skills_list = sorted([str(s).strip().title() for s in df_s[col].dropna().unique() if len(str(s).strip()) > 2])
    elif Config.FINAL_SKILLS_CSV.exists():
        df_s = pd.read_csv(Config.FINAL_SKILLS_CSV)
        col = df_s.columns[0]
        skills_list = sorted([str(s).strip().title() for s in df_s[col].dropna().unique() if len(str(s).strip()) > 2])

    municipalities = engine.market_analyzer.get_locations()

    return render_template(
        "user/recommendations_form.html",
        skills=skills_list,
        municipalities=municipalities
    )

@rec_bp.route("/pathway/<business_type>")
def pathway(business_type):
    # Fetch original business catalog row
    b = Business.query.filter_by(business_type=business_type).first()
    if not b:
        return render_template(
            "user/pathway.html",
            roadmap=None,
            business=None,
            error=f"Business '{business_type}' does not exist in the active Philippine catalog."
        ), 404

    prof = session.get("last_profile", {})
    from ml.skill_normalizer import parse_skills_list
    core_skills = parse_skills_list(b.core_skills)
    user_skills = set(str(s).lower() for s in prof.get("skills", []))

    matched = [s for s in core_skills if s.lower() in user_skills]
    gaps = [s for s in core_skills if s.lower() not in user_skills]

    business_data = {
        "business_type": b.business_type,
        "category": b.category,
        "startup_cost": b.startup_cost_display,
        "min_capital": b.min_capital,
        "people_needed": b.people_needed,
        "minimum_requirements": b.minimum_requirements,
        "strategies": b.strategies,
        "risks": b.risks,
        "business_setup": b.business_setup,
        "experience_level": b.experience_required,
        "core_skills": core_skills,
        "matched_skills": matched,
        "skill_gaps": gaps
    }

    # Construct the 9-Step Pathway
    steps = [
        {"step": 1, "title": "Check Requirements", "action": f"Review baseline facility requirements: {b.minimum_requirements}."},
        {"step": 2, "title": "Prepare Capital", "action": f"Ensure minimum seed fund of ₱{b.min_capital:,.0f} is allocated without taking high-interest debt."},
        {"step": 3, "title": "Prepare Skills", "action": f"Skills already possessed: {', '.join(matched) or 'None'}. Priority competencies to acquire: {', '.join(gaps) or 'All core skills present!'}"},
        {"step": 4, "title": "Choose Setup", "action": f"Set up operational channel: {b.business_setup}."},
        {"step": 5, "title": "Prepare Equipment / Resources", "action": f"Procure essential equipment for a team size of {b.people_needed}."},
        {"step": 6, "title": "Prepare Marketing", "action": "Establish online presence, local signage, and identify first 10 prospective customers."},
        {"step": 7, "title": "Start Operations", "action": "Launch with a soft-opening or pilot order batch to validate order turnaround."},
        {"step": 8, "title": "Monitor Risks", "action": f"Implement active defenses against catalog risks: {b.risks}."},
        {"step": 9, "title": "Improve and Grow", "action": f"Deploy core survival and scaling strategy: {b.strategies}."}
    ]

    return render_template(
        "user/pathway.html",
        business=business_data,
        steps=steps,
        profile=prof
    )

@rec_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    rating = request.form.get("rating")
    is_acc = True if rating == "yes" else False
    uid = current_user.id if getattr(current_user, "is_authenticated", False) else None
    feedback = RecommendationFeedback(user_id=uid, is_accurate=is_acc)
    db.session.add(feedback)
    db.session.commit()
    return "<div style='color: var(--color-brand); font-weight: 700; padding: 10px;'>✓ Salamat! Your feedback has been recorded.</div>"
