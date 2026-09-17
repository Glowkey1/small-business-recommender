from models import db
from datetime import datetime

class Business(db.Model):
    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    business_type = db.Column(db.String(200), nullable=False, unique=True)
    category = db.Column(db.String(100), default="General")
    startup_cost_display = db.Column(db.String(100), default="Minimal")
    min_capital = db.Column(db.Float, default=0.0)
    core_skills = db.Column(db.Text, default="")
    people_needed = db.Column(db.String(50), default="1 person")
    minimum_requirements = db.Column(db.Text, default="")
    strategies = db.Column(db.Text, default="")
    risks = db.Column(db.Text, default="")
    business_setup = db.Column(db.String(100), default="Online / Home-Based")
    experience_required = db.Column(db.String(50), default="Beginner")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
