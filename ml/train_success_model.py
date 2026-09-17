import os
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
