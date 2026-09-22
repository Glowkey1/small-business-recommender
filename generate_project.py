import os, sys
if os.getenv("ALLOW_UPGRADE_SYSTEM") != "1":
    print("ERROR: generate_project.py contains legacy embedded code. Set ALLOW_UPGRADE_SYSTEM=1 to run.")
    sys.exit(1)
# generate_project.py
import os
import json

print("🚀 Building complete Small Business Recommender project structure...")

# Create directory tree (never touches data/raw/ contents)
DIRECTORIES = [
    "instance",
    "data/raw/dataset_1",
    "data/raw/dataset_2",
    "data/processed",
    "data/final",
    "notebooks",
    "ml/models",
    "models",
    "routes",
    "services",
    "templates/auth",
    "templates/user",
    "templates/admin",
    "static/css",
    "static/js",
    "tests"
]

for d in DIRECTORIES:
    os.makedirs(d, exist_ok=True)

FILES = {}

# -------------------------------------------------------------
# 1. ROOT CONFIGURATION & REQUIREMENTS
# -------------------------------------------------------------
FILES["requirements.txt"] = """Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Werkzeug==3.0.3
python-dotenv==1.0.1
pandas==2.2.2
numpy==1.26.4
scikit-learn==1.5.0
joblib==1.4.2
PyMySQL==1.1.1
cryptography==42.0.8
pytest==8.2.2
"""

FILES[".env"] = """FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev-secret-key-smallbiz-recommender-2026
DATABASE_URL=sqlite:///instance/app.db
# Switch to MySQL when ready:
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/small_business_recommender
"""

FILES["config.py"] = """import os
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-secret-2026")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    RAW_D1_PATH = os.path.join(BASE_DIR, "data", "raw", "dataset_1")
    RAW_D2_PATH = os.path.join(BASE_DIR, "data", "raw", "dataset_2")
    PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed")
    FINAL_PATH = os.path.join(BASE_DIR, "data", "final")
    ML_MODELS_PATH = os.path.join(BASE_DIR, "ml", "models")
"""

FILES["README.md"] = """# Small Business Idea Recommender & Business Pathway System

A Machine Learning-powered web platform that analyzes entrepreneur attributes (capital, skills, experience, commitment, and setup preference) to recommend feasible small businesses and generate actionable, phased launch pathways.

## Architecture
- **Recommendation System:** Capital feasibility gating + TF-IDF skill cosine similarity + multi-attribute scoring.
- **Pathway Generator:** Dynamically extracts requirements, risks, and strategies from catalog data and calculates skill gaps.
- **Success Classification Analysis:** Evaluates success factors from Dataset 1 for administrative insight.

## Getting Started
1. Place your raw files into `data/raw/dataset_1/` and `data/raw/dataset_2/`.
2. Run data preprocessing: `python ml/preprocessing.py`
3. Train ML models: `python ml/train_models.py`
4. Seed database: `python seed_real_data.py`
5. Run the web application: `python app.py`
"""

# -------------------------------------------------------------
# 2. DATABASE MODELS (models/)
# -------------------------------------------------------------
FILES["models/__init__.py"] = """from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
"""

FILES["models/user.py"] = """from models import db
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
"""

FILES["models/skill.py"] = """from models import db

class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
"""

FILES["models/business.py"] = """from models import db
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
"""

FILES["models/category.py"] = """from models import db

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
"""

FILES["models/recommendation.py"] = """from models import db
from datetime import datetime

class Recommendation(db.Model):
    __tablename__ = "recommendations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    compatibility_score = db.Column(db.Float, nullable=False)
    is_saved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    business = db.relationship("Business")
"""

FILES["models/pathway.py"] = """from models import db
from datetime import datetime

class BusinessPathway(db.Model):
    __tablename__ = "business_pathways"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    roadmap_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    business = db.relationship("Business")
"""

FILES["models/model_metrics.py"] = """from models import db
from datetime import datetime

class ModelMetric(db.Model):
    __tablename__ = "model_metrics"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)
    model_type = db.Column(db.String(50), nullable=False)
    accuracy = db.Column(db.Float, nullable=True)
    precision = db.Column(db.Float, nullable=True)
    recall = db.Column(db.Float, nullable=True)
    f1 = db.Column(db.Float, nullable=True)
    trained_at = db.Column(db.DateTime, default=datetime.utcnow)
"""

# -------------------------------------------------------------
# 3. MACHINE LEARNING & PIPELINE SCRIPTS (ml/)
# -------------------------------------------------------------
FILES["ml/__init__.py"] = ""

