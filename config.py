import os
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
