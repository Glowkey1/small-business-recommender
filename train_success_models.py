import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.success_features import APP_FEATURES

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = BASE_DIR / "data" / "processed" / "dataset_1_cleaned.csv"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_OUTPUT_JOBLIB = MODELS_DIR / "success_model.joblib"
METRICS_OUTPUT_JSON = MODELS_DIR / "model_metrics.json"
MODEL_CARD_OUTPUT_JSON = MODELS_DIR / "success_model_card.json"

RANDOM_STATE = 42
TEST_SIZE = 0.20


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (pd.Series, pd.DataFrame)):
        return _json_safe(value.to_dict())
    return value


def _rounded(value, digits=4):
    return round(float(value), digits)


def _load_dataset():
    if not DATASET_PATH.exists():
        logging.error("Success dataset missing at: %s", DATASET_PATH)
        return None

    df = pd.read_csv(DATASET_PATH)
    if df.empty:
        logging.error("Success dataset is empty.")
        return None

    target_col = next((column for column in df.columns if "success" in column), None)
    if not target_col:
        logging.error("Target column 'success' not found.")
        return None

    missing = [column for column in APP_FEATURES if column not in df.columns]
    if missing:
        logging.error("Success dataset is missing app features: %s", missing)
        return None

    selected = df[APP_FEATURES + [target_col]].copy()
    if selected.isnull().any().any():
        logging.error("Success dataset contains null values in the selected features.")
        return None

    y = selected[target_col].astype(int)
    if not set(y.unique()).issubset({0, 1}):
        logging.error("Target column must contain only binary values.")
        return None
    if y.nunique() < 2:
        logging.error("Target column must contain both success and non-success records.")
        return None

    return selected, target_col


def _candidate_models():
    return {
        "logistic_regression": {
            "label": "Logistic Regression",
            "estimator": Pipeline(
                steps=[
                    ("scale", StandardScaler()),
                    (
                        "logreg",
                        LogisticRegression(
                            max_iter=2000,
                            class_weight="balanced",
                            random_state=RANDOM_STATE,
                        ),
                    ),
                ]
            ),
            "param_grid": {"logreg__C": [0.01, 0.1, 1.0, 10.0]},
        },
        "random_forest": {
            "label": "Random Forest",
            "estimator": RandomForestClassifier(
                n_estimators=200,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=1,
            ),
            "param_grid": {
                "max_depth": [3, 5, None],
                "min_samples_leaf": [1, 2, 4],
            },
        },
        "hist_gradient_boosting": {
            "label": "Histogram Gradient Boosting",
            "estimator": HistGradientBoostingClassifier(
                learning_rate=0.05,
                max_iter=200,
                max_depth=3,
                class_weight="balanced",
                early_stopping=False,
                random_state=RANDOM_STATE,
            ),
            "param_grid": {
                "max_depth": [2, 3],
                "learning_rate": [0.05, 0.1],
                "max_iter": [100, 200],
                "min_samples_leaf": [5, 10],
            },
        },
    }


def _summarise_cv(scores):
    summary = {}
    for metric in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "brier"):
        values = scores[f"test_{metric}"]
        if metric == "brier":
            values = -values
        summary[f"{metric}_mean"] = _rounded(np.mean(values))
        summary[f"{metric}_std"] = _rounded(np.std(values))
    return summary


def _nested_cv(candidate, X, y):
    outer_cv = RepeatedStratifiedKFold(
        n_splits=5, n_repeats=2, random_state=RANDOM_STATE
    )
    inner_cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        candidate["estimator"],
        candidate["param_grid"],
        scoring="average_precision",
        cv=inner_cv,
        n_jobs=1,
        refit=True,
        error_score="raise",
    )
    scoring = {
        "accuracy": "accuracy",
        "precision": "precision",
        "recall": "recall",
        "f1": "f1",
        "roc_auc": "roc_auc",
        "pr_auc": "average_precision",
        "brier": "neg_brier_score",
    }
    scores = cross_validate(
        search,
        X,
        y,
        cv=outer_cv,
        scoring=scoring,
        n_jobs=1,
        error_score="raise",
    )
    return _summarise_cv(scores)


