import math

import pytest

from ml.recommendation_metrics import (
    average_precision_at_k,
    budget_feasibility_rate,
    catalog_coverage,
    category_diversity_at_k,
    evaluate_profiles,
    evaluate_ranked_list,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_precision_and_recall_at_k():
    relevances = [2, 0, 1, 0, 0]
    assert precision_at_k(relevances, 5) == pytest.approx(0.4)
    assert precision_at_k(relevances, 2) == pytest.approx(0.5)
    assert recall_at_k(relevances, 5) == pytest.approx(1.0)
    assert recall_at_k(relevances, 2) == pytest.approx(0.5)
    assert recall_at_k([0, 0, 1], 2) == pytest.approx(0.0)


def test_ndcg_at_k_uses_graded_relevance():
    relevances = [2, 0, 1, 0, 0]
    dcg = 3.0 + 1.0 / math.log2(4)
    ideal = 3.0 + 1.0 / math.log2(3)
    assert ndcg_at_k(relevances, 5) == pytest.approx(dcg / ideal)
    assert ndcg_at_k([0, 0, 0], 3) == 0.0


def test_ndcg_and_recall_use_full_scope_when_available():
    assert ndcg_at_k([0, 0], 2, ideal_relevances=[2, 2, 2]) == 0.0
    assert recall_at_k([2, 0], 2, total_relevant=4) == pytest.approx(0.25)
    result = evaluate_ranked_list(
        [2, 2],
        k=2,
        ideal_relevances=[2, 2, 2, 2],
        total_relevant=4,
    )
    assert result["ndcg"] == pytest.approx(1.0)
    assert result["recall"] == pytest.approx(0.5)


def test_average_precision_at_k():
    assert average_precision_at_k([2, 0, 1, 0, 0], 5) == pytest.approx(
        (1.0 + 2.0 / 3.0) / 2.0
    )
    assert average_precision_at_k([0, 0, 0], 3) == 0.0


def test_evaluate_ranked_list_returns_expected_shape():
    result = evaluate_ranked_list([2, 1, 0, 0, 0], k=5)
    assert result["k"] == 5
    assert result["labeled_count"] == 5
    assert result["relevant_count"] == 2
    assert 0.0 <= result["precision"] <= 1.0
    assert 0.0 <= result["ndcg"] <= 1.0


def test_evaluate_ranked_list_handles_short_lists():
    result = evaluate_ranked_list([2, 1], k=5)
    assert result["k"] == 5
    assert result["labeled_count"] == 2
    assert result["relevant_count"] == 2
    assert result["precision"] == pytest.approx(1.0)


def test_evaluate_profiles_aggregates_per_profile_metrics():
    result = evaluate_profiles({"P1": [2, 0, 1, 0, 0], "P2": [0, 0, 0, 0, 0]}, k=5)
    assert result["profile_count"] == 2
    assert result["aggregate"]["precision_at_5"] == pytest.approx(0.2)
    assert result["aggregate"]["recall_at_5"] == pytest.approx(0.5)
    assert result["aggregate"]["labeled_count"] == 10
    assert set(result["per_profile"]) == {"P1", "P2"}


def test_coverage_diversity_and_feasibility():
    assert catalog_coverage({"P1": [1, 2], "P2": [2, 3]}, catalog_size=4) == 0.75
    items = [
        {"category": "Food", "affordable": True},
        {"category": "Food", "affordable": False},
        {"category": "Retail", "affordable": True},
    ]
    assert category_diversity_at_k(items, k=3) == pytest.approx(2 / 3)
    assert budget_feasibility_rate(items, k=3) == pytest.approx(2 / 3)
