import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import validate_weights
from ml.recommendation_engine import HybridBusinessRecommender
from ml.recommendation_metrics import (
    budget_feasibility_rate,
    catalog_coverage,
    category_diversity_at_k,
    evaluate_profiles,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILES = BASE_DIR / "data" / "eval" / "recommendation_profiles.csv"
DEFAULT_RELEVANCE = BASE_DIR / "data" / "eval" / "recommendation_relevance.csv"
DEFAULT_OUTPUT = BASE_DIR / "models" / "recommendation_metrics.json"
ALLOWED_RELEVANCE = {0, 1, 2}


def load_weights_file(path, expected_keys):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    weights = payload.get("weights", payload)
    if not isinstance(weights, dict):
        raise ValueError("Weights payload must be a dictionary.")
    if set(weights) != set(expected_keys):
        raise ValueError("Weight keys do not match the recommender schema.")
    weights = {key: float(value) for key, value in weights.items()}
    validate_weights(weights)
    return weights


def _split(value):
    if pd.isna(value) or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split("|") if part.strip()]


def profile_to_engine_input(row):
    return {
        "capital": float(row["capital"]),
        "skills": _split(row["skills"]),
        "experience": str(row["experience"]),
        "available_time": str(row["available_time"]),
        "setup": _split(row["setup"]),
        "location": str(row["location_psgc"]).zfill(10),
    }


def load_profiles(path=DEFAULT_PROFILES):
    if not path.exists():
        raise FileNotFoundError(f"Profiles file not found: {path}")
    profiles = pd.read_csv(path, dtype={"location_psgc": str})
    required = {
        "profile_id",
        "capital",
        "skills",
        "experience",
        "available_time",
        "setup",
        "location_psgc",
    }
    missing = required - set(profiles.columns)
    if missing:
        raise ValueError(f"Profiles file is missing columns: {sorted(missing)}")
    return profiles


def parse_relevance(value):
    if pd.isna(value) or str(value).strip() == "":
        return None
    number = int(float(value))
    if number not in ALLOWED_RELEVANCE:
        raise ValueError(f"Invalid relevance value: {value!r}")
    return number


