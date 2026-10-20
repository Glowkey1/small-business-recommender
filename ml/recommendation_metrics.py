import math


def _cut(relevances, k):
    if k <= 0:
        return []
    return list(relevances[:k])


def dcg_at_k(relevances, k):
    scores = _cut(relevances, k)
    return sum(
        (2 ** float(relevance) - 1) / math.log2(index + 2)
        for index, relevance in enumerate(scores)
    )


def ndcg_at_k(relevances, k, ideal_relevances=None):
    scores = _cut(relevances, k)
    if not scores:
        return 0.0
    ideal_source = scores if ideal_relevances is None else list(ideal_relevances)
    ideal = sorted(ideal_source, reverse=True)[:k]
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg == 0:
        return 0.0
    return dcg_at_k(scores, k) / ideal_dcg


def precision_at_k(relevances, k, threshold=1):
    scores = _cut(relevances, k)
    if not scores:
        return 0.0
    relevant = sum(1 for score in scores if score >= threshold)
    return relevant / len(scores)


def recall_at_k(relevances, k, total_relevant=None, threshold=1):
    scores = _cut(relevances, k)
    if total_relevant is None:
        total_relevant = sum(
            1 for relevance in relevances if relevance >= threshold
        )
    if total_relevant <= 0:
        return 0.0
    relevant = sum(1 for score in scores if score >= threshold)
    return min(1.0, relevant / total_relevant)


def average_precision_at_k(relevances, k, threshold=1, total_relevant=None):
    scores = _cut(relevances, k)
    if not scores:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for index, relevance in enumerate(scores, start=1):
        if relevance >= threshold:
            hits += 1
            precision_sum += hits / index
    if hits == 0:
        return 0.0
    if total_relevant is None:
        total_relevant = sum(
            1 for relevance in relevances if relevance >= threshold
        )
    denominator = min(total_relevant, len(scores))
    return precision_sum / denominator if denominator else 0.0


def evaluate_ranked_list(relevances, k=5, threshold=1,
                         ideal_relevances=None, total_relevant=None):
    scores = _cut(relevances, k)
    if ideal_relevances is None:
        ideal_relevances = relevances
    if total_relevant is None:
        total_relevant = sum(
            1 for relevance in ideal_relevances if relevance >= threshold
        )
    return {
        "k": k,
        "precision": precision_at_k(scores, k, threshold),
        "recall": recall_at_k(
            scores, k, total_relevant=total_relevant, threshold=threshold
        ),
        "ndcg": ndcg_at_k(scores, k, ideal_relevances=ideal_relevances),
        "average_precision": average_precision_at_k(
            scores, k, threshold, total_relevant=total_relevant
        ),
        "relevant_count": sum(1 for score in scores if score >= threshold),
        "labeled_count": len(scores),
    }


def evaluate_profiles(profile_rankings, k=5, threshold=1, full_rankings=None):
    per_profile = {}
    for profile_id, relevances in profile_rankings.items():
        scope = relevances
        if full_rankings and profile_id in full_rankings:
            scope = full_rankings[profile_id]
        per_profile[profile_id] = evaluate_ranked_list(
            relevances,
            k=k,
            threshold=threshold,
            ideal_relevances=scope,
        )

    if not per_profile:
        return {
            "k": k,
            "threshold": threshold,
            "profile_count": 0,
            "per_profile": {},
            "aggregate": {},
        }

    metric_names = ("precision", "recall", "ndcg", "average_precision")
    aggregate = {
        f"{metric}_at_{k}": round(
            sum(values[metric] for values in per_profile.values())
            / len(per_profile),
            4,
        )
        for metric in metric_names
    }
    aggregate["relevant_count"] = sum(
        values["relevant_count"] for values in per_profile.values()
    )
    aggregate["labeled_count"] = sum(
        values["labeled_count"] for values in per_profile.values()
    )
    return {
        "k": k,
        "threshold": threshold,
        "profile_count": len(per_profile),
        "per_profile": per_profile,
        "aggregate": aggregate,
    }


def catalog_coverage(recommended_ids_by_profile, catalog_size):
    if catalog_size <= 0:
        return 0.0
    unique_ids = set()
    for ids in recommended_ids_by_profile.values():
        unique_ids.update(ids)
    return len(unique_ids) / catalog_size


def category_diversity_at_k(items, k=5):
    selected = list(items[:k])
    if not selected:
        return 0.0
    categories = {
        str(item.get("market_category") or item.get("category") or "").strip().lower()
        for item in selected
    }
    categories.discard("")
    if not categories:
        return 0.0
    return len(categories) / len(selected)


def budget_feasibility_rate(items, k=5):
    selected = list(items[:k])
    if not selected:
        return 0.0
    affordable = sum(1 for item in selected if item.get("affordable") is True)
    return affordable / len(selected)
