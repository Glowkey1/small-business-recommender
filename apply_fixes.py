# apply_fixes.py
import os

print("=" * 80)
print("Applying all fixes: Account Gating, Philippine Design System, ML Models, & Git Config...")
print("=" * 80)

# Clean up deprecated files
old_attr = os.path.join("data", "raw", "dataset_2", "business_attributes.csv")
if os.path.exists(old_attr):
    os.remove(old_attr)
    print(f"  ✓ Deleted deprecated lookup table: {old_attr}")

stale_vec = os.path.join("ml", "models", "tfidf_vectorizer.pkl")
if os.path.exists(stale_vec):
    os.remove(stale_vec)
    print(f"  ✓ Removed stale vectorizer: {stale_vec}")

UPDATES = {}

# ----------------------------------------------------------------------
# 1. config.py
# ----------------------------------------------------------------------
UPDATES["config.py"] = r'''import os
import re
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

def resolve_db_uri():
    env_url = os.getenv("DATABASE_URL")
    default_uri = f"sqlite:///{os.path.join(INSTANCE_DIR, 'app.db').replace(os.sep, '/')}"

    if not env_url or not env_url.strip():
        return default_uri

    env_url = env_url.strip()

    if not env_url.startswith("sqlite:///"):
        return env_url

    path_part = env_url[len("sqlite:///"):]

    if os.path.isabs(path_part) or re.match(r"^[A-Za-z]:[/\\]", path_part):
        return env_url

    abs_path = os.path.join(BASE_DIR, path_part).replace(os.sep, "/")
    return f"sqlite:///{abs_path}"

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-secret-2026")
    SQLALCHEMY_DATABASE_URI = resolve_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BASE_DIR = BASE_DIR
    RAW_D1_PATH = os.path.join(BASE_DIR, "data", "raw", "dataset_1")
    RAW_D2_PATH = os.path.join(BASE_DIR, "data", "raw", "dataset_2")
    PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed")
    FINAL_PATH = os.path.join(BASE_DIR, "data", "final")
    ML_MODELS_PATH = os.path.join(BASE_DIR, "ml", "models")
'''

# ----------------------------------------------------------------------
# 2. app.py (Landing route, custom login message, table creation)
# ----------------------------------------------------------------------
UPDATES["app.py"] = r'''import os
from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db
from models.user import User
from routes.main import main_bp
from routes.auth import auth_bp
from routes.user import user_bp
from routes.recommendation import rec_bp
from routes.business import biz_bp
from routes.admin import admin_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"❌ Could not initialize database at: {app.config['SQLALCHEMY_DATABASE_URI']}")
            print(f"   Reason: {e}")
            raise

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Create a free account or sign in to get your personalized business matches."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(rec_bp)
    app.register_blueprint(biz_bp)
    app.register_blueprint(admin_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
'''

# ----------------------------------------------------------------------
# 3. routes/main.py (Public Landing Page)
# ----------------------------------------------------------------------
UPDATES["routes/main.py"] = r'''from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def landing():
    return render_template("main/landing.html")
'''

# ----------------------------------------------------------------------
# 4. routes/auth.py (Safe next URL redirection & form validation)
# ----------------------------------------------------------------------
UPDATES["routes/auth.py"] = r'''import re
from urllib.parse import urlsplit
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)

def is_safe_url(target):
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    next_page = request.args.get("next")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("A valid email address is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("auth/register.html", username=username, email=email, next=next_page), 400

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already registered.", "danger")
            return render_template("auth/register.html", username=username, email=email, next=next_page), 400

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Mabuhay! Your account has been created.", "success")

        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for("rec.find"))

    return render_template("auth/register.html", next=next_page)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_page = request.args.get("next")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("rec.find"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", next=next_page)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.landing"))
'''

# ----------------------------------------------------------------------
# 5. routes/recommendation.py (Gated /find, small cookies, feedback)
# ----------------------------------------------------------------------
UPDATES["routes/recommendation.py"] = r'''import re
from flask import Blueprint, render_template, request, session
from flask_login import login_required, current_user
from services.recommendation_service import RecommendationService
from services.skill_service import SkillService
from services.pathway_service import PathwayService
from models import db
from models.recommendation import RecommendationFeedback

rec_bp = Blueprint("rec", __name__)
rec_service = RecommendationService()

@rec_bp.route("/find", methods=["GET", "POST"])
@login_required
def find():
    if request.method == "POST":
        recs, prof = rec_service.get_recommendations(current_user, request.form)
        session["last_recs"] = [
            {
                "id": r["id"],
                "business_type": r["business_type"],
                "compatibility_score": r["compatibility_score"],
                "startup_cost": r["startup_cost"],
                "min_capital": r["min_capital"],
                "matched_skills": r["matched_skills"],
                "skill_gaps": r["skill_gaps"]
            }
            for r in recs
        ]
        session["last_profile"] = prof
        return render_template("user/recommendations.html", recs=recs, profile=prof)

    skills = SkillService.get_all()
    return render_template("user/recommendations_form.html", skills=skills)

@rec_bp.route("/pathway/<business_type>")
def pathway(business_type):
    from models.business import Business

    recs = session.get("last_recs", [])
    prof = session.get("last_profile", {})
    selected = next((r for r in recs if r.get("business_type") == business_type), None)

    if not selected:
        b = Business.query.filter_by(business_type=business_type).first()
        if b:
            from ml.recommendation_engine import BusinessRecommenderEngine
            engine = BusinessRecommenderEngine()
            core_skills = engine.parse_skills(b.core_skills)
            user_skills = set(s.strip().lower() for s in prof.get("skills", []))

            selected = {
                "business_type": b.business_type,
                "startup_cost": b.startup_cost_display,
                "min_capital": b.min_capital,
                "minimum_requirements": b.minimum_requirements,
                "strategies": b.strategies,
                "risks": b.risks,
                "business_setup": b.business_setup,
                "matched_skills": [s for s in core_skills if s.lower() in user_skills],
                "skill_gaps": [s for s in core_skills if s.lower() not in user_skills]
            }
        else:
            return render_template(
                "user/pathway.html",
                roadmap=None,
                business=None,
                profile=prof,
                error=f"Business '{business_type}' does not exist in the active catalog."
            ), 404

    roadmap = PathwayService.create_pathway(selected, prof)
    return render_template("user/pathway.html", roadmap=roadmap, business=selected, profile=prof)

@rec_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    rating = request.form.get("rating")
    is_acc = True if rating == "yes" else False
    uid = current_user.id if getattr(current_user, "is_authenticated", False) else None

    feedback = RecommendationFeedback(user_id=uid, is_accurate=is_acc)
    db.session.add(feedback)
    db.session.commit()
    return "<div style='color: var(--color-brand); font-weight: 700; padding: 10px;'>✓ Salamat! Your feedback has been recorded.</div>"
'''

