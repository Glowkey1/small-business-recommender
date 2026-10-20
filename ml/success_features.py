import math

from ml.skill_fields import canonical_skill

APP_FEATURES = [
    "initial_capital",
    "financial_record_keeping",
    "internet_usage",
    "marketing_effort",
    "partnership",
    "industry_experience",
]

EXPERIENCE_YEARS = {
    "beginner": 0.0,
    "intermediate": 10.0,
    "experienced": 20.0,
}

FEATURE_BOUNDS = {
    "initial_capital": (0.0, 1.0),
    "financial_record_keeping": (0.0, 1.0),
    "internet_usage": (0.0, 1.0),
    "marketing_effort": (1.0, 7.0),
    "partnership": (0.0, 1.0),
    "industry_experience": (0.0, 20.0),
}

FINANCE_SKILL_TERMS = {
    "accounting",
    "billing",
    "bookkeeping",
    "costing",
    "finance",
    "financial",
}

DIGITAL_SKILL_TERMS = {
    "analytics",
    "computer literacy",
    "crm",
    "data management",
    "design",
    "development",
    "marketing",
    "programming",
    "seo",
    "social media",
    "technology",
}

MARKETING_SKILL_TERMS = {
    "advertising",
    "branding",
    "content creation",
    "crm",
    "marketing",
    "negotiation",
    "sales",
    "seo",
    "social media",
}


def _normalised_skills(user_profile):
    skills = user_profile.get("skills", []) or []
    normalised = set()
    for skill in skills:
        name = canonical_skill(skill).strip().lower()
        if not name:
            continue
        if name in {"accounting", "bookkeeping", "finance"}:
            name = "basic bookkeeping"
        normalised.add(name)
    return normalised


def _matches_any(skills, terms):
    return any(
        term in skill
        for skill in skills
        for term in terms
    )


def _safe_float(value, fallback=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return number


def map_success_features(user_profile, business_item):
    user_cap = _safe_float(user_profile.get("capital", 0.0))
    min_cap = _safe_float(business_item.get("min_capital", 0.0))
    skills = _normalised_skills(user_profile)
    experience = str(user_profile.get("experience", "Beginner")).strip().lower()
    setup = " ".join(str(value).lower() for value in user_profile.get("setup", []) or [])
    core_skills = str(business_item.get("core_skills", "")).lower()
    people_needed = str(business_item.get("people_needed", "")).lower()

    marketing_count = sum(
        1 for skill in skills if any(term in skill for term in MARKETING_SKILL_TERMS)
    )
    if marketing_count == 0:
        marketing_effort = 2.0
    elif marketing_count == 1:
        marketing_effort = 4.0
    elif marketing_count == 2:
        marketing_effort = 6.0
    else:
        marketing_effort = 7.0

    row = {
        "initial_capital": 1.0 if user_cap >= min_cap else 0.0,
        "financial_record_keeping": 1.0 if (
            _matches_any(skills, FINANCE_SKILL_TERMS)
            or any(term in core_skills for term in ("costing", "bookkeeping", "financial"))
        ) else 0.0,
        "internet_usage": 1.0 if (
            "online" in setup or _matches_any(skills, DIGITAL_SKILL_TERMS)
        ) else 0.0,
        "marketing_effort": marketing_effort,
        "partnership": 1.0 if ("solo" not in people_needed and people_needed) else 0.0,
        "industry_experience": EXPERIENCE_YEARS.get(experience, 0.0),
    }

    for feature, (low, high) in FEATURE_BOUNDS.items():
        value = _safe_float(row[feature], fallback=low)
        row[feature] = float(min(max(value, low), high))

    return {feature: row[feature] for feature in APP_FEATURES}
