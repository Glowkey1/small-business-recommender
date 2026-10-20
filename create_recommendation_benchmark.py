import argparse
from pathlib import Path

import pandas as pd

from ml.recommendation_engine import HybridBusinessRecommender

BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR / "data" / "eval"
PROFILES_PATH = EVAL_DIR / "recommendation_profiles.csv"
RELEVANCE_PATH = EVAL_DIR / "recommendation_relevance.csv"

PROFILES = [
    ("P01", 10000, "Cooking|Baking", "Beginner", "5-6 hours/day", "Home-Based", "0401021000", "Food beginner, Rosario Batangas"),
    ("P02", 5000, "Cooking", "Beginner", "3-4 hours/day", "Home-Based", "0402117000", "Very low capital, Rosario Cavite"),
    ("P03", 15000, "Sales", "Beginner", "5-6 hours/day", "Online", "0401014000", "Sales beginner, Lipa"),
    ("P04", 25000, "Marketing|Sales", "Intermediate", "Full-time", "Online|Home-Based", "0401005000", "Marketing and sales, Batangas City"),
    ("P05", 30000, "Basic Bookkeeping|Accounting", "Intermediate", "5-6 hours/day", "Online", "0431200000", "Finance skills, Lucena"),
    ("P06", 50000, "Marketing|Content Creation", "Intermediate", "7-8 hours/day", "Online", "0402119000", "Content and marketing, Tagaytay"),
    ("P07", 100000, "Management|Leadership", "Experienced", "Full-time", "Physical Store", "0405802000", "Management, Antipolo"),
    ("P08", 250000, "Management|Budgeting", "Experienced", "Full-time", "Physical Store", "0403405000", "High capital management, Calamba"),
    ("P09", 8000, "Gardening", "Beginner", "3-4 hours/day", "Home-Based", "0401021000", "Agriculture beginner, Rosario Batangas"),
    ("P10", 20000, "Gardening|Animal Care", "Intermediate", "5-6 hours/day", "Home-Based", "0402117000", "Agriculture, Rosario Cavite"),
    ("P11", 12000, "Baking", "Beginner", "5-6 hours/day", "Home-Based", "0401014000", "Baking beginner, Lipa"),
    ("P12", 35000, "Cooking|Food Costing", "Intermediate", "Full-time", "Physical Store", "0401005000", "Food business, Batangas City"),
    ("P13", 10000, "Computer Literacy", "Beginner", "3-4 hours/day", "Online", "0431200000", "Digital beginner, Lucena"),
    ("P14", 40000, "Programming|Design", "Intermediate", "Full-time", "Online", "0402119000", "Tech and design, Tagaytay"),
    ("P15", 120000, "Development|Analytics", "Experienced", "Full-time", "Online", "0405802000", "Tech experienced, Antipolo"),
    ("P16", 15000, "Carpentry", "Beginner", "5-6 hours/day", "Service / Mobile", "0403405000", "Trades beginner, Calamba"),
    ("P17", 60000, "Electrical|Maintenance", "Intermediate", "Full-time", "Service / Mobile", "0403428000", "Electrical services, Santa Rosa"),
    ("P18", 150000, "Diagnostics|Maintenance", "Experienced", "Full-time", "Physical Store", "0402103000", "Repair shop, Bacoor"),
    ("P19", 10000, "Customer Service|Communication", "Beginner", "3-4 hours/day", "Online", "0403424000", "Customer service, San Pablo"),
    ("P20", 25000, "Sales|Negotiation", "Intermediate", "5-6 hours/day", "Physical Store", "0405647000", "Retail sales, Tayabas"),
    ("P21", 6000, "", "Beginner", "1-2 hours/day", "Home-Based", "0402117000", "No skills, very low capital"),
    ("P22", 50000, "", "Beginner", "5-6 hours/day", "Online", "0405805000", "No skills, higher capital, Cainta"),
    ("P23", 80000, "Logistics|Coordination", "Intermediate", "Full-time", "Service / Mobile", "0402108000", "Logistics, General Trias"),
    ("P24", 200000, "Logistics|Distribution", "Experienced", "Full-time", "Physical Store", "0401005000", "Distribution, Batangas City"),
    ("P25", 12000, "Cleaning|Hygiene", "Beginner", "5-6 hours/day", "Service / Mobile", "0401014000", "Cleaning services, Lipa"),
    ("P26", 30000, "Grooming|Hygiene", "Intermediate", "Full-time", "Physical Store", "0431200000", "Personal care, Lucena"),
    ("P27", 20000, "Teaching|Training", "Beginner", "5-6 hours/day", "Online", "0402119000", "Teaching, Tagaytay"),
    ("P28", 45000, "Content Creation|Social Media", "Intermediate", "Full-time", "Online", "0405802000", "Social media, Antipolo"),
    ("P29", 90000, "Consulting|Strategy", "Experienced", "Full-time", "Online", "0403405000", "Consulting, Calamba"),
    ("P30", 18000, "Delivery|Routing", "Beginner", "5-6 hours/day", "Service / Mobile", "0403428000", "Delivery, Santa Rosa"),
]