def load_relevance(path=DEFAULT_RELEVANCE):
    if not path.exists():
        raise FileNotFoundError(f"Relevance worksheet not found: {path}")
    frame = pd.read_csv(path, dtype={"profile_id": str})
    required = {"profile_id", "business_id", "rank", "relevance"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Relevance worksheet is missing columns: {sorted(missing)}")
    frame["relevance_value"] = frame["relevance"].apply(parse_relevance)
    frame["business_id"] = frame["business_id"].astype(int)
    return frame


def _proxy_metrics(engine, profiles, k):
    diversity_values = []
    feasibility_values = []
    recommended_ids = {}

    for _, profile in profiles.iterrows():
        results = engine.recommend(profile_to_engine_input(profile), top_n=k)
        recommended_ids[str(profile["profile_id"])] = [
            int(result["business_id"]) for result in results
        ]
        diversity_values.append(category_diversity_at_k(results, k=k))
        feasibility_values.append(budget_feasibility_rate(results, k=k))

    return {
        "coverage_at_k": round(
            catalog_coverage(recommended_ids, len(engine.df_businesses)), 4
        ),
        "category_diversity_at_k": round(
            sum(diversity_values) / len(diversity_values), 4
        ) if diversity_values else 0.0,
        "budget_feasibility_at_k": round(
            sum(feasibility_values) / len(feasibility_values), 4
        ) if feasibility_values else 0.0,
    }


def evaluate(k=5, relevance_threshold=1, profiles_path=DEFAULT_PROFILES,
             relevance_path=DEFAULT_RELEVANCE, output_path=DEFAULT_OUTPUT,
             weights_path=None):
    if not 1 <= k <= 5:
        raise ValueError(
            "k must be between 1 and 5 because the benchmark's first five rows "
            "match the app's displayed results."
        )
    profiles = load_profiles(profiles_path)
    relevance = load_relevance(relevance_path)

    total_labels = len(relevance)
    labeled_labels = int(relevance["relevance_value"].notna().sum())
    unlabeled_labels = total_labels - labeled_labels

    engine = HybridBusinessRecommender()
    weights_source = "active"
    if weights_path:
        engine.weights = load_weights_file(weights_path, engine.weights)
        weights_source = str(weights_path)
    version = engine.artifact_version(k)
    report = {
        "status": "ok" if unlabeled_labels == 0 else "unlabeled",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "k": k,
        "relevance_threshold": relevance_threshold,
        "profile_count": int(len(profiles)),
        "recommender_version": version,
        "weights_source": weights_source,
        "weights": engine.weights,
        "catalog_size": int(len(engine.df_businesses)),
        "labeling": {
            "worksheet_rows": total_labels,
            "labeled_rows": labeled_labels,
            "unlabeled_rows": unlabeled_labels,
            "completion": round(labeled_labels / total_labels, 4) if total_labels else 0.0,
        },
    }

    proxy = _proxy_metrics(engine, profiles, k)
    report["proxy_metrics"] = proxy

    if unlabeled_labels:
        report["message"] = (
            "Relevance labels are incomplete. Precision, recall, NDCG, and MAP "
            "are unavailable until every worksheet row is labeled."
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(report["message"])
        print(f"Labeled {labeled_labels}/{total_labels} rows. Report: {output_path}")
        return report

    labels = {}
    for _, row in relevance.iterrows():
        key = (str(row["profile_id"]), int(row["business_id"]))
        labels[key] = int(row["relevance_value"])

    catalog_ids = sorted(int(value) for value in engine.df_businesses["id"])
    scope_labels = {}
    full_catalog_profiles = 0
    for _, profile in profiles.iterrows():
        profile_id = str(profile["profile_id"])
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

    for profile_id, group in relevance.groupby("profile_id"):
        profile_id = str(profile_id)
        if profile_id not in scope_labels:
            scope_labels[profile_id] = [
                int(value) for value in group["relevance_value"].tolist()
            ]

    report["label_scope"] = (
        "full_catalog"
        if full_catalog_profiles == len(profiles)
        else "partial_labeled_candidates"
    )
    report["full_catalog_profile_count"] = full_catalog_profiles

    profile_rankings = {}
    items_by_profile = {}
    recommended_ids = {}

    for _, profile in profiles.iterrows():
        profile_id = str(profile["profile_id"])
        results = engine.recommend(profile_to_engine_input(profile), top_n=k)
        ranked_labels = []
        for result in results:
            key = (profile_id, int(result["business_id"]))
            if key not in labels:
                raise ValueError(
                    f"Missing relevance label for profile {profile_id}, "
                    f"business {result['business_id']} ({result['business_type']})."
                )
            ranked_labels.append(labels[key])
        profile_rankings[profile_id] = ranked_labels
        items_by_profile[profile_id] = results
        recommended_ids[profile_id] = [
            int(result["business_id"]) for result in results
        ]

    metrics = evaluate_profiles(
        profile_rankings,
        k=k,
        threshold=relevance_threshold,
        full_rankings=scope_labels,
    )
    metrics["aggregate"]["coverage_at_k"] = round(
        catalog_coverage(recommended_ids, len(engine.df_businesses)), 4
    )
    metrics["aggregate"]["category_diversity_at_k"] = round(
        sum(
            category_diversity_at_k(items, k=k)
            for items in items_by_profile.values()
        ) / len(items_by_profile),
        4,
    )
    metrics["aggregate"]["budget_feasibility_at_k"] = round(
        sum(
            budget_feasibility_rate(items, k=k)
            for items in items_by_profile.values()
        ) / len(items_by_profile),
        4,
    )

    report["metrics"] = metrics
    report["proxy_metrics"] = {
        **proxy,
        **{
            key: metrics["aggregate"][key]
            for key in (
                "coverage_at_k",
                "category_diversity_at_k",
                "budget_feasibility_at_k",
            )
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    aggregate = metrics["aggregate"]
    print(
        f"Evaluated {metrics['profile_count']} profiles at k={k}. "
        f"Precision@{k}={aggregate[f'precision_at_{k}']:.4f}, "
        f"Recall@{k}={aggregate[f'recall_at_{k}']:.4f}, "
        f"NDCG@{k}={aggregate[f'ndcg_at_{k}']:.4f}, "
        f"Scope={report['label_scope']}, "
        f"Coverage={aggregate['coverage_at_k']:.4f}, "
        f"Feasibility={aggregate['budget_feasibility_at_k']:.4f}"
    )
    print(f"Report: {output_path}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate recommendation ranking against labeled relevance data."
    )
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--relevance", type=Path, default=DEFAULT_RELEVANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--relevance-threshold", type=int, default=1)
    args = parser.parse_args()

    try:
        report = evaluate(
            k=args.k,
            relevance_threshold=args.relevance_threshold,
            profiles_path=args.profiles,
            relevance_path=args.relevance,
            output_path=args.output,
            weights_path=args.weights,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(exc)
        return 2
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
