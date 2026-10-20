import json

import joblib
import pytest

from config import Config
from ml.success_features import (
    APP_FEATURES,
    EXPERIENCE_YEARS,
    FEATURE_BOUNDS,
    map_success_features,
)
from ml.success_model_service import SuccessModelService


def test_app_feature_contract_excludes_uncollected_personal_fields():
    assert APP_FEATURES == [
        "initial_capital",
        "financial_record_keeping",
        "internet_usage",
        "marketing_effort",
        "partnership",
        "industry_experience",
    ]
    forbidden = {
        "age",
        "education",
        "owner_gender",
        "parent_business_experience",
        "professional_advice",
        "business_plan",
    }
    assert forbidden.isdisjoint(APP_FEATURES)


def test_map_success_features_uses_actual_app_inputs():
    profile = {
        "capital": 50000,
        "skills": ["Marketing", "Basic Bookkeeping"],
        "experience": "Intermediate",
        "setup": ["Online"],
    }
    business = {
        "min_capital": 10000,
        "core_skills": "Marketing, Sales",
        "people_needed": "Solo",
    }

    row = map_success_features(profile, business)

    assert set(row) == set(APP_FEATURES)
    assert row["initial_capital"] == 1.0
    assert row["financial_record_keeping"] == 1.0
    assert row["internet_usage"] == 1.0
    assert row["marketing_effort"] == 4.0
    assert row["partnership"] == 0.0
    assert row["industry_experience"] == EXPERIENCE_YEARS["intermediate"]


def test_map_success_features_does_not_use_business_setup_as_user_online_access():
    profile = {
        "capital": 1000,
        "skills": [],
        "experience": "Beginner",
        "setup": ["Home-Based"],
    }
    business = {
        "min_capital": 5000,
        "core_skills": "Cooking",
        "people_needed": "1 person",
        "business_setup": "Online",
    }

    row = map_success_features(profile, business)

    assert row["internet_usage"] == 0.0
    assert row["initial_capital"] == 0.0
    assert row["partnership"] == 1.0


def test_map_success_features_is_bounded_for_missing_inputs():
    row = map_success_features({}, {})

    assert set(row) == set(APP_FEATURES)
    for feature, (low, high) in FEATURE_BOUNDS.items():
        assert low <= row[feature] <= high
    assert row["industry_experience"] == 0.0
    assert row["marketing_effort"] == 2.0


def test_service_without_artifacts_returns_none(tmp_path):
    service = SuccessModelService(
        tmp_path / "missing_model.joblib",
        tmp_path / "missing_metrics.json",
    )

    assert service.is_available is False
    assert service.predict_success_scores({}, [{}]) == [None]


def test_service_rejects_old_or_mismatched_feature_schema(tmp_path):
    artifact = {
        "model": object(),
        "feature_columns": ["age", "education", "initial_capital"],
        "threshold": 0.5,
    }
    model_path = tmp_path / "model.joblib"
    joblib.dump(artifact, model_path)

    service = SuccessModelService(model_path, tmp_path / "metrics.json")

    assert service.is_available is False
    assert service.predict_success_scores({}, [{}]) == [None]


@pytest.mark.skipif(
    not Config.SUCCESS_MODEL_JOBLIB.exists(),
    reason="Trained success model artifact is not present.",
)
def test_trained_artifact_matches_feature_contract_and_metrics():
    service = SuccessModelService(
        Config.SUCCESS_MODEL_JOBLIB,
        Config.SUCCESS_METRICS_JSON,
    )

    assert service.is_available is True
    assert service.feature_columns == APP_FEATURES
    assert 0.0 < service.threshold < 1.0
    assert service.model_version

    probabilities = service.predict_success_scores(
        {
            "capital": 50000,
            "skills": ["Marketing", "Basic Bookkeeping"],
            "experience": "Intermediate",
            "setup": ["Online"],
        },
        [
            {
                "min_capital": 10000,
                "core_skills": "Marketing, Sales",
                "people_needed": "Solo",
            }
        ],
    )
    assert len(probabilities) == 1
    assert probabilities[0] is not None
    assert 0.0 <= probabilities[0] <= 1.0

    with open(Config.SUCCESS_METRICS_JSON, "r", encoding="utf-8") as handle:
        metrics = json.load(handle)

    assert metrics["feature_columns"] == APP_FEATURES
    assert "cross_validation" in metrics
    assert "holdout" in metrics
    assert "decision_threshold" in metrics
    assert metrics["model_selection"]["selection_metric"] == "nested_cv_pr_auc"
    assert Config.SUCCESS_MODEL_CARD_JSON.exists()