PROFILE_COLUMNS = [
    "profile_id",
    "capital",
    "skills",
    "experience",
    "available_time",
    "setup",
    "location_psgc",
    "location_display",
    "notes",
]

WORKSHEET_COLUMNS = [
    "profile_id",
    "profile_notes",
    "rank",
    "business_id",
    "business_type",
    "category",
    "score",
    "affordable",
    "capital_score",
    "skills_score",
    "experience_score",
    "setup_score",
    "time_score",
    "location_score",
    "success_score",
    "team_score",
    "relevance",
    "notes",
    "labeled_by",
]


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


def _existing_labels(path):
    if not path.exists():
        return {}
    try:
        existing = pd.read_csv(path)
    except Exception:
        return {}
    labels = {}
    for _, row in existing.iterrows():
        key = (str(row.get("profile_id", "")), int(row.get("business_id", -1)))
        labels[key] = {
            "relevance": "" if pd.isna(row.get("relevance")) else row.get("relevance"),
            "notes": "" if pd.isna(row.get("notes")) else row.get("notes"),
            "labeled_by": "" if pd.isna(row.get("labeled_by")) else row.get("labeled_by"),
        }
    return labels


def build_benchmark(top_n=10):
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    profiles = []
    for profile_id, capital, skills, experience, available_time, setup, location, notes in PROFILES:
        profiles.append(
            {
                "profile_id": profile_id,
                "capital": capital,
                "skills": skills,
                "experience": experience,
                "available_time": available_time,
                "setup": setup,
                "location_psgc": location,
                "location_display": "",
                "notes": notes,
            }
        )
    profiles_df = pd.DataFrame(profiles, columns=PROFILE_COLUMNS)

    engine = HybridBusinessRecommender()
    market = engine.market_analyzer.df_market[["adm3_psgc", "display_city"]].drop_duplicates()
    location_map = dict(zip(market["adm3_psgc"], market["display_city"]))
    profiles_df["location_display"] = profiles_df["location_psgc"].map(
        lambda psgc: location_map.get(str(psgc).zfill(10), psgc)
    )

    previous_labels = _existing_labels(RELEVANCE_PATH)
    worksheet_rows = []
    short_profiles = []

    for _, profile in profiles_df.iterrows():
        engine_input = profile_to_engine_input(profile)
        primary = engine.recommend(engine_input, top_n=5)
        extended = engine.recommend(engine_input, top_n=max(20, top_n * 2))
        results = []
        seen = set()
        for result in primary + extended:
            business_id = int(result["business_id"])
            if business_id in seen:
                continue
            seen.add(business_id)
            results.append(result)
            if len(results) == top_n:
                break

        if len(results) < top_n:
            short_profiles.append(
                f"{profile['profile_id']} ({len(results)}/{top_n})"
            )

        for rank, result in enumerate(results, start=1):
            components = result.get("component_scores", {})
            key = (str(profile["profile_id"]), int(result["business_id"]))
            previous = previous_labels.get(key, {})
            worksheet_rows.append(
                {
                    "profile_id": profile["profile_id"],
                    "profile_notes": profile["notes"],
                    "rank": rank,
                    "business_id": result["business_id"],
                    "business_type": result["business_type"],
                    "category": result.get("category", ""),
                    "score": result["recommendation_score"],
                    "affordable": result.get("affordable", False),
                    "capital_score": components.get("capital"),
                    "skills_score": components.get("skills"),
                    "experience_score": components.get("experience"),
                    "setup_score": components.get("setup"),
                    "time_score": components.get("time"),
                    "location_score": components.get("location"),
                    "success_score": components.get("success"),
                    "team_score": components.get("team"),
                    "relevance": previous.get("relevance", ""),
                    "notes": previous.get("notes", ""),
                    "labeled_by": previous.get("labeled_by", ""),
                }
            )

    worksheet = pd.DataFrame(worksheet_rows, columns=WORKSHEET_COLUMNS)
    profiles_df.to_csv(PROFILES_PATH, index=False)
    worksheet.to_csv(RELEVANCE_PATH, index=False)

    labeled = worksheet["relevance"].apply(
        lambda value: str(value).strip() != "" if not pd.isna(value) else False
    ).sum()
    print(f"Wrote {len(profiles_df)} profiles to {PROFILES_PATH}")
    print(f"Wrote {len(worksheet)} worksheet rows to {RELEVANCE_PATH}")
    print(f"Preserved {int(labeled)} existing labels")
    if short_profiles:
        print(
            f"{len(short_profiles)} profiles returned fewer than {top_n} "
            f"skill-connected candidates: {', '.join(short_profiles)}"
        )
    return profiles_df, worksheet


def main():
    parser = argparse.ArgumentParser(
        description="Generate the recommendation benchmark profiles and labeling worksheet."
    )
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Accepted for compatibility; existing labels are always preserved.",
    )
    args = parser.parse_args()
    build_benchmark(top_n=args.top_n)


if __name__ == "__main__":
    main()