# ----------------------------------------------------------------------
# 6. ml/preprocessing.py (Attribute derivation from real data)
# ----------------------------------------------------------------------
UPDATES["ml/preprocessing.py"] = r'''import os
import re
import glob
import logging
import pandas as pd
import numpy as np
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

RAW_D1_DIR = Config.RAW_D1_PATH
RAW_D2_DIR = Config.RAW_D2_PATH
PROCESSED_DIR = Config.PROCESSED_PATH
FINAL_DIR = Config.FINAL_PATH

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

old_attr_file = os.path.join(RAW_D2_DIR, "business_attributes.csv")
if os.path.exists(old_attr_file):
    os.remove(old_attr_file)

def standardize_cols(df):
    df.columns = [re.sub(r"[^\w\s]", "", c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def parse_cost(val):
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace(",", "")
    nums = re.findall(r"\d+(?:\.\d+)?", val_str)
    return float(nums[0]) if nums else 0.0

def parse_people_needed(text):
    if pd.isna(text) or text is None:
        return None
    cleaned = str(text).strip().lower()

    if "solo" in cleaned or cleaned in {"1", "single", "individual"}:
        return (1, 1)

    m_range = re.search(r"(\d+)\s*[-–—to]+\s*(\d+)", cleaned)
    if m_range:
        return (int(m_range.group(1)), int(m_range.group(2)))

    m_plus = re.search(r"(\d+)\s*\+", cleaned)
    if m_plus:
        n = int(m_plus.group(1))
        return (n, int(n * 2))

    m_single = re.search(r"\b(\d+)\b", cleaned)
    if m_single:
        n = int(m_single.group(1))
        return (n, n)

    return None

def capital_tier(min_people, max_people):
    avg = (min_people + max_people) / 2.0
    if avg <= 1:
        return 5000.0, "₱5,000 - ₱15,000", "Online / Home-Based"
    if avg <= 3:
        return 15000.0, "₱15,000 - ₱30,000", "Home-Based"
    if avg <= 6:
        return 35000.0, "₱35,000 - ₱60,000", "Physical Store"
    if avg <= 12:
        return 75000.0, "₱75,000 - ₱120,000", "Physical Store"
    return 150000.0, "₱150,000 - ₱250,000+", "Physical Store / Commercial"

EXPERIENCED_KEYWORDS = [
    "certified", "certification", "license", "licensed", "regulatory", "compliance",
    "consultancy", "consultant", "architect", "engineering", "legal", "clinical",
    "manufacturing", "factory", "plant", "heavy equipment", "specialized"
]

INTERMEDIATE_KEYWORDS = [
    "studio", "agency", "commercial kitchen", "technician", "commercial equipment",
    "workshop", "inventory management", "staff management", "portfolio", "permits",
    "machinery", "professional", "advanced", "specialist", "salon", "kitchen space"
]

def derive_experience_level(reqs_text):
    if pd.isna(reqs_text) or not reqs_text:
        return "Beginner", True

    text = str(reqs_text).lower()
    for kw in EXPERIENCED_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text):
            return "Experienced", False

    for kw in INTERMEDIATE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text):
            return "Intermediate", False

    return "Beginner", True

PHYSICAL_STORE_KEYWORDS = [
    "shop", "store", "kitchen", "space", "warehouse", "facility", "outlet",
    "salon", "restaurant", "center", "centre", "clinic", "counter", "premises"
]

SERVICE_MOBILE_KEYWORDS = [
    "vehicle", "transport", "van", "truck", "motorcycle", "bike", "on-site",
    "mobile", "cleaning equipment", "field", "visiting", "tools bag"
]

ONLINE_HOME_KEYWORDS = [
    "laptop", "internet", "computer", "phone", "smartphone", "desk", "wifi",
    "software", "pc", "online", "digital", "camera"
]

def derive_business_setup(reqs_text, baseline_setup):
    if pd.isna(reqs_text) or not reqs_text:
        return baseline_setup, True

    text = str(reqs_text).lower()
    has_physical = any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in PHYSICAL_STORE_KEYWORDS)
    has_mobile = any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in SERVICE_MOBILE_KEYWORDS)
    has_online = any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in ONLINE_HOME_KEYWORDS)

    if has_physical:
        return "Physical Store", False
    if has_mobile:
        return "Service / Mobile", False
    if has_online:
        return "Online / Home-Based", False

    return baseline_setup, True

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
    biz_files = [
        f for f in glob.glob(os.path.join(RAW_D2_DIR, "*.csv"))
        if "business" in os.path.basename(f).lower() and "attribute" not in os.path.basename(f).lower()
    ]
    if not biz_files:
        biz_files = [f for f in glob.glob(os.path.join(RAW_D2_DIR, "*.csv")) if "attribute" not in os.path.basename(f).lower()]

    if not biz_files:
        logging.error("No catalog CSV files found in dataset_2 raw folder.")
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
        elif "people" in c: col_map[c] = "people_needed"
        elif "category" in c: col_map[c] = "category"

    merged = merged.rename(columns=col_map)
    merged["business_type"] = merged[name_col].astype(str).str.strip()

    if "id" in merged.columns:
        merged = merged.drop(columns=["id"])
    merged.insert(0, "id", range(1, len(merged) + 1))

    unparseable_people_count = 0
    exp_default_count = 0
    setup_default_count = 0

    min_caps = []
    startup_costs = []
    setups = []
    exp_levels = []

    for _, row in merged.iterrows():
        p_raw = row.get("people_needed", "")
        reqs_raw = row.get("minimum_requirements", "")

        headcount = parse_people_needed(p_raw)
        if headcount is None:
            unparseable_people_count += 1
            min_p, max_p = (1, 2)
        else:
            min_p, max_p = headcount

        tier_cap, tier_cost_str, baseline_setup = capital_tier(min_p, max_p)
        exp_lvl, exp_is_default = derive_experience_level(reqs_raw)
        if exp_is_default:
            exp_default_count += 1

        setup, setup_is_default = derive_business_setup(reqs_raw, baseline_setup)
        if setup_is_default:
            setup_default_count += 1

        min_caps.append(tier_cap)
        startup_costs.append(tier_cost_str)
        setups.append(setup)
        exp_levels.append(exp_lvl)

    merged["min_capital"] = min_caps
    merged["startup_cost"] = startup_costs
    merged["business_setup"] = setups
    merged["experience_level"] = exp_levels

    if "category" not in merged.columns:
        merged["category"] = "General"
    else:
        merged["category"] = merged["category"].fillna("General")

    merged["core_skills"] = merged.get("core_skills", "").fillna("")
    merged["minimum_requirements"] = merged.get("minimum_requirements", "Basic workspace and standard equipment.").fillna("Basic workspace and standard equipment.")
    merged["strategies"] = merged.get("strategies", "Focus on customer satisfaction and cash flow control.").fillna("Focus on customer satisfaction and cash flow control.")
    merged["risks"] = merged.get("risks", "Competition and operational delays.").fillna("Competition and operational delays.")

    final_biz_path = os.path.join(FINAL_DIR, "final_business_dataset.csv")
    merged.to_csv(final_biz_path, index=False)
    logging.info(f"Final Business Catalog saved to {final_biz_path}")

    skill_set = set()
    for raw_s in merged["core_skills"].dropna():
        for token in re.split(r"[,;\n|•/\s]+", str(raw_s)):
            c = re.sub(r"[^\w-]", "", token).strip().title()
            if len(c) > 1 and not c.isdigit():
                skill_set.add(c)

    skills_df = pd.DataFrame({"skill_name": sorted(list(skill_set))})
    skill_out = os.path.join(FINAL_DIR, "final_skill_dataset.csv")
    skills_df.to_csv(skill_out, index=False)
    logging.info(f"Final Skill Dataset saved ({len(skills_df)} skills).")

    return merged, skills_df

if __name__ == "__main__":
    process_dataset_1()
    df, _ = process_dataset_2()
    if df is not None:
        print("\n" + "=" * 60)
        print("RESULTING CATALOG DISTRIBUTIONS (N=119)")
        print("=" * 60)
        print("\n--- min_capital value_counts ---")
        print(df['min_capital'].value_counts())
        print("\n--- business_setup value_counts ---")
        print(df['business_setup'].value_counts())
        print("\n--- experience_level value_counts ---")
        print(df['experience_level'].value_counts())
        print("=" * 60)
'''

