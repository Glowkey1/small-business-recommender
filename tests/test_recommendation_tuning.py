import json

import pytest
import pandas as pd

from config import Config
from ml.recommendation_engine import HybridBusinessRecommender
from tune_recommender import build_candidates, load_benchmark


def test_candidates_include_baseline_and_keep_success_at_zero():
    candidates = build_candidates()
    baseline = {
        key: round(value / sum(Config.RECOMMENDATION_WEIGHTS.values()), 10)
        for key, value in Config.RECOMMENDATION_WEIGHTS.items()
    }
    baseline["success"] = 0.0

    assert len(candidates) == 27
    for key, value in baseline.items():
        assert candidates[0][key] == pytest.approx(value)
    for candidate in candidates:
        assert set(candidate) == set(Config.RECOMMENDATION_WEIGHTS)
        assert sum(candidate.values()) == pytest.approx(1.0)
        assert candidate["success"] == 0.0


def test_tuning_refuses_incomplete_labels(tmp_path):
    profiles_path = tmp_path / "profiles.csv"
    relevance_path = tmp_path / "relevance.csv"

    pd.DataFrame(
        [
            {
                "profile_id": "P01",
                "capital": 10000,
                "skills": "Cooking",
                "experience": "Beginner",
                "available_time": "5-6 hours/day",
                "setup": "Home-Based",
                "location_psgc": "0401021000",
                "location_display": "Rosario",
                "notes": "test",
            }
        ]
    ).to_csv(profiles_path, index=False)
    pd.DataFrame(
        [
            {
                "profile_id": "P01",
                "business_id": 1,
                "rank": 1,
                "relevance": "",
            }
        ]
    ).to_csv(relevance_path, index=False)

    with pytest.raises(ValueError, match="incomplete"):
        load_benchmark(profiles_path, relevance_path)


def test_engine_loads_valid_tuned_weights(tmp_path, monkeypatch):
    weights = dict(Config.RECOMMENDATION_WEIGHTS)
    weights["capital"] = 0.30
    weights["skills"] = 0.26
    weights_path = tmp_path / "recommendation_weights.json"
    weights_path.write_text(json.dumps({"weights": weights}), encoding="utf-8")

    monkeypatch.setattr(Config, "RECOMMENDATION_WEIGHTS_JSON", weights_path)
    engine = HybridBusinessRecommender()

    assert engine.weights["capital"] == pytest.approx(0.30)
    assert engine.weights["skills"] == pytest.approx(0.26)


def test_engine_ignores_invalid_tuned_weights(tmp_path, monkeypatch):
    weights = dict(Config.RECOMMENDATION_WEIGHTS)
    weights["capital"] = 0.90
    weights_path = tmp_path / "recommendation_weights.json"
    weights_path.write_text(json.dumps({"weights": weights}), encoding="utf-8")

    monkeypatch.setattr(Config, "RECOMMENDATION_WEIGHTS_JSON", weights_path)
    engine = HybridBusinessRecommender()

    for key, value in Config.RECOMMENDATION_WEIGHTS.items():
        assert engine.weights[key] == pytest.approx(value)