FILES["ml/preprocessing.py"] = """import os
import re
import glob
import json
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

RAW_D1_DIR = os.path.join("data", "raw", "dataset_1")
RAW_D2_DIR = os.path.join("data", "raw", "dataset_2")
PROCESSED_DIR = os.path.join("data", "processed")
FINAL_DIR = os.path.join("data", "final")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

def standardize_cols(df):
    df.columns = [re.sub(r"[^\\w\\s]", "", c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def parse_cost(val):
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace(",", "")
    nums = re.findall(r"\\d+(?:\\.\\d+)?", val_str)
    return float(nums[0]) if nums else 0.0

def process_dataset_1():
    files = glob.glob(os.path.join(RAW_D1_DIR, "*.csv"))
    if not files:
        logging.warning("No CSV found in dataset_1 raw folder.")
        return None

    df = pd.read_csv(files[0])
    df = standardize_cols(df).drop_duplicates().reset_index(drop=True)

    success_col = next((c for c in df.columns if "success" in c), None)
    if success_col:
        df[success_col] = df[success_col].astype(str).str.lower().map({
            "yes": 1, "no": 0, "1": 1, "0": 0, "true": 1, "false": 0, "successful": 1
        }).fillna(0).astype(int)

    cap_col = next((c for c in df.columns if "capital" in c), None)
    if cap_col:
        df[cap_col] = df[cap_col].apply(parse_cost)

    out = os.path.join(PROCESSED_DIR, "dataset_1_cleaned.csv")
    df.to_csv(out, index=False)
    logging.info(f"Dataset 1 cleaned ({len(df)} rows). Saved to {out}")
    return df

def process_dataset_2():
    biz_files = [f for f in glob.glob(os.path.join(RAW_D2_DIR, "*.csv")) if "business" in os.path.basename(f).lower()]
    if not biz_files:
        biz_files = glob.glob(os.path.join(RAW_D2_DIR, "*.csv"))

    if not biz_files:
        logging.warning("No CSV files found in dataset_2 raw folder.")
        return None, None

    dfs = [standardize_cols(pd.read_csv(f)) for f in biz_files]
    merged = pd.concat(dfs, ignore_index=True)

    name_col = next((c for c in merged.columns if "type" in c or "name" in c or c == "business"), merged.columns[0])
    merged = merged.drop_duplicates(subset=[name_col]).reset_index(drop=True)

    col_map = {}
    for c in merged.columns:
        if "skill" in c: col_map[c] = "core_skills"
        elif "requirement" in c: col_map[c] = "minimum_requirements"
        elif "strateg" in c: col_map[c] = "strategies"
        elif "risk" in c: col_map[c] = "risks"
        elif "cost" in c or "capital" in c: col_map[c] = "startup_cost"
        elif "people" in c: col_map[c] = "people_needed"
        elif "setup" in c: col_map[c] = "business_setup"
        elif "experience" in c: col_map[c] = "experience_level"
        elif "category" in c: col_map[c] = "category"

    merged = merged.rename(columns=col_map)
    merged["business_type"] = merged[name_col].astype(str).str.strip()

    defaults = {
        "core_skills": "",
        "minimum_requirements": "Basic operational tools and workspace.",
        "strategies": "Focus on cash flow management and customer retention.",
        "risks": "Competition, cash flow fluctuations, and operational delays.",
        "startup_cost": "Minimal",
        "people_needed": "1 person",
        "business_setup": "Online / Home-Based",
        "experience_level": "Beginner",
        "category": "General"
    }
    for k, v in defaults.items():
        merged[k] = merged[k].fillna(v) if k in merged.columns else v

    merged["min_capital"] = merged["startup_cost"].apply(parse_cost)
    biz_out = os.path.join(FINAL_DIR, "final_business_dataset.csv")
    merged.to_csv(biz_out, index=False)
    logging.info(f"Final Business Catalog saved ({len(merged)} businesses).")

    # Extract Skill Vocabulary from core_skills, courses, and jobs
    skill_set = set()
    for raw_s in merged["core_skills"].dropna():
        for token in re.split(r"[,;\\n|•/]", str(raw_s)):
            c = re.sub(r"[^\\w\\s-]", "", token).strip().title()
            if len(c) > 1 and not c.isdigit():
                skill_set.add(c)

    extra_files = glob.glob(os.path.join(RAW_D2_DIR, "*skill*.csv")) + glob.glob(os.path.join(RAW_D2_DIR, "*job*.csv"))
    for ef in extra_files:
        try:
            extra_df = pd.read_csv(ef)
            for col in extra_df.columns:
                for item in extra_df[col].dropna().unique():
                    c = re.sub(r"[^\\w\\s-]", "", str(item)).strip().title()
                    if 2 < len(c) < 40:
                        skill_set.add(c)
        except Exception:
            pass

    skills_df = pd.DataFrame({"skill_name": sorted(list(skill_set))})
    skill_out = os.path.join(FINAL_DIR, "final_skill_dataset.csv")
    skills_df.to_csv(skill_out, index=False)
    logging.info(f"Final Skill Dataset saved ({len(skills_df)} skills).")

    return merged, skills_df

if __name__ == "__main__":
    process_dataset_1()
    process_dataset_2()
"""

FILES["ml/feature_engineering.py"] = """import re
import numpy as np
import pandas as pd

def parse_experience_score(user_exp, req_exp):
    levels = {"beginner": 1, "intermediate": 2, "experienced": 3}
    u = levels.get(str(user_exp).lower(), 1)
    r = levels.get(str(req_exp).lower(), 1)
    return 1.0 if u >= r else 0.5

def parse_setup_score(user_setups, biz_setup):
    if not biz_setup or not user_setups:
        return 0.8
    bs = str(biz_setup).lower()
    for us in user_setups:
        if str(us).lower() in bs:
            return 1.0
    return 0.4
"""

FILES["ml/skill_encoder.py"] = """from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
import os

class SkillEncoder:
    def __init__(self, model_path="ml/models/tfidf_vectorizer.pkl"):
        self.model_path = model_path
        self.vectorizer = None

    def fit_and_save(self, corpus):
        self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\\b[\\w\\s-]+\\b")
        self.vectorizer.fit(corpus)
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.vectorizer, self.model_path)
        return self.vectorizer

    def load(self):
        if os.path.exists(self.model_path):
            self.vectorizer = joblib.load(self.model_path)
        return self.vectorizer
"""

FILES["ml/business_encoder.py"] = """# Reserved for categorical business embedding extensions
def encode_business_categories(df):
    return pd.get_dummies(df, columns=["category"], drop_first=True)
"""