# ----------------------------------------------------------------------
# 7. ml/recommendation_engine.py
# ----------------------------------------------------------------------
UPDATES["ml/recommendation_engine.py"] = r'''import os
import re
import sys
import joblib
import logging
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

logger = logging.getLogger(__name__)

class BusinessRecommenderEngine:
    def __init__(self, catalog_path=None, tfidf_path=None):
        self.catalog_path = catalog_path or os.path.join(Config.FINAL_PATH, "final_business_dataset.csv")
        self.tfidf_path = tfidf_path or os.path.join(Config.ML_MODELS_PATH, "tfidf_vectorizer.pkl")
        self.load_engine()

    def load_engine(self):
        if not os.path.exists(self.catalog_path):
            logger.error(f"Catalog missing at {self.catalog_path}")
            self.df = pd.DataFrame()
            self.vectorizer = None
            self.skill_matrix = None
            return

        self.df = pd.read_csv(self.catalog_path)
        self.df["min_capital"] = pd.to_numeric(self.df.get("min_capital", 0.0), errors="coerce").fillna(0.0)
        self.df["core_skills"] = self.df.get("core_skills", "").fillna("").astype(str)

        refit = True
        if os.path.exists(self.tfidf_path):
            try:
                vec = joblib.load(self.tfidf_path)
                vocab = getattr(vec, "vocabulary_", {})
                if vocab and len(vocab) > 20 and not any(" " in term for term in list(vocab.keys())[:30]):
                    self.vectorizer = vec
                    self.skill_matrix = self.vectorizer.transform(self.df["core_skills"])
                    refit = False
            except Exception:
                pass

        if refit:
            self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w-]+\b", stop_words="english")
            self.skill_matrix = self.vectorizer.fit_transform(self.df["core_skills"])
            os.makedirs(os.path.dirname(self.tfidf_path), exist_ok=True)
            joblib.dump(self.vectorizer, self.tfidf_path)

    def parse_skills(self, skills_raw):
        if not skills_raw or pd.isna(skills_raw):
            return []
        tokens = [s.strip().title() for s in re.split(r"[,;\s]+", str(skills_raw)) if len(s.strip()) > 1]
        seen = set()
        deduped = []
        for t in tokens:
            tl = t.lower()
            if tl not in seen:
                seen.add(tl)
                deduped.append(t)
        return deduped

    def recommend(self, user_profile, top_n=5):
        if self.df.empty:
            return []

        user_cap = float(user_profile.get("capital", 0))
        raw_skills = user_profile.get("skills", [])
        if isinstance(raw_skills, str):
            raw_skills = re.split(r"[,;\s]+", raw_skills)
        user_skills_lower = set(s.strip().lower() for s in raw_skills if s.strip())

        user_exp = str(user_profile.get("experience", "Beginner")).strip().lower()
        user_time = str(user_profile.get("available_time", "4-6 hours/day")).strip().lower()
        user_setups = user_profile.get("setup", ["Online / Home-Based"])
        if isinstance(user_setups, str):
            user_setups = [user_setups]
        user_setups_lower = [str(s).strip().lower() for s in user_setups if s]

        # 1. Hard Capital Feasibility Gate
        feasible_mask = self.df["min_capital"] <= user_cap
        feasible_df = self.df[feasible_mask].copy()

        if feasible_df.empty:
            feasible_df = self.df.nsmallest(top_n, "min_capital").copy()

        feasible_submatrix = self.skill_matrix[feasible_df.index]

        # 2. Skill Cosine Similarity
        skill_query = " ".join(user_skills_lower)
        if skill_query.strip() and self.vectorizer is not None:
            user_vec = self.vectorizer.transform([skill_query])
            skill_similarities = cosine_similarity(user_vec, feasible_submatrix).flatten()
        else:
            skill_similarities = np.zeros(len(feasible_df))

        exp_levels = {"beginner": 1, "intermediate": 2, "experienced": 3}
        u_exp_val = exp_levels.get(user_exp, 1)

        results = []
        for idx, (_, row) in enumerate(feasible_df.iterrows()):
            s_score = float(skill_similarities[idx])
            c_score = 1.0 if user_cap >= row["min_capital"] else max(0.2, user_cap / max(row["min_capital"], 1.0))
            b_exp_val = exp_levels.get(str(row.get("experience_level", "Beginner")).strip().lower(), 1)
            e_score = 1.0 if u_exp_val >= b_exp_val else 0.5
            b_setup = str(row.get("business_setup", "")).strip().lower()
            set_score = 1.0 if any(u in b_setup for u in user_setups_lower) else 0.4
            t_score = 1.0 if any(k in user_time for k in ["full", "6+", "4-6"]) else 0.7

            comp = (0.35 * c_score + 0.30 * s_score + 0.15 * e_score + 0.10 * t_score + 0.10 * set_score) * 100

            req_skills = self.parse_skills(row.get("core_skills", ""))
            matched = [s for s in req_skills if s.lower() in user_skills_lower]
            gaps = [s for s in req_skills if s.lower() not in user_skills_lower]

            results.append({
                "id": int(row["id"]),
                "business_type": row["business_type"],
                "category": row.get("category", "General"),
                "startup_cost": row.get("startup_cost", f"₱{row['min_capital']:,.0f}"),
                "min_capital": float(row["min_capital"]),
                "compatibility_score": round(comp, 1),
                "business_setup": row.get("business_setup", "Online / Home-Based"),
                "experience_level": row.get("experience_level", "Beginner"),
                "people_needed": row.get("people_needed", "1 person"),
                "minimum_requirements": row.get("minimum_requirements", ""),
                "strategies": row.get("strategies", ""),
                "risks": row.get("risks", ""),
                "matched_skills": matched,
                "skill_gaps": gaps
            })

        results.sort(key=lambda x: x["compatibility_score"], reverse=True)
        return results[:top_n]
'''

