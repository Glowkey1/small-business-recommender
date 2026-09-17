from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User, user_skills
from models.skill import Skill
from models.business import Business
from models.category import Category
from models.recommendation import Recommendation, RecommendationFeedback
from models.pathway import BusinessPathway
from models.model_metrics import ModelMetric