def _threshold_metrics(y_true, probabilities, threshold):
    predictions = (probabilities >= threshold).astype(int)
    return {
        "threshold": _rounded(threshold),
        "accuracy": _rounded(accuracy_score(y_true, predictions)),
        "precision": _rounded(precision_score(y_true, predictions, zero_division=0)),
        "recall": _rounded(recall_score(y_true, predictions, zero_division=0)),
        "f1": _rounded(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": _rounded(roc_auc_score(y_true, probabilities)),
        "pr_auc": _rounded(average_precision_score(y_true, probabilities)),
        "brier": _rounded(brier_score_loss(y_true, probabilities)),
        "confusion_matrix": confusion_matrix(y_true, predictions).tolist(),
        "classification_report": classification_report(
            y_true, predictions, output_dict=True, zero_division=0
        ),
    }


def _select_threshold(y_true, probabilities):
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    f1_scores = 2 * precision * recall / (precision + recall + 1e-12)
    finite = np.isfinite(thresholds)
    if not finite.any():
        return 0.5
    best_index = int(np.argmax(f1_scores[:-1][finite]))
    valid_thresholds = thresholds[finite]
    return float(valid_thresholds[best_index])


def _collect_repeated_oof_probabilities(estimator, X, y, n_repeats=10):
    repeat_probabilities = []
    for repeat in range(n_repeats):
        cv = StratifiedKFold(
            n_splits=5, shuffle=True, random_state=RANDOM_STATE + repeat
        )
        probabilities = np.zeros(len(y), dtype=float)
        for train_index, test_index in cv.split(X, y):
            fold_model = clone(estimator)
            fold_model.fit(X.iloc[train_index], y.iloc[train_index])
            probabilities[test_index] = fold_model.predict_proba(
                X.iloc[test_index]
            )[:, 1]
        repeat_probabilities.append(probabilities)
    return np.mean(repeat_probabilities, axis=0), np.asarray(repeat_probabilities)


def _summarise_repeated_thresholds(y_true, repeated_probabilities, threshold):
    keys = ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "brier")
    per_repeat = {key: [] for key in keys}
    for probabilities in repeated_probabilities:
        metrics = _threshold_metrics(y_true, probabilities, threshold)
        for key in keys:
            per_repeat[key].append(metrics[key])

    summary = {}
    for key in keys:
        summary[f"{key}_mean"] = _rounded(np.mean(per_repeat[key]))
        summary[f"{key}_std"] = _rounded(np.std(per_repeat[key]))
    return summary


def _calibration_summary(y_true, probabilities):
    prob_true, prob_pred = calibration_curve(
        y_true, probabilities, n_bins=5, strategy="quantile"
    )
    return {
        "brier": _rounded(brier_score_loss(y_true, probabilities)),
        "curve": {
            "prob_true": [_rounded(value) for value in prob_true],
            "prob_pred": [_rounded(value) for value in prob_pred],
        },
    }