# ----------------------------------------------------------------------
# 8. ml/train_success_model.py (Logistic Regression pipeline)
# ----------------------------------------------------------------------
UPDATES["ml/train_success_model.py"] = r'''import os
import sys
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

def train_success_classifier(data_path=None, model_dir=None):
    data_path = data_path or os.path.join(Config.PROCESSED_PATH, "dataset_1_cleaned.csv")
    model_dir = model_dir or Config.ML_MODELS_PATH

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

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    metrics = {
        "Logistic Regression": {
            "accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "precision": round(float(precision_score(y_test, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, preds, zero_division=0)), 4),
        }
    }

    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(model, os.path.join(model_dir, "success_model.pkl"))
    joblib.dump(metrics, os.path.join(model_dir, "success_metrics.pkl"))
    joblib.dump(list(X.columns), os.path.join(model_dir, "success_model_features.pkl"))

    return metrics

if __name__ == "__main__":
    res = train_success_classifier()
    print("✓ Model Training Complete! Performance Results:")
    print(res)
'''

# ----------------------------------------------------------------------
# 9. ml/evaluate_models.py (5-fold Stratified CV)
# ----------------------------------------------------------------------
UPDATES["ml/evaluate_models.py"] = r'''import os
import sys
import joblib
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

def get_current_metrics():
    path = os.path.join(Config.ML_MODELS_PATH, "success_metrics.pkl")
    return joblib.load(path) if os.path.exists(path) else {}

def run_model_comparison(data_path=None):
    data_path = data_path or os.path.join(Config.PROCESSED_PATH, "dataset_1_cleaned.csv")
    if not os.path.exists(data_path):
        print(f"Dataset not found at {data_path}")
        return None

    df = pd.read_csv(data_path)
    target = next((c for c in df.columns if "success" in c), None)
    if not target:
        print("Target column missing.")
        return None

    X = pd.get_dummies(df.drop(columns=[target]), drop_first=True)
    y = df[target]

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    candidate_models = {
        "RandomForest (baseline)": RandomForestClassifier(n_estimators=100, random_state=42),
        "LogReg (unscaled)": LogisticRegression(max_iter=1000, random_state=42),
        "LogReg (scaled + balanced)": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
        )
    }

    scoring = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    comparison_table = []

    for name, model in candidate_models.items():
        scores = cross_validate(model, X, y, cv=skf, scoring=scoring)
        comparison_table.append({
            "model": name,
            "acc": round(float(scores["test_accuracy"].mean()), 3),
            "prec": round(float(scores["test_precision"].mean()), 3),
            "recall": round(float(scores["test_recall"].mean()), 3),
            "F1": round(float(scores["test_f1"].mean()), 3),
            "AUC": round(float(scores["test_roc_auc"].mean()), 3),
            "F1 std": f"±{round(float(scores['test_f1'].std()), 3)}"
        })

    report_df = pd.DataFrame(comparison_table)
    print("\n" + "=" * 75)
    print("5-FOLD STRATIFIED CROSS-VALIDATION MODEL COMPARISON (N=250)")
    print("=" * 75)
    print(report_df.to_string(index=False))
    print("=" * 75)
    return report_df

if __name__ == "__main__":
    run_model_comparison()
'''

