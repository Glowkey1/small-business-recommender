from models import db
from datetime import datetime

class BusinessPathway(db.Model):
    __tablename__ = "business_pathways"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    roadmap_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    business = db.relationship("Business")