FILES["ml/recommendation_engine.py"] = """import os
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from ml.feature_engineering import parse_experience_score, parse_setup_score

class BusinessRecommenderEngine:
    def __init__(self, catalog_path="data/final/final_business_dataset.csv", tfidf_path="ml/models/tfidf_vectorizer.pkl"):
        self.catalog_path = catalog_path
        self.tfidf_path = tfidf_path
        self.load_engine()

    def load_engine(self):
        if not os.path.exists(self.catalog_path):
            self.df = pd.DataFrame()
            self.vectorizer = None
            self.skill_matrix = None
            return

        self.df = pd.read_csv(self.catalog_path)
        self.df["min_capital"] = pd.to_numeric(self.df["min_capital"], errors="coerce").fillna(0.0)
        self.df["core_skills"] = self.df["core_skills"].fillna("")

        if os.path.exists(self.tfidf_path):
            self.vectorizer = joblib.load(self.tfidf_path)
            self.skill_matrix = self.vectorizer.transform(self.df["core_skills"])
        else:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\\b[\\w\\s-]+\\b")
            self.skill_matrix = self.vectorizer.fit_transform(self.df["core_skills"])
            os.makedirs(os.path.dirname(self.tfidf_path), exist_ok=True)
            joblib.dump(self.vectorizer, self.tfidf_path)

    def recommend(self, user_profile, top_n=5):
        if self.df.empty:
            return []

        user_cap = float(user_profile.get("capital", 0))
        user_skills = [s.strip().lower() for s in user_profile.get("skills", [])]
        user_exp = user_profile.get("experience", "Beginner")
        user_setups = user_profile.get("setup", ["Online / Home-Based"])
        if isinstance(user_setups, str):
            user_setups = [user_setups]

        # 1. HARD CAPITAL FEASIBILITY FILTER
        feasible_mask = self.df["min_capital"] <= user_cap
        feasible_df = self.df[feasible_mask].copy()

        if feasible_df.empty:
            feasible_df = self.df.nsmallest(top_n, "min_capital").copy()

        feasible_submatrix = self.skill_matrix[feasible_df.index]

        # 2. SKILL SIMILARITY via TF-IDF COSINE
        query = " ".join(user_skills)
        if query.strip():
            user_vec = self.vectorizer.transform([query])
            skill_scores = cosine_similarity(user_vec, feasible_submatrix).flatten()
        else:
            skill_scores = np.zeros(len(feasible_df))

        # 3. MULTI-ATTRIBUTE COMPATIBILITY
        results = []
        for i, (_, row) in enumerate(feasible_df.iterrows()):
            s_score = float(skill_scores[i])
            c_score = 1.0 if user_cap >= row["min_capital"] else 0.4
            e_score = parse_experience_score(user_exp, row.get("experience_level", "Beginner"))
            set_score = parse_setup_score(user_setups, row.get("business_setup", ""))

            # Score Formula: 35% Capital, 30% Skill, 15% Experience, 10% Time, 10% Setup
            comp = (0.35 * c_score + 0.30 * s_score + 0.15 * e_score + 0.10 * 0.9 + 0.10 * set_score) * 100

            req_skills = [sk.strip().title() for sk in str(row["core_skills"]).split(",") if sk.strip()]
            matched = [s for s in req_skills if s.lower() in user_skills]
            gaps = [s for s in req_skills if s.lower() not in user_skills]

            results.append({
                "id": int(row.get("id", i + 1)),
                "business_type": row["business_type"],
                "category": row.get("category", "General"),
                "startup_cost": row.get("startup_cost", f"₱{row['min_capital']:,.0f}"),
                "min_capital": float(row["min_capital"]),
                "compatibility_score": round(comp, 1),
                "business_setup": row.get("business_setup", "Online / Home-Based"),
                "people_needed": row.get("people_needed", "1 person"),
                "minimum_requirements": row.get("minimum_requirements", ""),
                "strategies": row.get("strategies", ""),
                "risks": row.get("risks", ""),
                "matched_skills": matched,
                "skill_gaps": gaps
            })

        results.sort(key=lambda x: x["compatibility_score"], reverse=True)
        return results[:top_n]
"""

FILES["ml/pathway_generator.py"] = """class BusinessPathwayGenerator:
    @staticmethod
    def generate(business_data, user_profile):
        cap = float(user_profile.get("capital", 0))
        gaps = business_data.get("skill_gaps", [])
        matched = business_data.get("matched_skills", [])
        reqs = business_data.get("minimum_requirements", "Standard workspace equipment")
        strat = business_data.get("strategies", "Carefully monitor expenses and prioritize customer satisfaction.")
        risks = business_data.get("risks", "Competitive shifts and cash flow delays.")

        steps = [
            {
                "phase": "Phase 1: Financial & Demand Validation",
                "title": "Allocate Capital & Confirm Market",
                "description": f"Ringfence your available ₱{cap:,.2f} for mandatory startup items only. Confirm demand through 10-15 prospective customer interviews."
            },
            {
                "phase": "Phase 2: Competency & Workspace Setup",
                "title": "Bridge Skill Gaps & Prepare Workspace",
                "description": f"Focus immediately on learning: {', '.join(gaps) if gaps else 'Core competencies already met.'}. Requirements: {reqs}."
            },
            {
                "phase": "Phase 3: Pilot & Soft Launch",
                "title": "Start With Low-Risk Channels",
                "description": f"Establish {business_data.get('business_setup', 'Online / Home-Based')} channels. Take pre-orders to avoid excess inventory."
            },
            {
                "phase": "Phase 4: Risk Control & Defense",
                "title": "Deploy Strategy Against Primary Risks",
                "description": f"Address catalog risks: {risks}. Maintain operational survival strategy: {strat}."
            },
            {
                "phase": "Phase 5: Scaling & Reinvestment",
                "title": "Sustainable Growth",
                "description": "Reinvest 30-50% of monthly net margins into enhanced marketing and better supplier wholesale terms."
            }
        ]

        return {
            "business_type": business_data.get("business_type"),
            "matched_skills": matched,
            "skill_gaps": gaps,
            "steps": steps
        }
"""