# ----------------------------------------------------------------------
# 10. static/css/main.css (Philippine Mercantile Design System)
# ----------------------------------------------------------------------
UPDATES["static/css/main.css"] = r'''@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Space+Grotesk:wght@500;600;700&family=Space+Mono:wght@400;700&display=swap');

:root {
  --color-canvas: #f6f4ee;
  --color-surface: #ffffff;
  --color-surface-soft: #edeae0;
  --color-ink: #1c1f1d;
  --color-ink-muted: #5c635d;
  --color-border: #dcd7c9;
  --color-brand: #0f4c3a;
  --color-brand-hover: #0a3528;
  --color-accent: #c85a17;
  --color-badge-bg: #e6ede8;
  --color-badge-text: #0f4c3a;

  --font-display: 'Space Grotesk', -apple-system, sans-serif;
  --font-body: 'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-mono: 'Space Mono', monospace;

  --shadow-flat: 3px 3px 0px var(--color-ink);
  --shadow-flat-sm: 2px 2px 0px var(--color-ink);
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-body);
  background-color: var(--color-canvas);
  color: var(--color-ink);
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {
  outline: 2px solid var(--color-brand);
  outline-offset: 3px;
}

.header {
  background: var(--color-surface);
  border-bottom: 2px solid var(--color-ink);
  padding: 16px 24px;
}

.nav-container {
  max-width: 1040px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 700;
  color: var(--color-ink);
  text-decoration: none;
  letter-spacing: -0.5px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-dot {
  width: 8px;
  height: 8px;
  background: var(--color-accent);
  display: inline-block;
}

nav {
  display: flex;
  align-items: center;
  gap: 20px;
}

nav a {
  text-decoration: none;
  color: var(--color-ink);
  font-size: 14px;
  font-weight: 600;
  transition: color 0.15s ease;
}

nav a:hover {
  color: var(--color-brand);
}

.container {
  max-width: 1040px;
  margin: 40px auto;
  padding: 0 20px;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  padding: 32px;
  margin-bottom: 24px;
}

.card-editorial {
  border: 1.5px solid var(--color-ink);
  box-shadow: var(--shadow-flat);
  background: var(--color-surface);
}

h1, h2, h3, h4 {
  font-family: var(--font-display);
  color: var(--color-ink);
  font-weight: 700;
  line-height: 1.2;
}

h1 { font-size: clamp(32px, 5vw, 44px); letter-spacing: -1px; }
h2 { font-size: 26px; letter-spacing: -0.5px; margin-bottom: 12px; }
h3 { font-size: 20px; letter-spacing: -0.3px; }

.subtitle {
  color: var(--color-ink-muted);
  font-size: 15px;
  margin-bottom: 24px;
}

.mono-tag {
  font-family: var(--font-mono);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-brand);
  display: inline-block;
  margin-bottom: 8px;
  font-weight: 700;
}

.btn {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  padding: 12px 24px;
  border-radius: 0;
  border: 1.5px solid var(--color-ink);
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}

.btn-primary {
  background-color: var(--color-brand);
  color: var(--color-surface);
  border-color: var(--color-ink);
  box-shadow: var(--shadow-flat-sm);
}

.btn-primary:hover {
  background-color: var(--color-brand-hover);
  transform: translate(-1px, -1px);
  box-shadow: var(--shadow-flat);
}

.btn-secondary {
  background: var(--color-surface);
  color: var(--color-ink);
  box-shadow: var(--shadow-flat-sm);
}

.btn-secondary:hover {
  background: var(--color-surface-soft);
  transform: translate(-1px, -1px);
  box-shadow: var(--shadow-flat);
}

.btn-block { width: 100%; }
.btn-sm { padding: 6px 14px; font-size: 12px; }

.form-group {
  margin-bottom: 22px;
}

.form-group label {
  display: block;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-control {
  width: 100%;
  padding: 12px 14px;
  font-family: var(--font-body);
  font-size: 14px;
  border: 1.5px solid var(--color-ink);
  background: var(--color-surface);
  color: var(--color-ink);
  border-radius: 0;
}

.form-control:focus {
  outline: 2px solid var(--color-brand);
}

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 6px;
  max-height: 250px;
  overflow-y: auto;
  padding: 12px;
  background: var(--color-surface-soft);
  border: 1.5px solid var(--color-ink);
}

.skill-pill {
  font-size: 12px;
  background: var(--color-surface);
  padding: 8px 10px;
  cursor: pointer;
  border: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 6px;
  user-select: none;
}

.skill-pill input[type="checkbox"] {
  accent-color: var(--color-brand);
}

.business-card {
  background: var(--color-surface);
  border: 1.5px solid var(--color-ink);
  box-shadow: var(--shadow-flat);
  margin-bottom: 20px;
  padding: 24px;
  display: grid;
  grid-template-columns: 140px 1fr 180px;
  gap: 20px;
  align-items: center;
}

.biz-cost-col {
  border-right: 1px dashed var(--color-border);
  padding-right: 16px;
  text-align: left;
}

.biz-cost-label {
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.biz-cost-val {
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-ink);
}

.biz-main-col h3 {
  font-size: 20px;
  margin-bottom: 4px;
}

.biz-meta {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin-bottom: 8px;
}

.skills-match {
  font-size: 12.5px;
  color: var(--color-brand);
  font-weight: 600;
}

.skills-gap-preview {
  font-size: 12px;
  color: var(--color-accent);
}

.biz-score-col {
  text-align: right;
  border-left: 1px dashed var(--color-border);
  padding-left: 16px;
}

.score-num {
  font-family: var(--font-mono);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-brand);
  line-height: 1;
  margin-bottom: 6px;
}

.score-lbl {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  font-family: var(--font-mono);
  margin-bottom: 12px;
}

.phase-card {
  border: 1.5px solid var(--color-ink);
  border-left: 6px solid var(--color-brand);
  background: var(--color-surface);
  padding: 20px 24px;
  margin-bottom: 16px;
}

.phase-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--color-brand);
  margin-bottom: 4px;
}

.badge {
  font-family: var(--font-mono);
  background: var(--color-badge-bg);
  color: var(--color-badge-text);
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  border: 1px solid var(--color-brand);
}

.alert {
  padding: 14px 18px;
  border: 1.5px solid var(--color-ink);
  margin-bottom: 24px;
  font-size: 14px;
  font-weight: 500;
}

.alert-info { background: var(--color-surface-soft); border-left: 6px solid var(--color-ink); }
.alert-danger { background: #fbeae8; border-left: 6px solid var(--color-accent); color: #851e06; }
.alert-success { background: #eaf3ed; border-left: 6px solid var(--color-brand); color: #0f4c3a; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }

@media (max-width: 820px) {
  .business-card {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .biz-cost-col, .biz-score-col {
    border: none;
    padding: 0;
    text-align: left;
  }
  .biz-score-col {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .grid-2, .grid-3, .grid-4 {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
'''

# ----------------------------------------------------------------------
# 11. templates/base.html
# ----------------------------------------------------------------------
UPDATES["templates/base.html"] = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}SmallBiz Match{% endblock %}</title>
  <link rel="stylesheet" href="/static/css/main.css">
</head>
<body>
  <header class="header">
    <div class="nav-container">
      <a href="/" class="brand">
        <span class="brand-dot"></span>
        SMALLBIZ MATCH
      </a>
      <nav>
        <a href="/find">Find Ideas</a>
        {% if current_user.is_authenticated %}
          <a href="/dashboard">Dashboard</a>
          <a href="/profile">Profile</a>
          <a href="/history">History</a>
          {% if current_user.role == 'admin' %}
            <a href="/admin/metrics">ML Admin</a>
          {% endif %}
          <a href="/logout">Logout</a>
        {% else %}
          <a href="/login">Login</a>
          <a href="/register" class="btn btn-sm btn-primary">Register</a>
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
'''

# ----------------------------------------------------------------------
# 12. templates/main/landing.html (Philippine Value Proposition)
# ----------------------------------------------------------------------
UPDATES["templates/main/landing.html"] = r'''{% extends "base.html" %}
{% block title %}SmallBiz Match — Philippine Enterprise Matching{% endblock %}

