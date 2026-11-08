import os
import sys

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config


def train_recommender():
    """Rebuild the TF-IDF vectorizer artifact from the current catalog.

    The pickle is tied to the scikit-learn version that created it, so rerun
    this script after upgrading scikit-learn or regenerating the catalog.
    """
    if not Config.FINAL_BUSINESSES_CSV.exists():
        raise FileNotFoundError(f"Business catalog not found: {Config.FINAL_BUSINESSES_CSV}")

    df_businesses = pd.read_csv(Config.FINAL_BUSINESSES_CSV)
    if "core_skills" not in df_businesses.columns:
        raise ValueError("Business catalog is missing the 'core_skills' column.")

    corpus = df_businesses["core_skills"].dropna().astype(str)
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w-]+\b", stop_words="english")
    vectorizer.fit(corpus)

    Config.ML_MODELS_PATH.mkdir(parents=True, exist_ok=True)
    output_path = Config.ML_MODELS_PATH / "tfidf_vectorizer.pkl"
    joblib.dump(vectorizer, output_path)
    print(f"Saved TF-IDF vectorizer with {len(vectorizer.vocabulary_)} terms to {output_path}")
    return vectorizer


if __name__ == "__main__":
    train_recommender()