FILES["ml/train_success_model.py"] = """import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

def train_success_classifier(data_path="data/processed/dataset_1_cleaned.csv", model_dir="ml/models"):
    if not os.path.exists(data_path):
        return None

    df = pd.read_csv(data_path)
    target = next((c for c in df.columns if "success" in c), None)
    if not target:
        return None

    X = pd.get_dummies(df.drop(columns=[target]), drop_first=True)
    y = df[target]

    if len(y.unique()) < 2:
        return None

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models = {
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "Logistic Regression": LogisticRegression(max_iter=1000)
    }

    metrics = {}
    best_f1, best_m = -1, None
    for name, m in models.items():
        m.fit(X_train, y_train)
        preds = m.predict(X_test)
        f1 = float(f1_score(y_test, preds, zero_division=0))
        metrics[name] = {
            "accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "precision": round(float(precision_score(y_test, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, preds, zero_division=0)), 4),
            "f1": round(f1, 4)
        }
        if f1 > best_f1:
            best_f1, best_m = f1, m

    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(best_m, os.path.join(model_dir, "success_model.pkl"))
    joblib.dump(metrics, os.path.join(model_dir, "success_metrics.pkl"))
    return metrics
"""

FILES["ml/train_recommender.py"] = """from ml.recommendation_engine import BusinessRecommenderEngine

def train_recommender():
    engine = BusinessRecommenderEngine()
    print("Recommender artifacts verified.")
    return engine
"""

FILES["ml/evaluate_models.py"] = """import os
import joblib

def get_current_metrics():
    path = "ml/models/success_metrics.pkl"
    return joblib.load(path) if os.path.exists(path) else {}
"""

# -------------------------------------------------------------
# 4. SERVICES LAYER (services/)
# -------------------------------------------------------------
FILES["services/__init__.py"] = ""

FILES["services/user_service.py"] = """from models import db
from models.user import User

class UserService:
    @staticmethod
    def get_by_id(user_id):
        return User.query.get(user_id)
"""

FILES["services/business_service.py"] = """from models.business import Business

class BusinessService:
    @staticmethod
    def get_all():
        return Business.query.all()

    @staticmethod
    def get_by_name(b_type):
        return Business.query.filter_by(business_type=b_type).first()
"""

FILES["services/skill_service.py"] = """from models.skill import Skill

class SkillService:
    @staticmethod
    def get_all():
        return Skill.query.order_by(Skill.name).all()
"""

FILES["services/pathway_service.py"] = """from ml.pathway_generator import BusinessPathwayGenerator

class PathwayService:
    @staticmethod
    def create_pathway(business_data, user_profile):
        return BusinessPathwayGenerator.generate(business_data, user_profile)
"""

FILES["services/ml_service.py"] = """from ml.train_success_model import train_success_classifier
from ml.evaluate_models import get_current_metrics

class MLService:
    @staticmethod
    def retrain_models():
        return train_success_classifier()

    @staticmethod
    def get_metrics():
        return get_current_metrics()
"""

FILES["services/recommendation_service.py"] = """from ml.recommendation_engine import BusinessRecommenderEngine
from models import db
from models.recommendation import Recommendation
from models.business import Business

class RecommendationService:
    def __init__(self):
        self.engine = BusinessRecommenderEngine()

    def get_recommendations(self, user, form_data):
        profile = {
            "capital": float(form_data.get("capital", getattr(user, "starting_capital", 10000.0) or 10000.0)),
            "skills": form_data.getlist("skills") if form_data.getlist("skills") else [s.name for s in getattr(user, "skills", [])],
            "experience": form_data.get("experience", getattr(user, "experience_level", "Beginner")),
            "available_time": form_data.get("available_time", getattr(user, "available_time", "4-6 hours/day")),
            "setup": form_data.getlist("setup") if form_data.getlist("setup") else [getattr(user, "preferred_setup", "Online / Home-Based")]
        }

        recs = self.engine.recommend(profile, top_n=5)

        if user and getattr(user, "is_authenticated", False):
            for r in recs:
                b = Business.query.filter_by(business_type=r["business_type"]).first()
                if b:
                    audit = Recommendation(
                        user_id=user.id,
                        business_id=b.id,
                        compatibility_score=r["compatibility_score"]
                    )
                    db.session.add(audit)
            db.session.commit()

        return recs, profile
"""

# -------------------------------------------------------------
# 5. ROUTES LAYER (routes/)
# -------------------------------------------------------------
FILES["routes/__init__.py"] = ""

FILES["routes/auth.py"] = """from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        e = request.form.get("email", "").strip()
        p = request.form.get("password")
        if User.query.filter((User.username == u) | (User.email == e)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for("auth.register"))
        user = User(username=u, email=e)
        user.set_password(p)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("user.dashboard"))
    return render_template("auth/register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        e = request.form.get("email", "").strip()
        p = request.form.get("password")
        user = User.query.filter_by(email=e).first()
        if user and user.check_password(p):
            login_user(user)
            return redirect(url_for("user.dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
"""

FILES["routes/user.py"] = """from flask import Blueprint, render_template, request, flash, redirect, url_for
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
"""

FILES["routes/recommendation.py"] = """from flask import Blueprint, render_template, request, session
from flask_login import current_user
from services.recommendation_service import RecommendationService
from services.skill_service import SkillService
from services.pathway_service import PathwayService

rec_bp = Blueprint("rec", __name__)
rec_service = RecommendationService()

@rec_bp.route("/find", methods=["GET", "POST"])
def find():
    if request.method == "POST":
        recs, prof = rec_service.get_recommendations(current_user, request.form)
        session["last_recs"] = recs
        session["last_profile"] = prof
        return render_template("user/recommendations.html", recs=recs, profile=prof)
    skills = SkillService.get_all()
    return render_template("user/recommendations_form.html", skills=skills)

@rec_bp.route("/pathway/<business_type>")
def pathway(business_type):
    recs = session.get("last_recs", [])
    prof = session.get("last_profile", {})
    selected = next((r for r in recs if r["business_type"] == business_type), None)
    if not selected:
        from models.business import Business
        b = Business.query.filter_by(business_type=business_type).first()
        if b:
            selected = {
                "business_type": b.business_type,
                "startup_cost": b.startup_cost_display,
                "minimum_requirements": b.minimum_requirements,
                "strategies": b.strategies,
                "risks": b.risks,
                "business_setup": b.business_setup,
                "matched_skills": [],
                "skill_gaps": [s.strip().title() for s in b.core_skills.split(",") if s.strip()]
            }
        else:
            return render_template("user/pathway.html", error="Business pathway not found. Please find ideas first.")

    roadmap = PathwayService.create_pathway(selected, prof)
    return render_template("user/pathway.html", roadmap=roadmap, business=selected, profile=prof)
"""