{% block content %}
<div class="card card-editorial" style="margin-bottom: 32px; padding: 48px 36px; background: var(--color-surface);">
  <span class="mono-tag">EST. 2026 // LOCAL PHILIPPINE ENTERPRISE ADVISOR</span>
  <h1 style="margin: 12px 0 16px 0;">Turn ₱5,000 into a Real Operating Small Business.</h1>
  <p class="subtitle" style="font-size: 17px; max-width: 720px; line-height: 1.6; margin-bottom: 32px;">
    Stop guessing what business fits your budget. We match your exact starting capital, existing skills, and available hours against a verified catalog of 119 Philippine business models — then generate an actionable 5-phase startup roadmap.
  </p>

  <div style="display: flex; gap: 16px; flex-wrap: wrap;">
    <a href="/register" class="btn btn-primary" style="padding: 14px 28px; font-size: 15px;">
      CREATE FREE ACCOUNT & GET MATCHED
    </a>
    <a href="/login" class="btn btn-secondary" style="padding: 14px 24px;">
      EXISTING FOUNDER LOGIN
    </a>
  </div>
</div>

<div class="grid-4" style="margin-bottom: 40px;">
  <div class="card card-editorial" style="padding: 20px;">
    <span class="mono-tag">01 / GATING</span>
    <h3 style="font-size: 16px; margin: 8px 0 6px 0;">Hard Capital Gate</h3>
    <p style="font-size: 13px; color: var(--color-ink-muted);">
      We strictly eliminate any business requiring more capital than you have. Zero false hopes.
    </p>
  </div>

  <div class="card card-editorial" style="padding: 20px;">
    <span class="mono-tag">02 / SKILLS</span>
    <h3 style="font-size: 16px; margin: 8px 0 6px 0;">Skill Embeddings</h3>
    <p style="font-size: 13px; color: var(--color-ink-muted);">
      TF-IDF vector matching measures the cosine angle between your strengths and catalog requirements.
    </p>
  </div>

  <div class="card card-editorial" style="padding: 20px;">
    <span class="mono-tag">03 / ROADMAP</span>
    <h3 style="font-size: 16px; margin: 8px 0 6px 0;">5-Phase Pathways</h3>
    <p style="font-size: 13px; color: var(--color-ink-muted);">
      Concrete step-by-step milestones from tool acquisition and licensing to pre-orders and scaling.
    </p>
  </div>

  <div class="card card-editorial" style="padding: 20px;">
    <span class="mono-tag">04 / STRATEGY</span>
    <h3 style="font-size: 16px; margin: 8px 0 6px 0;">Catalog-Backed Risks</h3>
    <p style="font-size: 13px; color: var(--color-ink-muted);">
      Review documented survival strategies and operational risks specific to each model.
    </p>
  </div>
</div>
{% endblock %}
'''

# ----------------------------------------------------------------------
# 13. templates/user/recommendations_form.html
# ----------------------------------------------------------------------
UPDATES["templates/user/recommendations_form.html"] = r'''{% extends "base.html" %}
{% block title %}Find Business Ideas — SmallBiz Match{% endblock %}

{% block content %}
<div class="card card-editorial">
  <span class="mono-tag">FEASIBILITY ENGINE // REAL CATALOG ATTRIBUTES</span>
  <h2 style="margin: 8px 0 12px 0;">Find Your Business Match</h2>
  <p class="subtitle">Enter your real parameters to filter candidate businesses and calculate compatibility.</p>

  <form action="/find" method="POST">
    <div class="form-group">
      <label>Starting Capital (₱ PHP)</label>
      <input type="number" name="capital" value="10000" min="0" step="500" required class="form-control">
    </div>

    <div class="form-group">
      <label>Select Your Existing Skills</label>
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
      <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-top: 8px;">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="setup" value="Online" checked> Online
        </label>
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="setup" value="Home-Based" checked> Home-Based
        </label>
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="setup" value="Physical Store"> Physical Store
        </label>
      </div>
    </div>

    <button type="submit" class="btn btn-primary btn-block" style="padding: 14px; margin-top: 10px;">
      DISCOVER COMPATIBLE BUSINESSES
    </button>
  </form>
</div>
{% endblock %}
'''

# ----------------------------------------------------------------------
# 14. templates/user/recommendations.html (Asymmetric cards & feedback)
# ----------------------------------------------------------------------
UPDATES["templates/user/recommendations.html"] = r'''{% extends "base.html" %}
{% block title %}Matched Recommendations — SmallBiz Match{% endblock %}

{% block content %}
<div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 24px;">
  <div>
    <span class="mono-tag">FEASIBILITY MATCHES // ₱{{ "{:,.2f}".format(profile.capital) }} CAPITAL</span>
    <h2>Recommended Business Opportunities</h2>
    <p class="subtitle" style="margin-bottom: 0;">
      Filtered strictly within your available budget and ranked by skill vector similarity.
    </p>
  </div>
  <a href="/find" class="btn btn-secondary btn-sm">Adjust Filters</a>
</div>

{% for r in recs %}
  <div class="business-card">
    <div class="biz-cost-col">
      <div class="biz-cost-label">Required Capital</div>
      <div class="biz-cost-val">₱{{ "{:,.0f}".format(r.min_capital) }}</div>
      <div style="font-size: 11px; color: var(--color-ink-muted); margin-top: 4px;">{{ r.startup_cost }}</div>
    </div>

    <div class="biz-main-col">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
        <h3>{{ r.business_type }}</h3>
        <span class="badge">{{ r.category }}</span>
      </div>
      <div class="biz-meta">
        Setup: <strong>{{ r.business_setup }}</strong> · Minimum Staff: <strong>{{ r.people_needed }}</strong>
      </div>
      {% if r.matched_skills %}
        <div class="skills-match">✓ Matching Skills: {{ r.matched_skills | join(', ') }}</div>
      {% endif %}
      {% if r.skill_gaps %}
        <div class="skills-gap-preview">⚠ Skills to Acquire: {{ r.skill_gaps[:3] | join(', ') }}{% if r.skill_gaps | length > 3 %} +{{ r.skill_gaps | length - 3 }} more{% endif %}</div>
      {% endif %}
    </div>

    <div class="biz-score-col">
      <div>
        <div class="score-num">{{ r.compatibility_score }}%</div>
        <div class="score-lbl">Compatibility</div>
      </div>
      <a href="/pathway/{{ r.business_type }}" class="btn btn-primary btn-sm btn-block">View Pathway</a>
    </div>
  </div>
{% else %}
  <div class="card card-editorial">
    <h3>No Compatible Businesses Found</h3>
    <p style="margin-top: 8px;">Try increasing your capital limit or selecting broader skill categories.</p>
    <a href="/find" class="btn btn-primary" style="margin-top: 16px;">Refine Input</a>
  </div>
{% endfor %}

