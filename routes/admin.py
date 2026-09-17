from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from services.ml_service import MLService
from models.user import User
from models.business import Business
from models.skill import Skill
from models.recommendation import RecommendationFeedback

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.before_request
@login_required
def verify_admin():
    if current_user.role != "admin":
        flash("Admin credentials required.", "danger")
        return redirect(url_for("user.dashboard"))

@admin_bp.route("/dashboard")
def dashboard():
    return render_template("admin/dashboard.html",
                           users_count=User.query.count(),
                           biz_count=Business.query.count(),
                           skill_count=Skill.query.count())

@admin_bp.route("/metrics")
def metrics():
    m = MLService.get_metrics()
    total_votes = RecommendationFeedback.query.count()
    positive_votes = RecommendationFeedback.query.filter_by(is_accurate=True).count()
    live_accuracy = round((positive_votes / total_votes * 100), 1) if total_votes > 0 else 0.0

    return render_template("admin/metrics.html",
                           metrics=m,
                           total_votes=total_votes,
                           positive_votes=positive_votes,
                           live_accuracy=live_accuracy)

@admin_bp.route("/retrain", methods=["POST"])
@login_required
def retrain():
    res = MLService.retrain_models()
    if res and "Logistic Regression" in res:
        flash("Logistic Regression (scaled + balanced) model retrained successfully.", "success")
    else:
        flash("Model retraining failed: Dataset 1 is missing, unreadable, or has invalid labels.", "danger")
    return redirect(url_for("admin.metrics"))
