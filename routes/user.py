from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db
from models.skill import Skill
from models.recommendation import Recommendation

user_bp = Blueprint("user", __name__)

@user_bp.route("/dashboard")
@login_required
def dashboard():
    recent = Recommendation.query.filter_by(user_id=current_user.id).order_by(Recommendation.created_at.desc()).limit(5).all()
    return render_template("user/dashboard.html", recent=recent)

@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.starting_capital = float(request.form.get("capital", 0))
        current_user.experience_level = request.form.get("experience")
        current_user.available_time = request.form.get("available_time")
        current_user.preferred_setup = request.form.get("preferred_setup")
        selected = request.form.getlist("skills")
        current_user.skills = Skill.query.filter(Skill.name.in_(selected)).all()
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("user.profile"))
    skills = Skill.query.order_by(Skill.name).all()
    return render_template("user/profile.html", skills=skills)

@user_bp.route("/history")
@login_required
def history():
    history_items = Recommendation.query.filter_by(user_id=current_user.id).order_by(Recommendation.created_at.desc()).all()
    return render_template("user/history.html", history=history_items)

@user_bp.route("/saved")
@login_required
def saved():
    saved_items = Recommendation.query.filter_by(user_id=current_user.id, is_saved=True).all()
    return render_template("user/saved.html", saved=saved_items)