<div class="card card-editorial" id="feedback-card" style="text-align: center; margin-top: 40px; background: var(--color-surface-soft);">
  <h4 style="margin-bottom: 6px;">Evaluate Recommendation Realism</h4>
  <p style="font-size: 14px; color: var(--color-ink-muted); margin-bottom: 16px;">
    Are these business ideas feasible with your starting funds and aligned with your skills?
  </p>
  <div style="display: flex; justify-content: center; gap: 14px;">
    <button onclick="sendFeedback('yes')" class="btn btn-primary btn-sm">👍 Yes, Realistic Match</button>
    <button onclick="sendFeedback('no')" class="btn btn-secondary btn-sm">👎 Not a Good Fit</button>
  </div>
</div>

<script>
function sendFeedback(choice) {
  const formData = new FormData();
  formData.append('rating', choice);
  fetch('/feedback', { method: 'POST', body: formData })
    .then(res => res.text())
    .then(html => { document.getElementById('feedback-card').innerHTML = html; });
}
</script>
{% endblock %}
'''

# ----------------------------------------------------------------------
# 15. templates/user/pathway.html
# ----------------------------------------------------------------------
UPDATES["templates/user/pathway.html"] = r'''{% extends "base.html" %}
{% block title %}
  {% if roadmap and roadmap.business_type %}
    Business Pathway: {{ roadmap.business_type }}
  {% else %}
    Business Pathway Unavailable
  {% endif %}
{% endblock %}

{% block content %}
{% if error or not roadmap %}
  <div class="card card-editorial" style="border-left: 6px solid var(--color-accent);">
    <h2>Pathway Unavailable</h2>
    <p>{{ error or "The requested business could not be found in the active catalog." }}</p>
    <a href="/find" class="btn btn-primary" style="margin-top: 12px;">Back to Recommender</a>
  </div>
{% else %}
  <div class="card card-editorial" style="margin-bottom: 24px;">
    <span class="mono-tag">STARTUP ROADMAP // {{ roadmap.business_type }}</span>
    <h2>{{ roadmap.business_type }}</h2>
    <div class="grid-2" style="margin-top: 16px;">
      <div style="background: #eaf3ed; border: 1.5px solid var(--color-brand); padding: 16px;">
        <strong style="color: var(--color-brand);">✓ Your Matching Skills:</strong>
        <p style="margin-top: 4px; font-size: 13.5px;">{{ roadmap.matched_skills | join(', ') or 'None currently' }}</p>
      </div>
      <div style="background: #fbeae8; border: 1.5px solid var(--color-accent); padding: 16px;">
        <strong style="color: var(--color-accent);">⚠ Skills to Acquire:</strong>
        <p style="margin-top: 4px; font-size: 13.5px;">{{ roadmap.skill_gaps | join(', ') or 'All core skills present!' }}</p>
      </div>
    </div>
  </div>

  <h3>Step-by-Step Implementation Pathway</h3>
  <div style="margin-top: 16px;">
    {% for s in roadmap.steps %}
      <div class="phase-card">
        <div class="phase-title">{{ s.phase }}</div>
        <h4 style="margin: 4px 0 6px 0;">{{ s.title }}</h4>
        <p style="font-size: 13.5px; color: var(--color-ink-muted);">{{ s.description }}</p>
      </div>
    {% endfor %}
  </div>
  <div style="margin-top: 24px;">
    <a href="/find" class="btn btn-secondary">← Back to Recommendations</a>
  </div>
{% endif %}
{% endblock %}
'''

# ----------------------------------------------------------------------
# 16. templates/auth/login.html & register.html
# ----------------------------------------------------------------------
UPDATES["templates/auth/login.html"] = r'''{% extends "base.html" %}
{% block title %}Sign In — SmallBiz Match{% endblock %}

{% block content %}
<div class="card card-editorial" style="max-width: 440px; margin: 40px auto;">
  <span class="mono-tag">AUTHENTICATION // FOUNDER ACCESS</span>
  <h2 style="margin: 8px 0 16px 0;">Sign In</h2>
  <form method="POST" action="/login{% if next %}?next={{ next }}{% endif %}">
    <div class="form-group">
      <label>Email Address</label>
      <input type="email" name="email" required class="form-control" placeholder="juan@example.ph">
    </div>
    <div class="form-group">
      <label>Password</label>
      <input type="password" name="password" required class="form-control">
    </div>
    <button type="submit" class="btn btn-primary btn-block" style="padding: 12px;">Sign In</button>
  </form>
  <p style="font-size: 13px; color: var(--color-ink-muted); margin-top: 16px; text-align: center;">
    Don't have an account? <a href="/register{% if next %}?next={{ next }}{% endif %}" style="color: var(--color-brand); font-weight: 700;">Create one here</a>.
  </p>
</div>
{% endblock %}
'''

UPDATES["templates/auth/register.html"] = r'''{% extends "base.html" %}
{% block title %}Create Account — SmallBiz Match{% endblock %}

{% block content %}
<div class="card card-editorial" style="max-width: 460px; margin: 40px auto;">
  <span class="mono-tag">REGISTRATION // FREE FOUNDER ACCOUNT</span>
  <h2 style="margin: 8px 0 16px 0;">Create Account</h2>
  <form method="POST" action="/register{% if next %}?next={{ next }}{% endif %}">
    <div class="form-group">
      <label>Full Name / Username</label>
      <input type="text" name="username" value="{{ username or '' }}" required class="form-control" placeholder="Juan dela Cruz">
    </div>
    <div class="form-group">
      <label>Email Address</label>
      <input type="email" name="email" value="{{ email or '' }}" required class="form-control" placeholder="juan@example.ph">
    </div>
    <div class="form-group">
      <label>Password</label>
      <input type="password" name="password" required class="form-control" placeholder="Minimum 6 characters">
    </div>
    <div class="form-group">
      <label>Confirm Password</label>
      <input type="password" name="confirm_password" required class="form-control">
    </div>
    <button type="submit" class="btn btn-primary btn-block" style="padding: 12px;">Create Free Account</button>
  </form>
  <p style="font-size: 13px; color: var(--color-ink-muted); margin-top: 16px; text-align: center;">
    Already have an account? <a href="/login{% if next %}?next={{ next }}{% endif %}" style="color: var(--color-brand); font-weight: 700;">Sign in here</a>.
  </p>