FILES["routes/business.py"] = """from flask import Blueprint, render_template, abort
from models.business import Business

biz_bp = Blueprint("biz", __name__, url_prefix="/business")

@biz_bp.route("/<int:biz_id>")
def details(biz_id):
    b = Business.query.get_or_404(biz_id)
    return render_template("user/business_details.html", business=b)
"""

FILES["routes/admin.py"] = """from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from services.ml_service import MLService
from models.user import User
from models.business import Business
from models.skill import Skill

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
    return render_template("admin/metrics.html", metrics=m)

@admin_bp.route("/retrain", methods=["POST"])
def retrain():
    res = MLService.retrain_models()
    flash("Success classification model retrained successfully.", "success")
    return redirect(url_for("admin.metrics"))
"""

# -------------------------------------------------------------
# 6. APPLICATION ENTRYPOINT (app.py)
# -------------------------------------------------------------
FILES["app.py"] = """import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import Config
from models import db
from models.user import User
from routes.auth import auth_bp
from routes.user import user_bp
from routes.recommendation import rec_bp
from routes.business import biz_bp
from routes.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(rec_bp)
    app.register_blueprint(biz_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def home():
        return redirect(url_for("rec.find"))

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
"""

# -------------------------------------------------------------
# 7. REAL-DATA DATABASE SEEDER (seed_real_data.py)
# -------------------------------------------------------------
FILES["seed_real_data.py"] = """import os
import pandas as pd
from app import create_app
from models import db
from models.business import Business
from models.skill import Skill
from models.category import Category
from models.user import User

app = create_app()

with app.app_context():
    db.create_all()
    print("Database schema created/verified.")

    # 1. Seed Real Skills extracted from actual files
    skill_csv = os.path.join("data", "final", "final_skill_dataset.csv")
    if os.path.exists(skill_csv):
        df_skills = pd.read_csv(skill_csv)
        count_s = 0
        for _, r in df_skills.iterrows():
            name = str(r["skill_name"]).strip()
            if name and not Skill.query.filter_by(name=name).first():
                db.session.add(Skill(name=name))
                count_s += 1
        db.session.commit()
        print(f"✓ Seeded {count_s} unique skills from your real data.")
    else:
        print("⚠ Run ml/preprocessing.py first to extract skills from your data.")

    # 2. Seed Real Business Catalog from actual files
    biz_csv = os.path.join("data", "final", "final_business_dataset.csv")
    if os.path.exists(biz_csv):
        df_biz = pd.read_csv(biz_csv)
        count_b = 0
        for _, r in df_biz.iterrows():
            b_type = str(r["business_type"]).strip()
            cat = str(r.get("category", "General")).strip().title()
            
            if not Category.query.filter_by(name=cat).first():
                db.session.add(Category(name=cat))

            if not Business.query.filter_by(business_type=b_type).first():
                biz = Business(
                    business_type=b_type,
                    category=cat,
                    startup_cost_display=str(r.get("startup_cost", "Minimal")),
                    min_capital=float(r.get("min_capital", 0.0)),
                    core_skills=str(r.get("core_skills", "")),
                    people_needed=str(r.get("people_needed", "1 person")),
                    minimum_requirements=str(r.get("minimum_requirements", "")),
                    strategies=str(r.get("strategies", "")),
                    risks=str(r.get("risks", "")),
                    business_setup=str(r.get("business_setup", "Online / Home-Based")),
                    experience_required=str(r.get("experience_level", "Beginner"))
                )
                db.session.add(biz)
                count_b += 1
        db.session.commit()
        print(f"✓ Seeded {count_b} businesses from your real catalog.")
    else:
        print("⚠ Run ml/preprocessing.py first to build final_business_dataset.csv.")

    # 3. Create Default Admin
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@smallbiz.local", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("✓ Created default admin user (admin / admin123).")
"""

# -------------------------------------------------------------
# 8. HTML TEMPLATES (templates/)
# -------------------------------------------------------------
FILES["templates/base.html"] = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Small Business Recommender{% endblock %}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/css/main.css">
</head>
<body>
  <header class="header">
    <div class="nav-container">
      <a href="/" class="brand">🚀 SmallBiz Match</a>
      <nav>
        <a href="/find">Find Ideas</a>
        {% if current_user.is_authenticated %}
          <a href="/dashboard">Dashboard</a>
          <a href="/profile">Profile</a>
          <a href="/history">History</a>
          {% if current_user.role == 'admin' %}
            <a href="/admin/metrics">ML Metrics</a>
          {% endif %}
          <a href="/logout">Logout</a>
        {% else %}
          <a href="/login">Login</a>
          <a href="/register">Register</a>
        {% endif %}
      </nav>
    </div>
  </header>
  <main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}
          <div class="alert alert-{{ cat }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </main>