def train():
    loaded = _load_dataset()
    if loaded is None:
        return None
    df, target_col = loaded

    y = df[target_col].astype(int)
    X = df[APP_FEATURES].astype(float)
    positive_count = int((y == 1).sum())
    negative_count = int((y == 0).sum())
    majority_baseline = _rounded(max(positive_count, negative_count) / len(y))

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    candidates = _candidate_models()
    nested_results = {}
    for name, candidate in candidates.items():
        logging.info("Running nested CV for %s...", candidate["label"])
        nested_results[name] = _nested_cv(candidate, X_train, y_train)

    best_name = max(
        nested_results,
        key=lambda name: (
            nested_results[name]["pr_auc_mean"],
            nested_results[name]["f1_mean"],
        ),
    )
    best_candidate = candidates[best_name]
    logging.info("Selected model: %s", best_candidate["label"])

    inner_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    final_search = GridSearchCV(
        best_candidate["estimator"],
        best_candidate["param_grid"],
        scoring="average_precision",
        cv=inner_cv,
        n_jobs=1,
        refit=True,
        error_score="raise",
    )
    final_search.fit(X_train, y_train)

    calibrated_model = CalibratedClassifierCV(
        estimator=final_search.best_estimator_,
        method="sigmoid",
        cv=5,
    )

    logging.info("Collecting calibrated out-of-fold probabilities...")
    oof_probabilities, repeated_probabilities = _collect_repeated_oof_probabilities(
        calibrated_model, X_train, y_train
    )
    selected_threshold = _select_threshold(y_train, oof_probabilities)

    calibrated_model.fit(X_train, y_train)
    holdout_probabilities = calibrated_model.predict_proba(X_test)[:, 1]

    trained_at = datetime.now(timezone.utc).isoformat()
    dataset_hash = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    model_version = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{dataset_hash[:12]}"

    feature_metadata = {}
    for feature in APP_FEATURES:
        feature_metadata[feature] = {
            "min": _rounded(X[feature].min()),
            "median": _rounded(X[feature].median()),
            "max": _rounded(X[feature].max()),
        }

    cv_summary = {
        "scheme": "RepeatedStratifiedKFold(5 folds x 10 repeats)",
        "threshold_default": _threshold_metrics(y_train, oof_probabilities, 0.5),
        "threshold_selected": _threshold_metrics(
            y_train, oof_probabilities, selected_threshold
        ),
        "calibration": _calibration_summary(y_train, oof_probabilities),
    }
    cv_summary.update(
        _summarise_repeated_thresholds(
            y_train, repeated_probabilities, selected_threshold
        )
    )

    holdout_summary = {
        "size": int(len(y_test)),
        "positive_count": int((y_test == 1).sum()),
        "negative_count": int((y_test == 0).sum()),
        "threshold_default": _threshold_metrics(y_test, holdout_probabilities, 0.5),
        "threshold_selected": _threshold_metrics(
            y_test, holdout_probabilities, selected_threshold
        ),
        "calibration": _calibration_summary(y_test, holdout_probabilities),
    }

    report = {
        "model_name": f"{best_candidate['label']} (calibrated)",
        "model_key": best_name,
        "model_version": model_version,
        "trained_at": trained_at,
        "dataset_size": len(df),
        "successful_records": positive_count,
        "not_successful_records": negative_count,
        "majority_baseline_accuracy": majority_baseline,
        "feature_columns": APP_FEATURES,
        "feature_metadata": feature_metadata,
        "dataset_hash": dataset_hash,
        "random_state": RANDOM_STATE,
        "holdout_fraction": TEST_SIZE,
        "model_selection": {
            "selection_metric": "nested_cv_pr_auc",
            "nested_cv": nested_results,
            "selected_model": best_name,
            "selected_params": _json_safe(final_search.best_params_),
        },
        "cross_validation": cv_summary,
        "holdout": holdout_summary,
        "calibration": {
            "method": "sigmoid",
            "cv_folds": 5,
            "holdout_brier": holdout_summary["calibration"]["brier"],
        },
        "decision_threshold": {
            "selected": _rounded(selected_threshold),
            "default": 0.5,
            "strategy": "max_f1_on_calibrated_oof",
        },
    }

    model_card = {
        "model_name": report["model_name"],
        "model_version": model_version,
        "trained_at": trained_at,
        "dataset": {
            "path": str(DATASET_PATH),
            "records": len(df),
            "successful_records": positive_count,
            "not_successful_records": negative_count,
            "majority_baseline_accuracy": majority_baseline,
            "hash": dataset_hash,
        },
        "features": feature_metadata,
        "intended_use": (
            "Advisory business-success estimate for the recommender UI. "
            "It is not part of ranking while its weight is 0.0."
        ),
        "limitations": [
            "The training dataset is small (250 records) and appears to be UMKM/Indonesian MSME data, not Philippine-specific.",
            "Only features that can be derived from actual app inputs are used; no age, education, gender, or professional-advice fields are fabricated.",
            "Holdout metrics are based on a small test set and have wide uncertainty.",
            "A success probability is not the same as recommendation relevance or recommendation accuracy.",
        ],
        "metrics": {
            "nested_cv": nested_results,
            "cross_validation": cv_summary,
            "holdout": holdout_summary,
            "decision_threshold": report["decision_threshold"],
        },
    }

    artifact = {
        "model": calibrated_model,
        "feature_columns": APP_FEATURES,
        "threshold": float(selected_threshold),
        "model_version": model_version,
        "trained_at": trained_at,
    }

    joblib.dump(artifact, MODEL_OUTPUT_JOBLIB)
    with open(METRICS_OUTPUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(_json_safe(report), handle, indent=2)
    with open(MODEL_CARD_OUTPUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(_json_safe(model_card), handle, indent=2)

    logging.info("Saved production model to: %s", MODEL_OUTPUT_JOBLIB)
    logging.info("Saved metrics to: %s", METRICS_OUTPUT_JSON)
    logging.info("Saved model card to: %s", MODEL_CARD_OUTPUT_JSON)
    logging.info(
        "Selected threshold %.4f; nested CV PR-AUC %.4f; holdout F1 %.4f",
        selected_threshold,
        nested_results[best_name]["pr_auc_mean"],
        holdout_summary["threshold_selected"]["f1"],
    )
    return report


if __name__ == "__main__":
    train()
