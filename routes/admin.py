import json
import logging
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from config import Config
from services.ml_service import MLService
from models.user import User
from models.business import Business
from models.skill import Skill
from models.recommendation import RecommendationFeedback
import train_success_models

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
logger = logging.getLogger(__name__)

@admin_bp.before_request
@login_required
def verify_admin():
    if current_user.role != "admin":
        flash("Admin credentials required.", "danger")
        return redirect(url_for("user.dashboard"))

@admin_bp.route("/dashboard")
def dashboard():
    return render_template(
        "admin/dashboard.html",
        users_count=User.query.count(),
        biz_count=Business.query.count(),
        skill_count=Skill.query.count()
    )

@admin_bp.route("/metrics")
def metrics():
    metrics_data = {}
    if Config.SUCCESS_METRICS_JSON.exists():
        try:
            with open(Config.SUCCESS_METRICS_JSON, "r", encoding="utf-8") as f:
                metrics_data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading model metrics JSON: {e}")

    dataset_counts = {
        "business_ideas": 119,
        "raw_skills": 163,
        "master_skills": 158,
        "osm_records": 152657,
        "municipalities": 250,
        "success_records": 250
    }

    total_votes = RecommendationFeedback.query.count()
    positive_votes = RecommendationFeedback.query.filter_by(is_accurate=True).count()
    live_accuracy = round((positive_votes / total_votes * 100), 1) if total_votes > 0 else 0.0

    return render_template(
        "admin/metrics.html",
        metrics_data=metrics_data,
        dataset_counts=dataset_counts,
        total_votes=total_votes,
        positive_votes=positive_votes,
        live_accuracy=live_accuracy
    )

@admin_bp.route("/retrain", methods=["POST"])
@login_required
def retrain():
    res = train_success_models.train()
    if res:
        from routes.recommendation import engine
        engine.success_service._load()
        flash("Logistic Regression success prediction model retrained successfully.", "success")
    else:
        flash("Model retraining failed: Dataset 1 is missing, unreadable, or invalid.", "danger")
    return redirect(url_for("admin.metrics"))
