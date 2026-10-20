import argparse
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from sklearn.model_selection import KFold

from config import Config, validate_weights
from evaluate_recommender import (
    DEFAULT_PROFILES,
    DEFAULT_RELEVANCE,
    load_profiles,
    load_relevance,
    profile_to_engine_input,
)
from ml.recommendation_engine import HybridBusinessRecommender
from ml.recommendation_metrics import evaluate_ranked_list

DEFAULT_REPORT = Config.RECOMMENDATION_TUNING_REPORT_JSON
DEFAULT_OUTPUT = Config.RECOMMENDATION_WEIGHTS_JSON
METRICS = ("precision", "recall", "ndcg", "average_precision")


def load_benchmark(profiles_path, relevance_path):
    profiles = load_profiles(profiles_path)
    relevance = load_relevance(relevance_path)
    unlabeled = int(relevance["relevance_value"].isna().sum())
    if unlabeled:
        raise ValueError(
            f"Relevance labels are incomplete: {unlabeled}/{len(relevance)} rows "
            "are blank. Finish the labeling worksheet before tuning."
        )

    labels = {}
    for _, row in relevance.iterrows():
        labels[(str(row["profile_id"]), int(row["business_id"]))] = int(
            row["relevance_value"]
        )
    return profiles, labels


def _normalized(weights):
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Candidate weights have no positive mass.")
    result = {key: round(value / total, 10) for key, value in weights.items()}
    validate_weights(result)
    return result


def build_candidates(base_weights=None):
    base = dict(base_weights or Config.RECOMMENDATION_WEIGHTS)
    base["success"] = 0.0
    baseline = _normalized(base)
    candidates = [baseline]
    seen = {tuple(baseline[name] for name in sorted(baseline))}

    for capital_factor, skills_factor, location_factor in itertools.product(
        (0.8, 1.0, 1.2),
        (0.8, 1.0, 1.2),
        (0.6, 1.0, 1.4),
    ):
        weights = dict(base)
        weights["capital"] *= capital_factor
        weights["skills"] *= skills_factor
        weights["location"] *= location_factor
        weights["success"] = 0.0
        weights = _normalized(weights)
        key = tuple(weights[name] for name in sorted(weights))
        if key not in seen:
            seen.add(key)
            candidates.append(weights)

    return candidates


def _aggregate(per_profile, profile_ids=None, k=5):
    ids = list(profile_ids) if profile_ids is not None else list(per_profile)
    result = {}
    for metric in METRICS:
        result[f"{metric}_at_{k}"] = round(
            mean(per_profile[profile_id][metric] for profile_id in ids), 4
        )
    result["relevant_count"] = sum(
        per_profile[profile_id]["relevant_count"] for profile_id in ids
    )
    result["labeled_count"] = sum(
        per_profile[profile_id]["labeled_count"] for profile_id in ids
    )
    return result


def evaluate_candidate(engine, profiles, labels, scope_labels, weights, k):
    original_weights = engine.weights
    engine.weights = dict(weights)
    per_profile = {}
    try:
        for _, profile in profiles.iterrows():
            profile_id = str(profile["profile_id"])
            results = engine.recommend(
                profile_to_engine_input(profile), top_n=k
            )
            relevances = []
            for result in results:
                key = (profile_id, int(result["business_id"]))
                if key not in labels:
                    raise ValueError(
                        f"Missing relevance label for profile {profile_id}, "
                        f"business {result['business_id']}."
                    )
                relevances.append(labels[key])
            per_profile[profile_id] = evaluate_ranked_list(
                relevances,
                k=k,
                threshold=1,
                ideal_relevances=scope_labels[profile_id],
            )
    finally:
        engine.weights = original_weights

    return {
        "weights": dict(weights),
        "per_profile": per_profile,
        "aggregate": _aggregate(per_profile, k=k),
    }


def _selection_key(evaluation, k):
    aggregate = evaluation["aggregate"]
    return (
        aggregate[f"ndcg_at_{k}"],
        aggregate[f"precision_at_{k}"],
        aggregate[f"average_precision_at_{k}"],
    )


def _selection_key_for_profiles(evaluation, profile_ids, k):
    aggregate = _aggregate(evaluation["per_profile"], profile_ids, k)
    return (
        aggregate[f"ndcg_at_{k}"],
        aggregate[f"precision_at_{k}"],
        aggregate[f"average_precision_at_{k}"],
    )


