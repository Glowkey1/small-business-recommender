import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer

class SkillEncoder:
    def __init__(self, model_path=None):
        if model_path is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            model_path = os.path.join(base_dir, "ml", "models", "tfidf_vectorizer.pkl")
        self.model_path = model_path
        self.vectorizer = None

    def fit_and_save(self, corpus):
        self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w-]+\b", stop_words="english")
        self.vectorizer.fit(corpus)
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.vectorizer, self.model_path)
        return self.vectorizer

    def load(self):
        if os.path.exists(self.model_path):
            vec = joblib.load(self.model_path)
            vocab = getattr(vec, "vocabulary_", {})
            if any(" " in term for term in list(vocab.keys())[:30]):
                return None
            self.vectorizer = vec
            return self.vectorizer
        return None
