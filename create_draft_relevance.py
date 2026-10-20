import argparse
import re
from pathlib import Path

import pandas as pd

from config import Config
from evaluate_recommender import DEFAULT_PROFILES, DEFAULT_RELEVANCE, load_profiles
from ml.recommendation_engine import HybridBusinessRecommender

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BASE_DIR / "data" / "eval" / "recommendation_relevance_draft.csv"
DEFAULT_FULL_OUTPUT = (
    BASE_DIR / "data" / "eval" / "recommendation_relevance_draft_full.csv"
)
DRAFT_LABELER = "draft-heuristic-v1"


def _split(value):
    if pd.isna(value) or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split("|") if part.strip()]


def _capital_points(profile_capital, micro_capital, full_capital):
    if full_capital <= profile_capital:
        return 2
    if micro_capital <= profile_capital:
        return 1
    return 0


def _skill_points(skills, core_skills, engine):
    if not skills:
        return 1, "no skills selected"
    _, matched, gaps = engine.calculate_skill_score(skills, str(core_skills))
    total = len(matched) + len(gaps)
    if total == 0:
        return 1, "no core skills listed"
    ratio = len(matched) / total
    if ratio >= 0.5:
        return 2, f"{len(matched)}/{total} core skills matched"
    if ratio > 0:
        return 1, f"{len(matched)}/{total} core skills matched"
    return 0, f"0/{total} core skills matched"


def _setup_points(business_setup, profile_setups):
    business = str(business_setup).lower()
    profile = [item.lower() for item in profile_setups]
    checks = {
        "online": "online" in business,
        "home-based": "home" in business,
        "physical store": "store" in business or "commercial" in business,
        "service / mobile": (
            "service" in business or "mobile" in business or "market" in business
        ),
    }
    if any(checks.get(item, False) for item in profile):
        return 2, f"compatible setup ({business_setup})"
    return 0, f"incompatible setup ({business_setup})"


def _people_count(people_needed):
    text = str(people_needed).lower()
    if "solo" in text or text.startswith("1"):
        return 1
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 2


def _time_points(people_needed, available_time):
    required_people = _people_count(people_needed)
    available = {
        "1-2 hours/day": 1,
        "3-4 hours/day": 2,
        "5-6 hours/day": 3,
        "7-8 hours/day": 4,
        "Full-time": 4,
    }.get(str(available_time), 2)

    if required_people <= 1:
        return 2, "solo/small operation"
    if required_people < 5:
        return (2 if available >= 2 else 1), f"{people_needed} staffing need"
    return (2 if available >= 3 else 0), f"{people_needed} staffing need"


def _location_points(location_score):
    if location_score is None or pd.isna(location_score):
        return 1, "location signal unavailable"
    score = float(location_score)
    if score >= 85:
        return 2, f"strong local market signal ({score:.0f})"
    if score >= 70:
        return 1, f"moderate local market signal ({score:.0f})"
    return 0, f"weak local market signal ({score:.0f})"


def _label(points, capital_points, setup_points):
    if capital_points == 0:
        return 0
    if setup_points == 0:
        return 0
    if points >= 8:
        return 2
    if points >= 5:
        return 1
    return 0


def _draft_row(profile, business_id, business, location_score, engine, rank=0):
    capital_points = _capital_points(
        float(profile["capital"]),
        float(business["micro_start_capital"]),
        float(business["full_start_capital"]),
    )
    skill_points, skill_reason = _skill_points(
        _split(profile["skills"]),
        business["core_skills"],
        engine,
    )
    setup_points, setup_reason = _setup_points(
        business["business_setup"], _split(profile["setup"])
    )
    time_points, time_reason = _time_points(
        business["people_needed"], profile["available_time"]
    )
    location_points, location_reason = _location_points(location_score)

    points = capital_points + skill_points + setup_points + time_points + location_points
    relevance = _label(points, capital_points, setup_points)
    reason = (
        f"capital={capital_points}; {skill_reason}; {setup_reason}; "
        f"{time_reason}; {location_reason}; total={points}/10"
    )

    return {
        "profile_id": str(profile["profile_id"]),
        "profile_notes": profile.get("notes", ""),
        "rank": int(rank),
        "business_id": int(business_id),
        "business_type": business["business_type"],
        "category": business.get("category", ""),
        "relevance": relevance,
        "notes": reason,
        "labeled_by": DRAFT_LABELER,
        "draft_points": points,
    }


def build_draft_labels(profiles_path=DEFAULT_PROFILES,
                       relevance_path=DEFAULT_RELEVANCE,
                       output_path=DEFAULT_OUTPUT,
                       all_businesses=False):
    profiles = load_profiles(profiles_path)
    businesses = pd.read_csv(Config.FINAL_BUSINESSES_CSV).set_index("id")
    engine = HybridBusinessRecommender()
    profile_map = {
        str(row["profile_id"]): row for _, row in profiles.iterrows()
    }

    rows = []
    if all_businesses:
        location_cache = {}
        for _, profile in profiles.iterrows():
            profile_id = str(profile["profile_id"])
            psgc = str(profile["location_psgc"]).zfill(10)
            for business_id, business in businesses.iterrows():
                cache_key = (psgc, str(business["business_type"]))
                if cache_key not in location_cache:
                    market = engine.market_analyzer.analyze_location_market(
                        psgc, str(business["business_type"])
                    )
                    score = market["location_score"]
                    location_cache[cache_key] = (
                        score * 100 if score is not None else None
                    )
                rows.append(
                    _draft_row(
                        profile,
                        business_id,
                        business,
                        location_cache[cache_key],
                        engine,
                    )
                )
    else:
        worksheet = pd.read_csv(relevance_path, dtype={"profile_id": str})
        for _, worksheet_row in worksheet.iterrows():
            profile_id = str(worksheet_row["profile_id"])
            business_id = int(worksheet_row["business_id"])
            rows.append(
                _draft_row(
                    profile_map[profile_id],
                    business_id,
                    businesses.loc[business_id],
                    worksheet_row.get("location_score"),
                    engine,
                    rank=worksheet_row.get("rank", 0),
                )
            )

    output = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)

    counts = output["relevance"].value_counts().sort_index().to_dict()
    print(f"Wrote {len(output)} draft labels to {output_path}")
    print(
        "Draft distribution: "
        f"0={counts.get(0, 0)}, 1={counts.get(1, 0)}, 2={counts.get(2, 0)}"
    )
    print("These are provisional heuristic labels, not human ground truth.")
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Generate provisional draft relevance labels for the benchmark."
    )
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--relevance", type=Path, default=DEFAULT_RELEVANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--all-businesses",
        action="store_true",
        help="Label every business for every profile, not just worksheet rows.",
    )
    args = parser.parse_args()
    output_path = DEFAULT_FULL_OUTPUT if args.all_businesses else args.output
    if args.all_businesses and args.output == DEFAULT_OUTPUT:
        args.output = output_path
    build_draft_labels(
        args.profiles,
        args.relevance,
        args.output,
        all_businesses=args.all_businesses,
    )


if __name__ == "__main__":
    main()