</div>
{% endblock %}
'''

# ----------------------------------------------------------------------
# 17. templates/admin/metrics.html
# ----------------------------------------------------------------------
UPDATES["templates/admin/metrics.html"] = r'''{% extends "base.html" %}
{% block title %}ML Performance Dashboard — SmallBiz Match{% endblock %}

{% block content %}
<h2>Machine Learning Performance Dashboard</h2>
<p class="subtitle">Operational metrics for recommender feedback and founder success prediction.</p>

<div class="card card-editorial" style="background: #eaf3ed; border-left: 6px solid var(--color-brand); margin-bottom: 24px;">
  <h3 style="margin-top: 0; color: var(--color-brand);">Live Recommender Accuracy (User Survey Feedback)</h3>
  <div style="display: flex; gap: 40px; align-items: center; margin-top: 12px;">
    <div>
      <div style="font-family: var(--font-mono); font-size: 40px; font-weight: 700; color: var(--color-brand); line-height: 1;">
        {{ live_accuracy }}%
      </div>
      <div style="font-size: 12px; color: var(--color-ink-muted); text-transform: uppercase; font-family: var(--font-mono); margin-top: 4px;">
        Live Match Accuracy
      </div>
    </div>
    <div>
      <p style="margin: 0; font-size: 14px;"><strong>Total User Ratings:</strong> {{ total_votes }}</p>
      <p style="margin: 0; font-size: 14px;"><strong>Positive Matches:</strong> {{ positive_votes }}</p>
    </div>
  </div>
</div>

<div class="card card-editorial">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
    <div>
      <h3 style="margin: 0;">Founder Success Prediction Model</h3>
      <p style="margin: 4px 0 0 0; color: var(--color-ink-muted); font-size: 13px;">
        Architecture: <strong>StandardScaler + Logistic Regression (class_weight="balanced")</strong>
      </p>
    </div>
    <form action="/admin/retrain" method="POST" style="margin: 0;">
      <button type="submit" class="btn btn-primary btn-sm">Retrain Model</button>
    </form>
  </div>
  <hr style="border: 0; border-top: 1px solid var(--color-border); margin: 16px 0;">

  {% if metrics and "Logistic Regression" in metrics %}
    {% set m = metrics["Logistic Regression"] %}
    <div class="grid-4" style="text-align: center;">
      <div style="background: var(--color-surface-soft); padding: 16px; border: 1.5px solid var(--color-ink);">
        <div style="font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; color: var(--color-ink-muted);">Accuracy</div>
        <div style="font-family: var(--font-mono); font-size: 26px; font-weight: 700; margin-top: 4px;">{{ (m.accuracy * 100) | round(1) }}%</div>
      </div>
      <div style="background: var(--color-surface-soft); padding: 16px; border: 1.5px solid var(--color-ink);">
        <div style="font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; color: var(--color-ink-muted);">Precision</div>
        <div style="font-family: var(--font-mono); font-size: 26px; font-weight: 700; margin-top: 4px;">{{ m.precision }}</div>
      </div>
      <div style="background: var(--color-surface-soft); padding: 16px; border: 1.5px solid var(--color-ink);">
        <div style="font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; color: var(--color-ink-muted);">Recall</div>
        <div style="font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: var(--color-brand); margin-top: 4px;">{{ m.recall }}</div>
      </div>
      <div style="background: var(--color-surface-soft); padding: 16px; border: 1.5px solid var(--color-ink);">
        <div style="font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; color: var(--color-ink-muted);">F1-Score</div>
        <div style="font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: var(--color-brand); margin-top: 4px;">{{ m.f1 }}</div>
      </div>
    </div>
  {% else %}
    <p>No model metrics found. Click <strong>Retrain Model</strong> to fit the classifier on Dataset 1.</p>
  {% endif %}
</div>
{% endblock %}
'''

# ----------------------------------------------------------------------
# 18. Git & Publishing: .gitignore, requirements.txt, .env.example, pytest.ini
# ----------------------------------------------------------------------
UPDATES[".gitignore"] = r'''# Python bytecode
__pycache__/
*.py[cod]
*$py.class
*.so

# Environment & local state
venv/
env/
.env

# SQLite local database
instance/*.db
instance/*.db-journal
instance/*.sqlite

# Pytest & test cache
.pytest_cache/
.coverage
htmlcov/

# OS artifacts
.DS_Store
Thumbs.db
'''

UPDATES["requirements.txt"] = r'''Flask==3.0.3
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
gunicorn==22.0.0
'''

UPDATES[".env.example"] = r'''FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=generate-a-secure-random-32-byte-hex-string
DATABASE_URL=sqlite:///instance/app.db
'''

UPDATES["pytest.ini"] = r'''[pytest]
addopts = -p no:flask
pythonpath = .
'''

# ----------------------------------------------------------------------
# 19. tests/test_gating_and_redesign.py
# ----------------------------------------------------------------------
UPDATES["tests/test_gating_and_redesign.py"] = r'''import pytest
from app import create_app
from models import db
from models.user import User

@pytest.fixture
def app_instance():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        user = User(username="founder_test", email="founder@example.ph")
        user.set_password("securepassword123")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app_instance):
    return app_instance.test_client()

def test_landing_page_renders_cleanly(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"CREATE FREE ACCOUNT" in res.data

def test_find_route_is_login_gated(client):
    res = client.get("/find", follow_redirects=False)
    assert res.status_code == 302
    assert "/login?next=%2Ffind" in res.headers["Location"]

def test_login_redirects_back_to_find(client):
    res = client.post("/login?next=%2Ffind", data={
        "email": "founder@example.ph",
        "password": "securepassword123"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Find Your Business Match" in res.data

def test_pathway_remains_publicly_readable(client):
    res = client.get("/pathway/NonexistentRandom123")
    assert res.status_code == 404
    assert b"Pathway Unavailable" in res.data
'''

# ----------------------------------------------------------------------
# Execute All Writes with Windows root folder protection
# ----------------------------------------------------------------------
count = 0
for rel_path, content in UPDATES.items():
    folder = os.path.dirname(rel_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(rel_path, "w", encoding="utf-8") as f:
        f.write(content)
    count += 1
    print(f"  ✓ Patched ({count}/{len(UPDATES)}): {rel_path}")

print("\n" + "=" * 80)
print(f"🎉 ALL {count} FILES PATCHED SUCCESSFULLY!")
print("=" * 80)