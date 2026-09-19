import os
import json
import logging
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = BASE_DIR / "data" / "processed" / "dataset_1_cleaned.csv"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_OUTPUT_JOBLIB = MODELS_DIR / "success_model.joblib"
METRICS_OUTPUT_JSON = MODELS_DIR / "model_metrics.json"

def train():
    if not DATASET_PATH.exists():
        logging.error(f"Success dataset missing at: {DATASET_PATH}")
        return

    df = pd.read_csv(DATASET_PATH)
    logging.info(f"Loaded dataset: {len(df)} records.")

    target_col = next((c for c in df.columns if "success" in c), None)
    if not target_col:
        logging.error("Target column 'success' not found.")
        return

    y = df[target_col].astype(int)
    X = pd.get_dummies(df.drop(columns=[target_col]), drop_first=True)

    pos_count = int((y == 1).sum())
    neg_count = int((y == 0).sum())
    majority_baseline = round(max(pos_count, neg_count) / len(y), 4)

    logging.info(f"Target Distribution: {pos_count} Successful (1), {neg_count} Not Successful (0).")
    logging.info(f"Majority Class Baseline Accuracy: {majority_baseline * 100:.2f}%")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scoring = ["accuracy", "precision", "recall", "f1"]

    # 1. Logistic Regression Pipeline (StandardScaler + balanced weights)
    logreg_pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    )
    cv_logreg = cross_validate(logreg_pipe, X, y, cv=skf, scoring=scoring)

    # 2. Random Forest (Comparison)
    rf_clf = RandomForestClassifier(n_estimators=100, random_state=42)
    cv_rf = cross_validate(rf_clf, X, y, cv=skf, scoring=scoring)

    # Train production model on 80% train set
    logreg_pipe.fit(X_train, y_train)
    preds = logreg_pipe.predict(X_test)

    cm = confusion_matrix(y_test, preds).tolist()

    report = {
        "model_name": "Logistic Regression",
        "dataset_size": len(df),
        "successful_records": pos_count,
        "not_successful_records": neg_count,
        "majority_baseline_accuracy": majority_baseline,
        "test_metrics": {
            "accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "precision": round(float(precision_score(y_test, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, preds, zero_division=0)), 4),
            "confusion_matrix": cm
        },
        "five_fold_cross_validation": {
            "accuracy_mean": round(float(cv_logreg["test_accuracy"].mean()), 4),
            "accuracy_std": round(float(cv_logreg["test_accuracy"].std()), 4),
            "precision_mean": round(float(cv_logreg["test_precision"].mean()), 4),
            "precision_std": round(float(cv_logreg["test_precision"].std()), 4),
            "recall_mean": round(float(cv_logreg["test_recall"].mean()), 4),
            "recall_std": round(float(cv_logreg["test_recall"].std()), 4),
            "f1_mean": round(float(cv_logreg["test_f1"].mean()), 4),
            "f1_std": round(float(cv_logreg["test_f1"].std()), 4)
        },
        "random_forest_comparison": {
            "accuracy_mean": round(float(cv_rf["test_accuracy"].mean()), 4),
            "f1_mean": round(float(cv_rf["test_f1"].mean()), 4)
        }
    }

    # Save trained model and metrics
    joblib.dump(logreg_pipe, MODEL_OUTPUT_JOBLIB)
    with open(METRICS_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logging.info(f"✓ Saved production model to: {MODEL_OUTPUT_JOBLIB}")
    logging.info(f"✓ Saved metrics JSON to: {METRICS_OUTPUT_JSON}")
    print("\n" + "=" * 60)
    print("SUCCESS MODEL PERFORMANCE (5-Fold Stratified CV)")
    print("=" * 60)
    print(f"Accuracy:  {report['five_fold_cross_validation']['accuracy_mean']*100:.2f}% ± {report['five_fold_cross_validation']['accuracy_std']*100:.2f}%")
    print(f"Precision: {report['five_fold_cross_validation']['precision_mean']*100:.2f}% ± {report['five_fold_cross_validation']['precision_std']*100:.2f}%")
    print(f"Recall:    {report['five_fold_cross_validation']['recall_mean']*100:.2f}% ± {report['five_fold_cross_validation']['recall_std']*100:.2f}%")
    print(f"F1 Score:  {report['five_fold_cross_validation']['f1_mean']*100:.2f}% ± {report['five_fold_cross_validation']['f1_std']*100:.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    train()
