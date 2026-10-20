import re
from pathlib import Path

import pandas as pd

from config import Config


CATALOG_COLUMNS = [
    "skill_name",
    "field",
    "maps_to",
    "aliases",
    "related_business_ids",
    "related_business_types",
    "source",
]


def catalog_path(path=None):
    return Path(path) if path else Path(Config.SKILL_CATALOG_CSV)


def load_skill_catalog(path=None):
    csv_path = catalog_path(path)
    if not csv_path.exists():
        return pd.DataFrame(columns=CATALOG_COLUMNS)

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    missing = [column for column in CATALOG_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"skill catalog is missing columns: {', '.join(missing)}")

    df = df[CATALOG_COLUMNS].copy()
    for column in CATALOG_COLUMNS:
        df[column] = df[column].astype(str).str.strip()
    return df


def split_values(value):
    return [part.strip() for part in re.split(r"[;,|]", str(value)) if part.strip()]


def related_business_ids(row):
    return [int(value) for value in split_values(row.get("related_business_ids", ""))]


def catalog_alias_map(path=None):
    aliases = {}
    df = load_skill_catalog(path)
    for _, row in df.iterrows():
        target = row["maps_to"]
        if not target:
            continue
        names = [row["skill_name"], *split_values(row["aliases"])]
        for name in names:
            key = name.lower()
            if key:
                aliases.setdefault(key, target)
    return aliases


def catalog_skill_names(path=None):
    df = load_skill_catalog(path)
    return sorted({name for name in df["skill_name"] if name}, key=str.lower)


def catalog_skill_graph(path=None):
    df = load_skill_catalog(path)
    by_name = {}
    by_target = {}
    business_skills = {}

    for _, row in df.iterrows():
        ids = related_business_ids(row)
        if not ids:
            continue

        skill_name = row["skill_name"].lower()
        if skill_name:
            by_name.setdefault(skill_name, set()).update(ids)

        target = row["maps_to"]
        if not target:
            continue
        by_target.setdefault(target.lower(), set()).update(ids)
        for business_id in ids:
            business_skills.setdefault(business_id, set()).add(target)

    return {
        "by_name": by_name,
        "by_target": by_target,
        "business_skills": business_skills,
    }


def get_skill_groups(selectable_skills=None, field_order=None, path=None):
    df = load_skill_catalog(path)
    if df.empty:
        return []

    field_order = list(field_order or [])
    allowed = None
    if selectable_skills is not None:
        allowed = {str(skill).strip().lower() for skill in selectable_skills}

    grouped = []
    assigned = set()
    for field in field_order:
        members = sorted(
            {
                row["skill_name"]
                for _, row in df.iterrows()
                if row["field"] == field
                and (allowed is None or row["skill_name"].lower() in allowed)
            },
            key=str.lower,
        )
        if members:
            grouped.append({"field": field, "skills": members})
            assigned.update(members)

    remaining = {
        row["skill_name"]
        for _, row in df.iterrows()
        if (allowed is None or row["skill_name"].lower() in allowed)
        and row["skill_name"] not in assigned
        and row["field"] not in field_order
    }
    if allowed is not None:
        catalog_names = {row["skill_name"].lower() for _, row in df.iterrows()}
        remaining.update(skill for skill in selectable_skills if str(skill).lower() not in catalog_names)
    remaining = sorted(remaining, key=str.lower)
    if remaining:
        grouped.append({"field": "Other Skills", "skills": remaining})
    return grouped