def cross_validate(evaluations, profile_ids, folds, k, seed):
    splitter = KFold(n_splits=folds, shuffle=True, random_state=seed)
    cv_profile_metrics = {}
    baseline_profile_metrics = {}
    fold_details = []
    baseline = evaluations[0]

    for fold_number, (train_index, test_index) in enumerate(
        splitter.split(profile_ids), start=1
    ):
        train_ids = [profile_ids[index] for index in train_index]
        test_ids = [profile_ids[index] for index in test_index]

        best = max(
            evaluations,
            key=lambda item: _selection_key_for_profiles(item, train_ids, k),
        )
        for profile_id in test_ids:
            cv_profile_metrics[profile_id] = best["per_profile"][profile_id]
            baseline_profile_metrics[profile_id] = baseline["per_profile"][profile_id]

        fold_details.append(
            {
                "fold": fold_number,
                "train_profiles": train_ids,
                "test_profiles": test_ids,
                "selected_weights": best["weights"],
                "train_metrics": _aggregate(best["per_profile"], train_ids, k),
                "test_metrics": _aggregate(best["per_profile"], test_ids, k),
            }
        )

    return {
        "folds": folds,
        "seed": seed,
        "aggregate_test": _aggregate(cv_profile_metrics, k=k),
        "baseline_test": _aggregate(baseline_profile_metrics, k=k),
        "fold_details": fold_details,
    }


def tune(k=5, folds=5, seed=42, profiles_path=DEFAULT_PROFILES,
         relevance_path=DEFAULT_RELEVANCE, output_path=DEFAULT_OUTPUT,
         report_path=DEFAULT_REPORT):
    if not 1 <= k <= 5:
        raise ValueError(
            "k must be between 1 and 5 because the benchmark's first five rows "
            "match the app's displayed results."
        )
    if folds < 2:
        raise ValueError("folds must be at least 2.")

    profiles, labels = load_benchmark(profiles_path, relevance_path)
    profile_ids = [str(value) for value in profiles["profile_id"]]
    if len(profile_ids) < folds:
        raise ValueError("Not enough profiles for the requested folds.")

    engine = HybridBusinessRecommender()
    catalog_ids = sorted(int(value) for value in engine.df_businesses["id"])
    scope_labels = {}
    full_catalog_profiles = 0
    for profile_id in profile_ids:
        full_scope = []
        for business_id in catalog_ids:
            key = (profile_id, business_id)
            if key not in labels:
                full_scope = None
                break
            full_scope.append(labels[key])
        if full_scope is not None:
            scope_labels[profile_id] = full_scope
            full_catalog_profiles += 1
        else:
            scope_labels[profile_id] = [
                value
                for (candidate_profile, _), value in labels.items()
                if candidate_profile == profile_id
            ]

    label_scope = (
        "full_catalog"
        if full_catalog_profiles == len(profile_ids)
        else "partial_labeled_candidates"
    )
    candidates = build_candidates()
    evaluations = [
        evaluate_candidate(
            engine, profiles, labels, scope_labels, weights, k
        )
        for weights in candidates
    ]

    best = max(evaluations, key=lambda item: _selection_key(item, k))
    baseline = evaluations[0]
    cv = cross_validate(evaluations, profile_ids, folds, k, seed)

    report = {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "k": k,
        "benchmark": {
            "profiles": len(profile_ids),
            "labels": len(labels),
            "label_scope": label_scope,
            "full_catalog_profile_count": full_catalog_profiles,
            "profile_file": str(profiles_path),
            "relevance_file": str(relevance_path),
        },
        "candidate_count": len(candidates),
        "selection_metric": f"ndcg_at_{k}",
        "baseline": {
            "weights": baseline["weights"],
            "full_metrics": baseline["aggregate"],
            "cv_metrics": cv["baseline_test"],
        },
        "selected": {
            "weights": best["weights"],
            "full_metrics": best["aggregate"],
        },
        "cv": cv,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    payload = {
        "weights": best["weights"],
        "selected_by": f"profile-level {folds}-fold CV; full-data {report['selection_metric']}",
        "generated_at": report["generated_at"],
        "candidate_count": len(candidates),
        "cv_test_metrics": cv["aggregate_test"],
        "baseline_cv_test_metrics": cv["baseline_test"],
        "full_metrics": best["aggregate"],
        "report": str(report_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print(
        f"Selected weights on {len(profile_ids)} profiles and {len(candidates)} "
        f"candidates. CV NDCG@{k}={cv['aggregate_test'][f'ndcg_at_{k}']:.4f}, "
        f"baseline={cv['baseline_test'][f'ndcg_at_{k}']:.4f}."
    )
    print(f"Weights: {output_path}")
    print(f"Report: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Tune recommendation weights against labeled benchmark data."
    )
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--relevance", type=Path, default=DEFAULT_RELEVANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        tune(
            k=args.k,
            folds=args.folds,
            seed=args.seed,
            profiles_path=args.profiles,
            relevance_path=args.relevance,
            output_path=args.output,
            report_path=args.report,
        )
    except ValueError as exc:
        print(exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