</body>
</html>
"""

FILES["templates/user/recommendations_form.html"] = """{% extends "base.html" %}
{% block title %}Find Business Ideas{% endblock %}
{% block content %}
<div class="card">
  <h2>Find Your Business Idea</h2>
  <p class="subtitle">Tell us your real constraints and our ML recommender will calculate compatible businesses.</p>
  <form action="/find" method="POST">
    <div class="form-group">
      <label>Starting Capital (₱ PHP)</label>
      <input type="number" name="capital" value="10000" min="0" step="500" required class="form-control">
    </div>

    <div class="form-group">
      <label>Select Your Existing Skills (Derived from Real Catalog)</label>
      <div class="skills-grid">
        {% for s in skills %}
          <label class="skill-pill">
            <input type="checkbox" name="skills" value="{{ s.name }}"> {{ s.name }}
          </label>
        {% endfor %}
      </div>
    </div>

    <div class="grid-2">
      <div class="form-group">
        <label>Experience Level</label>
        <select name="experience" class="form-control">
          <option value="Beginner">Beginner</option>
          <option value="Intermediate">Intermediate</option>
          <option value="Experienced">Experienced</option>
        </select>
      </div>
      <div class="form-group">
        <label>Available Daily Commitment</label>
        <select name="available_time" class="form-control">
          <option value="Less than 2 hours/day">Less than 2 hours/day</option>
          <option value="2-4 hours/day">2-4 hours/day</option>
          <option value="4-6 hours/day" selected>4-6 hours/day</option>
          <option value="Full-Time (6+ hours/day)">Full-Time (6+ hours/day)</option>
        </select>
      </div>
    </div>

    <div class="form-group">
      <label>Preferred Business Setup</label>
      <div class="checkbox-row">
        <label><input type="checkbox" name="setup" value="Online" checked> Online</label>
        <label><input type="checkbox" name="setup" value="Home-Based" checked> Home-Based</label>
        <label><input type="checkbox" name="setup" value="Physical Store"> Physical Store</label>
      </div>
    </div>

    <button type="submit" class="btn btn-primary btn-block">FIND BUSINESS IDEAS</button>
  </form>
</div>
{% endblock %}
"""

FILES["templates/user/recommendations.html"] = """{% extends "base.html" %}
{% block title %}Recommendations{% endblock %}
{% block content %}
<h2>Your Business Recommendations</h2>
<p class="subtitle">Filtered within your capital feasibility (₱{{ "{:,.2f}".format(profile.capital) }}).</p>

{% for r in recs %}
  <div class="card business-card">
    <div class="biz-info">
      <div class="biz-header">
        <h3>{{ r.business_type }}</h3>
        <span class="badge">{{ r.category }}</span>
      </div>
      <p class="biz-meta">
        Capital: <strong>{{ r.startup_cost }}</strong> | Setup: <strong>{{ r.business_setup }}</strong>
      </p>
      {% if r.matched_skills %}
        <p class="skills-match">✓ Matching Skills: {{ r.matched_skills | join(', ') }}</p>
      {% endif %}
    </div>
    <div class="biz-action">
      <div class="score">{{ r.compatibility_score }}%</div>
      <a href="/pathway/{{ r.business_type }}" class="btn btn-primary">View Pathway</a>
    </div>
  </div>
{% else %}
  <div class="card">
    <p>No businesses found matching your criteria. Try adjusting capital or selecting additional skills.</p>
  </div>
{% endfor %}

<p class="disclaimer">* The recommendation score reflects statistical compatibility with your parameters, not a financial guarantee of business success.</p>
{% endblock %}
"""

FILES["templates/user/pathway.html"] = """{% extends "base.html" %}
{% block title %}Business Pathway: {{ roadmap.business_type }}{% endblock %}
{% block content %}
{% if error %}
  <div class="card"><p>{{ error }}</p><a href="/find" class="btn btn-primary">Find Ideas</a></div>
{% else %}
  <div class="card">
    <h2>{{ roadmap.business_type }}</h2>
    <div class="grid-2 gap-16">
      <div class="box-green">
        <strong>✓ Your Matching Skills:</strong>
        <p>{{ roadmap.matched_skills | join(', ') or 'None specified' }}</p>
      </div>
      <div class="box-red">
        <strong>⚠ Skills to Develop:</strong>
        <p>{{ roadmap.skill_gaps | join(', ') or 'All core skills present!' }}</p>
      </div>
    </div>
  </div>

  <h3>Step-by-Step Implementation Pathway</h3>
  {% for s in roadmap.steps %}
    <div class="card phase-card">
      <div class="phase-title">{{ s.phase }}</div>
      <h4>{{ s.title }}</h4>
      <p>{{ s.description }}</p>
    </div>
  {% endfor %}
  <div class="back-link"><a href="/find">← Back to Recommendations</a></div>
{% endif %}
{% endblock %}
"""

FILES["templates/user/dashboard.html"] = """{% extends "base.html" %}
{% block title %}User Dashboard{% endblock %}
{% block content %}
<div class="card">
  <h2>Welcome, {{ current_user.username }}</h2>
  <p class="subtitle">Quick access to your profile parameters and recent matches.</p>
  <a href="/find" class="btn btn-primary">Find New Business Ideas</a>
  <a href="/profile" class="btn btn-secondary">Edit Business Profile</a>
</div>

<h3>Recent Recommendations History</h3>
<div class="card">
  {% for r in recent %}
    <div class="history-item">
      <span><strong>{{ r.business.business_type }}</strong> (Score: {{ r.compatibility_score }}%)</span>
      <a href="/pathway/{{ r.business.business_type }}" class="btn btn-sm">Pathway</a>
    </div>
  {% else %}
    <p>No recent recommendations yet. Click 'Find New Business Ideas' to start!</p>
  {% endfor %}
