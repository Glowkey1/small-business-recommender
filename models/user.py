from models import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user")
    
    starting_capital = db.Column(db.Float, default=10000.0)
    experience_level = db.Column(db.String(50), default="Beginner")
    available_time = db.Column(db.String(50), default="4-6 hours/day")
    preferred_setup = db.Column(db.String(100), default="Online / Home-Based")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    skills = db.relationship("Skill", secondary="user_skills", backref=db.backref("users", lazy="dynamic"))
    recommendations = db.relationship("Recommendation", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

user_skills = db.Table(
    "user_skills",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
)
