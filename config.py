import os
import re
import secrets
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

SQLITE_PATH = (INSTANCE_DIR / "app.db").as_posix()
ENV_DB_URL = os.getenv("DATABASE_URL")

def resolve_db_uri():
    env_url = os.getenv("DATABASE_URL")
    default_uri = f"sqlite:///{SQLITE_PATH}"
    if not env_url or not env_url.strip():
        return default_uri
    env_url = env_url.strip()
    if not env_url.startswith("sqlite:///"):
        return env_url
    path_part = env_url[len("sqlite:///"):]
    if os.path.isabs(path_part) or re.match(r"^[A-Za-z]:[/\\]", path_part):
        return env_url
    abs_path = (BASE_DIR / path_part).as_posix()
    return f"sqlite:///{abs_path}"

# Generate ephemeral secret key if unset in environment (no hardcoded credentials)
_env_secret = os.getenv("SECRET_KEY")
if not _env_secret:
    logging.warning("SECRET_KEY unset in environment. Generating ephemeral 32-byte session secret.")
    _env_secret = secrets.token_hex(32)

def validate_weights(weights: dict):
    total = sum(weights.values())
    if not (0.999 <= total <= 1.001):
        raise ValueError(f"Recommendation weights must sum to 1.0, got {total}")

class Config:
    SECRET_KEY = _env_secret
    SQLALCHEMY_DATABASE_URI = resolve_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    RAW_D1_PATH = DATA_DIR / "raw" / "dataset_1"
    RAW_D2_PATH = DATA_DIR / "raw" / "dataset_2"
    PROCESSED_PATH = DATA_DIR / "processed"
    FINAL_PATH = DATA_DIR / "final"
    MODELS_DIR = BASE_DIR / "models"
    ML_MODELS_PATH = BASE_DIR / "ml" / "models"

    FINAL_BUSINESSES_CSV = FINAL_PATH / "final_business_dataset.csv"
    FINAL_SKILLS_CSV = FINAL_PATH / "final_skill_dataset.csv"
    SKILL_MASTER_CSV = FINAL_PATH / "skill_master.csv"
    MUNICIPALITY_MARKET_CSV = PROCESSED_PATH / "municipality_market_features.csv"
    BUSINESSES_PSA_CSV = PROCESSED_PATH / "businesses_with_psa_population.csv"
    DATASET_1_CLEANED_CSV = PROCESSED_PATH / "dataset_1_cleaned.csv"
    CATEGORY_MAP_CSV = FINAL_PATH / "business_market_category_map.csv"
    PSGC_NAMES_CSV = PROCESSED_PATH / "psgc_region_province_names.csv"

    SUCCESS_MODEL_JOBLIB = MODELS_DIR / "success_model.joblib"
    SUCCESS_METRICS_JSON = MODELS_DIR / "model_metrics.json"

    MAX_CAPITAL = 100_000_000.0
    ALLOWED_EXPERIENCE = ["Beginner", "Intermediate", "Experienced"]
    ALLOWED_TIMES = [
        "1-2 hours/day", "3-4 hours/day", "5-6 hours/day", "7-8 hours/day", "Full-time"
    ]
    ALLOWED_SETUPS = ["Online", "Home-Based", "Physical Store", "Service / Mobile"]

    LOCATION_SCORES = {
        "zero": 0.60,
        "low": 0.75,
        "mid": 0.90,
        "high": 0.85,
        "very_high": 0.75,
        "missing_pop_high": 0.85,
        "missing_pop_low": 0.75
    }

    RECOMMENDATION_WEIGHTS = {
        "capital": 0.30,
        "skills": 0.25,
        "experience": 0.10,
        "setup": 0.10,
        "time": 0.05,
        "location": 0.10,
        "success": 0.10
    }
