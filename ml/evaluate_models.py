import os
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