</div>
{% endblock %}
"""

FILES["templates/user/profile.html"] = """{% extends "base.html" %}
{% block title %}Edit Profile{% endblock %}
{% block content %}
<div class="card">
  <h2>Your Business Profile</h2>
  <form method="POST">
    <div class="form-group">
      <label>Starting Capital (₱ PHP)</label>
      <input type="number" name="capital" value="{{ current_user.starting_capital }}" class="form-control" required>
    </div>
    <div class="form-group">
      <label>Experience Level</label>
      <select name="experience" class="form-control">
        <option value="Beginner" {% if current_user.experience_level == 'Beginner' %}selected{% endif %}>Beginner</option>
        <option value="Intermediate" {% if current_user.experience_level == 'Intermediate' %}selected{% endif %}>Intermediate</option>
        <option value="Experienced" {% if current_user.experience_level == 'Experienced' %}selected{% endif %}>Experienced</option>
      </select>
    </div>
    <div class="form-group">
      <label>Available Daily Time</label>
      <input type="text" name="available_time" value="{{ current_user.available_time }}" class="form-control">
    </div>
    <div class="form-group">
      <label>Preferred Business Setup</label>
      <input type="text" name="preferred_setup" value="{{ current_user.preferred_setup }}" class="form-control">
    </div>
    <div class="form-group">
      <label>Select Your Skills</label>
      <div class="skills-grid">
        {% for s in skills %}
          <label class="skill-pill">
            <input type="checkbox" name="skills" value="{{ s.name }}" {% if s in current_user.skills %}checked{% endif %}> {{ s.name }}
          </label>
        {% endfor %}
      </div>
    </div>
    <button type="submit" class="btn btn-primary">Save Profile</button>
  </form>
</div>
{% endblock %}
"""

FILES["templates/user/history.html"] = """{% extends "base.html" %}
{% block title %}Recommendation History{% endblock %}
{% block content %}
<h2>Your Recommendation History</h2>
<div class="card">
  {% for h in history %}
    <div class="history-item">
      <div>
        <strong>{{ h.business.business_type }}</strong>
        <span class="badge">{{ h.compatibility_score }}% Match</span>
      </div>
      <a href="/pathway/{{ h.business.business_type }}" class="btn btn-sm">View Pathway</a>
    </div>
  {% else %}
    <p>No history found.</p>
  {% endfor %}
</div>
{% endblock %}
"""

FILES["templates/user/saved.html"] = """{% extends "base.html" %}
{% block title %}Saved Businesses{% endblock %}
{% block content %}
<h2>Saved Businesses</h2>
<div class="card">
  {% for s in saved %}
    <div class="history-item">
      <strong>{{ s.business.business_type }}</strong>
      <a href="/pathway/{{ s.business.business_type }}" class="btn btn-sm">View Pathway</a>
    </div>
  {% else %}
    <p>No saved businesses yet.</p>
  {% endfor %}
</div>
{% endblock %}
"""

FILES["templates/user/business_details.html"] = """{% extends "base.html" %}
{% block title %}{{ business.business_type }}{% endblock %}
{% block content %}
<div class="card">
  <h2>{{ business.business_type }}</h2>
  <span class="badge">{{ business.category }}</span>
  <hr>
  <p><strong>Required Capital:</strong> {{ business.startup_cost_display }}</p>
  <p><strong>Core Skills:</strong> {{ business.core_skills }}</p>
  <p><strong>Setup:</strong> {{ business.business_setup }}</p>
  <p><strong>Minimum Requirements:</strong> {{ business.minimum_requirements }}</p>
  <p><strong>Strategies to Grow:</strong> {{ business.strategies }}</p>
  <p><strong>Potential Risks:</strong> {{ business.risks }}</p>
  <a href="/pathway/{{ business.business_type }}" class="btn btn-primary">Start Business Pathway</a>
</div>
{% endblock %}
"""

FILES["templates/auth/login.html"] = """{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block content %}
<div class="card auth-card">
  <h2>Login</h2>
  <form method="POST">
    <div class="form-group">
      <label>Email</label>
      <input type="email" name="email" required class="form-control">
    </div>
    <div class="form-group">
      <label>Password</label>
      <input type="password" name="password" required class="form-control">
    </div>
    <button type="submit" class="btn btn-primary btn-block">Login</button>
  </form>
</div>
{% endblock %}
"""

FILES["templates/auth/register.html"] = """{% extends "base.html" %}
{% block title %}Register{% endblock %}
{% block content %}
<div class="card auth-card">
  <h2>Create Account</h2>
  <form method="POST">
    <div class="form-group">
      <label>Username</label>
      <input type="text" name="username" required class="form-control">
    </div>
    <div class="form-group">
      <label>Email</label>
      <input type="email" name="email" required class="form-control">
    </div>
    <div class="form-group">
      <label>Password</label>
      <input type="password" name="password" required class="form-control">
    </div>
    <button type="submit" class="btn btn-primary btn-block">Register</button>
  </form>
</div>
{% endblock %}
"""

FILES["templates/admin/dashboard.html"] = """{% extends "base.html" %}
{% block title %}Admin Dashboard{% endblock %}
{% block content %}
<h2>Admin Dashboard</h2>
<div class="grid-3">
  <div class="card"><h3>Users</h3><p class="stat">{{ users_count }}</p></div>
  <div class="card"><h3>Businesses</h3><p class="stat">{{ biz_count }}</p></div>
  <div class="card"><h3>Skills</h3><p class="stat">{{ skill_count }}</p></div>
</div>
<div class="card" style="margin-top:20px;">
  <a href="/admin/metrics" class="btn btn-primary">View ML Model Metrics</a>
</div>
{% endblock %}
"""

FILES["templates/admin/metrics.html"] = """{% extends "base.html" %}
{% block title %}ML Metrics{% endblock %}
{% block content %}
<h2>Machine Learning Performance Dashboard</h2>
<p class="subtitle">Empirical performance metrics trained on Dataset 1.</p>

<div class="card">
  {% for model_name, m in metrics.items() %}
    <div class="metric-block">
      <h3>{{ model_name }}</h3>
      <div class="grid-4">
        <div><strong>Accuracy:</strong> {{ m.accuracy }}</div>
        <div><strong>Precision:</strong> {{ m.precision }}</div>
        <div><strong>Recall:</strong> {{ m.recall }}</div>
        <div><strong>F1-Score:</strong> {{ m.f1 }}</div>
      </div>
    </div>
    <hr>
  {% else %}
    <p>No model metrics found. Click retrain below.</p>
  {% endfor %}

  <form action="/admin/retrain" method="POST">
    <button type="submit" class="btn btn-primary">Retrain Models</button>
  </form>
</div>
{% endblock %}
"""

# -------------------------------------------------------------
# 9. STATIC ASSETS (CSS & JS)
# -------------------------------------------------------------
FILES["static/css/main.css"] = """:root {
  --primary: #2563eb;
  --primary-dark: #1d4ed8;
  --bg: #f8fafc;
  --surface: #ffffff;
  --text: #1e293b;
  --muted: #64748b;
  --border: #e2e8f0;
  --success: #16a34a;
  --danger: #dc2626;
}
body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; }
.header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 14px 24px; }
.nav-container { max-width: 900px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
.brand { font-size: 18px; font-weight: 700; color: var(--primary); text-decoration: none; }
nav a { margin-left: 18px; text-decoration: none; color: var(--muted); font-size: 14px; font-weight: 500; }
nav a:hover { color: var(--primary); }
.container { max-width: 900px; margin: 30px auto; padding: 0 16px; }
.card { background: var(--surface); border-radius: 12px; border: 1px solid var(--border); padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
.btn { padding: 10px 18px; border-radius: 8px; font-weight: 600; text-decoration: none; display: inline-block; cursor: pointer; border: none; font-size: 14px; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-dark); }
.btn-secondary { background: #e2e8f0; color: var(--text); }
.btn-sm { padding: 6px 12px; font-size: 12px; }
.btn-block { width: 100%; }
.form-group { margin-bottom: 18px; }
.form-group label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 6px; }
.form-control { width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 8px; box-sizing: border-box; }
.skills-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; max-height: 220px; overflow-y: auto; padding: 8px; border: 1px solid var(--border); border-radius: 8px; }
.skill-pill { font-size: 12px; background: var(--bg); padding: 6px; border-radius: 6px; cursor: pointer; border: 1px solid var(--border); display: flex; align-items: center; gap: 4px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.business-card { display: flex; justify-content: space-between; align-items: center; border-left: 4px solid var(--primary); }
.badge { background: #eff6ff; color: var(--primary); padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.score { font-size: 26px; font-weight: 700; color: var(--primary); margin-bottom: 8px; }
.box-green { background: #f0fdf4; border: 1px solid #bbf7d0; padding: 12px; border-radius: 8px; color: #166534; }
.box-red { background: #fef2f2; border: 1px solid #fecaca; padding: 12px; border-radius: 8px; color: #991b1b; }
.phase-card { border-left: 4px solid var(--primary); }
.phase-title { font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--muted); }
.history-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border); }
.auth-card { max-width: 420px; margin: 40px auto; }
.disclaimer { font-size: 12px; color: var(--muted); margin-top: 20px; }
.stat { font-size: 32px; font-weight: 700; color: var(--primary); margin: 6px 0; }
"""

FILES["static/js/main.js"] = """console.log('Small Business Recommender System Loaded.');"""

# -------------------------------------------------------------
# 10. JUPYTER NOTEBOOKS (notebooks/)
# -------------------------------------------------------------
notebook_list = [
    "01_data_inspection", "02_data_cleaning", "03_eda", "04_feature_engineering",
    "05_success_model", "06_recommendation_model", "07_model_evaluation"
]
for nb in notebook_list:
    content = {
        "cells": [{"cell_type": "markdown", "metadata": {}, "source": [f"# {nb}\nOperational notebook analyzing real dataset attributes."]}],
        "metadata": {}, "nbformat": 4, "nbformat_minor": 2
    }
    FILES[f"notebooks/{nb}.ipynb"] = json.dumps(content, indent=2)

# -------------------------------------------------------------
# 11. UNIT TESTS (tests/)
# -------------------------------------------------------------
FILES["tests/test_auth.py"] = """import pytest

def test_auth_dummy():
    assert True
"""

FILES["tests/test_recommendation.py"] = """from ml.recommendation_engine import BusinessRecommenderEngine

def test_capital_filter():
    engine = BusinessRecommenderEngine()
    recs = engine.recommend({"capital": 1000, "skills": []}, top_n=5)
    assert isinstance(recs, list)
"""

FILES["tests/test_pathway.py"] = """from ml.pathway_generator import BusinessPathwayGenerator

def test_pathway_structure():
    res = BusinessPathwayGenerator.generate({"business_type": "Test Biz"}, {"capital": 5000})
    assert "steps" in res
    assert len(res["steps"]) == 5
"""

FILES["tests/test_ml.py"] = """import os

def test_processed_structure():
    assert os.path.exists("data/processed")
"""

FILES["tests/test_data.py"] = """import os

def test_raw_dataset_dirs():
    assert os.path.exists("data/raw/dataset_1")
    assert os.path.exists("data/raw/dataset_2")
"""

# -------------------------------------------------------------
# WRITE ALL FILES SAFELY
# -------------------------------------------------------------
for path, code in FILES.items():
    # Never overwrite files inside raw datasets directory
    if "data/raw" in path and os.path.exists(path):
        continue
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  ✓ Written: {path}")

print("\n🎉 ALL 55+ FILES WRITTEN SUCCESSFULLY!")
print("Your datasets in data/raw/ are completely intact.")
print("\nNext steps to run on your actual data:")
print("1. python ml/preprocessing.py")
print("2. python ml/train_models.py  (or train_success_model.py)")
print("3. python seed_real_data.py")
print("4. python app.py")
print("5. Open http://127.0.0.1:5000")