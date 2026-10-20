import re
from collections import defaultdict

import pandas as pd

from config import Config
from ml.skill_catalog import CATALOG_COLUMNS
from ml.skill_fields import (
    FIELD_ORDER,
    FIELD_SKILLS,
    OTHER_FIELD,
    SKILL_SYNONYM_MERGES,
    canonical_skill,
)
from ml.skill_normalizer import GENERIC_STOP_FRAGMENTS, parse_skills_list


CURATED_EXTENSIONS = [
    {
        "skill_name": "Food Safety",
        "field": "Food & Beverage",
        "maps_to": "Hygiene",
        "aliases": "food handling; food hygiene",
        "related_business_ids": [6, 36, 71],
    },
    {
        "skill_name": "Meal Planning",
        "field": "Food & Beverage",
        "maps_to": "Planning",
        "aliases": "meal prep planning; menu planning",
        "related_business_ids": [13, 113],
    },
    {
        "skill_name": "Menu Development",
        "field": "Food & Beverage",
        "maps_to": "Cooking",
        "aliases": "menu design; recipe development",
        "related_business_ids": [14, 53, 71, 121, 123],
    },
    {
        "skill_name": "Portion Control",
        "field": "Food & Beverage",
        "maps_to": "Food Costing",
        "aliases": "portioning; yield control",
        "related_business_ids": [121],
    },
    {
        "skill_name": "Irrigation",
        "field": "Agriculture & Environment",
        "maps_to": "Gardening",
        "aliases": "watering systems; irrigation systems",
        "related_business_ids": [52, 126],
    },
    {
        "skill_name": "Pest Management",
        "field": "Agriculture & Environment",
        "maps_to": "Plant Care",
        "aliases": "pest control; integrated pest management",
        "related_business_ids": [126],
    },
    {
        "skill_name": "Composting",
        "field": "Agriculture & Environment",
        "maps_to": "Gardening",
        "aliases": "compost production; organic composting",
        "related_business_ids": [52],
    },
    {
        "skill_name": "Soil Testing",
        "field": "Agriculture & Environment",
        "maps_to": "Gardening",
        "aliases": "soil analysis; soil health",
        "related_business_ids": [52, 63],
    },
    {
        "skill_name": "Livestock Management",
        "field": "Agriculture & Environment",
        "maps_to": "Animal Care",
        "aliases": "livestock raising; animal husbandry",
        "related_business_ids": [21],
    },
    {
        "skill_name": "Cash Handling",
        "field": "Retail & Sales",
        "maps_to": "Sales",
        "aliases": "cashiering; cash reconciliation",
        "related_business_ids": [120, 125],
    },
    {
        "skill_name": "Upselling",
        "field": "Retail & Sales",
        "maps_to": "Sales",
        "aliases": "upsell; cross-selling",
        "related_business_ids": [31, 32],
    },
    {
        "skill_name": "Visual Merchandising",
        "field": "Retail & Sales",
        "maps_to": "Merchandising",
        "aliases": "store display; retail display",
        "related_business_ids": [106],
    },
    {
        "skill_name": "Stock Auditing",
        "field": "Retail & Sales",
        "maps_to": "Inventory Management",
        "aliases": "stock counts; inventory audit",
        "related_business_ids": [6, 38, 70, 120],
    },
    {
        "skill_name": "Price Setting",
        "field": "Retail & Sales",
        "maps_to": "Pricing",
        "aliases": "pricing strategy; price setting",
        "related_business_ids": [5, 38, 51, 65, 110],
    },
    {
        "skill_name": "Copywriting",
        "field": "Marketing & Creative",
        "maps_to": "Writing",
        "aliases": "copywriting; ad copy",
        "related_business_ids": [9],
    },
    {
        "skill_name": "Graphic Design",
        "field": "Marketing & Creative",
        "maps_to": "Design",
        "aliases": "graphic design; visual design",
        "related_business_ids": [39, 56, 104],
    },
    {
        "skill_name": "Video Editing",
        "field": "Marketing & Creative",
        "maps_to": "Editing",
        "aliases": "video editing; video post-production",
        "related_business_ids": [55, 81, 87, 105, 108],
    },
    {
        "skill_name": "Social Media Management",
        "field": "Marketing & Creative",
        "maps_to": "Social Media",
        "aliases": "social media management; social media marketing",
        "related_business_ids": [121, 125],
    },
    {
        "skill_name": "Paid Advertising",
        "field": "Marketing & Creative",
        "maps_to": "Advertising",
        "aliases": "paid ads; PPC; digital ads",
        "related_business_ids": [23, 26],
    },
    {
        "skill_name": "Web Development",
        "field": "Technology & Data",
        "maps_to": "Development",
        "aliases": "web development; website development",
        "related_business_ids": [43, 61, 67, 83, 89],
    },
    {
        "skill_name": "Mobile App Development",
        "field": "Technology & Data",
        "maps_to": "Programming",
        "aliases": "mobile app development; app development",
        "related_business_ids": [4],
    },
    {
        "skill_name": "Data Processing",
        "field": "Technology & Data",
        "maps_to": "Data Management",
        "aliases": "data processing; data cleaning",
        "related_business_ids": [25],
    },
    {
        "skill_name": "Data Visualization",
        "field": "Technology & Data",
        "maps_to": "Analytics",
        "aliases": "data visualization; dashboards",
        "related_business_ids": [23, 25, 66, 74, 75],
    },
    {
        "skill_name": "API Integration",
        "field": "Technology & Data",
        "maps_to": "Integration",
        "aliases": "API integration; systems integration",
        "related_business_ids": [117],
    },
    {
        "skill_name": "UI/UX Design",
        "field": "Technology & Data",
        "maps_to": "UX",
        "aliases": "UI design; UX design; user experience; user interface",
        "related_business_ids": [4],
    },
    {
        "skill_name": "Solar Installation",
        "field": "Trades & Manufacturing",
        "maps_to": "Electrical",
        "aliases": "solar installation; PV installation",
        "related_business_ids": [98, 111],
    },
    {
        "skill_name": "Appliance Repair",
        "field": "Trades & Manufacturing",
        "maps_to": "Diagnostics",
        "aliases": "appliance repair; home appliance repair",
        "related_business_ids": [58],
    },
    {
        "skill_name": "Preventive Maintenance",
        "field": "Trades & Manufacturing",
        "maps_to": "Maintenance",
        "aliases": "preventive maintenance; planned maintenance",
        "related_business_ids": [3, 80, 101, 107],
    },
    {
        "skill_name": "Sewing",
        "field": "Trades & Manufacturing",
        "maps_to": "Production",
        "aliases": "sewing; garment construction",
        "related_business_ids": [37],
    },
    {
        "skill_name": "Upholstery",
        "field": "Trades & Manufacturing",
        "maps_to": "Finishing",
        "aliases": "upholstery; furniture upholstery",
        "related_business_ids": [86],
    },
    {
        "skill_name": "Fleet Management",
        "field": "Logistics & Operations",
        "maps_to": "Logistics",
        "aliases": "fleet management; vehicle fleet",
        "related_business_ids": [12, 100],
    },
    {
        "skill_name": "Warehouse Management",
        "field": "Logistics & Operations",
        "maps_to": "Inventory Management",
        "aliases": "warehouse management; warehouse operations",
        "related_business_ids": [16, 70, 115],
    },
    {
        "skill_name": "Procurement",
        "field": "Logistics & Operations",
        "maps_to": "Sourcing",
        "aliases": "procurement; purchasing",
        "related_business_ids": [26, 39, 51, 74, 85, 93, 106],
    },
    {
        "skill_name": "Customs Documentation",
        "field": "Logistics & Operations",
        "maps_to": "Documentation",
        "aliases": "customs documentation; customs clearance",
        "related_business_ids": [29],
    },
    {
        "skill_name": "Route Optimization",
        "field": "Logistics & Operations",
        "maps_to": "Routing",
        "aliases": "route optimization; route planning",
        "related_business_ids": [46, 76, 115],
    },
    {
        "skill_name": "Accounting",
        "field": "Business & Finance",
        "maps_to": "Basic Bookkeeping",
        "aliases": "accounting; financial accounting",
        "related_business_ids": [120],
    },
    {
        "skill_name": "Invoicing",
        "field": "Business & Finance",
        "maps_to": "Billing",
        "aliases": "invoicing; invoice preparation",
        "related_business_ids": [101, 106],
    },
    {
        "skill_name": "Taxation",
        "field": "Business & Finance",
        "maps_to": "Compliance",
        "aliases": "taxation; tax preparation; tax compliance",
        "related_business_ids": [29, 96],
    },
    {
        "skill_name": "Budgeting",
        "field": "Business & Finance",
        "maps_to": "Costing",
        "aliases": "budgeting; budget planning",
        "related_business_ids": [14, 76],
    },
    {
        "skill_name": "Market Research",
        "field": "Business & Finance",
        "maps_to": "Analytics",
        "aliases": "market research; customer research",
        "related_business_ids": [23, 66, 74, 75],
    },
    {
        "skill_name": "Conflict Resolution",
        "field": "Customer & People",
        "maps_to": "Customer Service",
        "aliases": "conflict resolution; dispute handling",
        "related_business_ids": [65, 120, 122],
    },
    {
        "skill_name": "Complaint Handling",
        "field": "Customer & People",
        "maps_to": "Customer Service",
        "aliases": "complaint handling; customer complaints",
        "related_business_ids": [20, 82, 120],
    },
    {
        "skill_name": "Team Leadership",
        "field": "Customer & People",
        "maps_to": "Leadership",
        "aliases": "team leadership; team management",
        "related_business_ids": [68],
    },
    {
        "skill_name": "Staff Scheduling",
        "field": "Customer & People",
        "maps_to": "Scheduling",
        "aliases": "staff scheduling; shift scheduling",
        "related_business_ids": [3, 102],
    },
    {
        "skill_name": "Lesson Planning",
        "field": "Education & Training",
        "maps_to": "Curriculum",
        "aliases": "lesson planning; lesson plans",
        "related_business_ids": [15, 17, 64, 114],
    },
    {
        "skill_name": "Classroom Management",
        "field": "Education & Training",
        "maps_to": "Teaching",
        "aliases": "classroom management; student management",
        "related_business_ids": [15, 17, 78, 114],
    },
    {
        "skill_name": "Instructional Design",
        "field": "Education & Training",
        "maps_to": "Curriculum",
        "aliases": "instructional design; course design",
        "related_business_ids": [15, 64, 114],
    },
    {
        "skill_name": "Career Coaching",
        "field": "Education & Training",
        "maps_to": "Guidance",
        "aliases": "career coaching; career guidance",
        "related_business_ids": [94],
    },
    {
        "skill_name": "Infection Control",
        "field": "Health & Personal Care",
        "maps_to": "Hygiene",
        "aliases": "infection control; disinfection",
        "related_business_ids": [22, 45, 48, 103],
    },
    {
        "skill_name": "Sanitation",
        "field": "Health & Personal Care",
        "maps_to": "Hygiene",
        "aliases": "sanitation; sanitization",
        "related_business_ids": [36, 45, 48],
    },
    {
        "skill_name": "Personal Grooming",
        "field": "Health & Personal Care",
        "maps_to": "Grooming",
        "aliases": "personal grooming; grooming services",
        "related_business_ids": [103],
    },
    {
        "skill_name": "Pet First Aid",
        "field": "Health & Personal Care",
        "maps_to": "Animal Care",
        "aliases": "pet first aid; animal first aid",
        "related_business_ids": [54],
    },
]


def load_business_frame():
    df = pd.read_csv(Config.FINAL_BUSINESSES_CSV, dtype=str, keep_default_na=False)
    return df


def load_alias_map():
    aliases = {}
    if Config.SKILL_MASTER_CSV.exists():
        df = pd.read_csv(Config.SKILL_MASTER_CSV, dtype=str, keep_default_na=False)
        for _, row in df.iterrows():
            canonical = row.get("skill_name", "").strip()
            if not canonical:
                continue
            aliases[canonical.lower()] = canonical
            for term in re.split(r"[,;|]", row.get("source_terms", "")):
                term = term.strip().lower()
                if term:
                    aliases[term] = canonical

    for alias, target in list(aliases.items()):
        aliases[alias] = canonical_skill(target)
    for old, new in SKILL_SYNONYM_MERGES.items():
        aliases[old.lower()] = canonical_skill(new)
    return aliases


def clean_aliases(skill_name, aliases_text):
    seen = {skill_name.strip().lower()}
    cleaned = []
    for alias in re.split(r"[;,|]", str(aliases_text)):
        alias = alias.strip()
        key = alias.lower()
        if alias and key not in seen:
            seen.add(key)
            cleaned.append(alias)
    return "; ".join(cleaned)


def build_business_skills(businesses, aliases):
    by_id = {}
    names = {}
    for _, row in businesses.iterrows():
        business_id = int(row["id"])
        names[business_id] = row["business_type"].strip()
        skills = set()
        for token in parse_skills_list(row.get("core_skills", "")):
            canonical = aliases.get(token.lower(), token)
            canonical = canonical_skill(canonical)
            if canonical and "," not in canonical:
                skills.add(canonical)
        by_id[business_id] = skills
    return by_id, names


def build_base_rows(business_skills, business_names, alias_map):
    df_skills = pd.read_csv(Config.SKILL_MASTER_CSV, dtype=str, keep_default_na=False)
    alias_sources = defaultdict(set)
    for _, row in df_skills.iterrows():
        canonical = canonical_skill(row.get("skill_name", "").strip())
        for term in re.split(r"[,;|]", row.get("source_terms", "")):
            term = term.strip()
            if term and term.lower() != canonical.lower():
                alias_sources[canonical].add(term)
    for old, new in SKILL_SYNONYM_MERGES.items():
        target = canonical_skill(new)
        if old.lower() != target.lower():
            alias_sources[target].add(old)

    all_skills = {
        skill
        for skills in business_skills.values()
        for skill in skills
        if skill.lower() not in GENERIC_STOP_FRAGMENTS and len(skill) > 2
    }
    rows = []
    for skill in sorted(all_skills, key=str.lower):
        field = next((name for name in FIELD_ORDER if skill in FIELD_SKILLS[name]), OTHER_FIELD)
        related = sorted(business_id for business_id, skills in business_skills.items() if skill in skills)
        rows.append(
            {
                "skill_name": skill,
                "field": field,
                "maps_to": skill,
                "aliases": clean_aliases(skill, "; ".join(sorted(alias_sources.get(skill, set()), key=str.lower))),
                "related_business_ids": ";".join(str(value) for value in related),
                "related_business_types": "; ".join(business_names[value] for value in related),
                "source": "catalog_core_skill",
            }
        )
    return rows


def validate_rows(rows, business_skills, known_aliases=None):
    errors = []
    seen_names = {}
    seen_aliases = {}

    for row in rows:
        name = row["skill_name"]
        name_key = name.lower()
        if name_key in seen_names:
            errors.append(f"duplicate skill name: {name}")
        seen_names[name_key] = name

        if row["field"] not in FIELD_ORDER and row["field"] != OTHER_FIELD:
            errors.append(f"{name}: invalid field {row['field']!r}")

        target = row["maps_to"]
        supported_ids = {business_id for business_id, skills in business_skills.items() if target in skills}
        if not supported_ids:
            errors.append(f"{name}: maps_to {target!r} is not used by any catalog business")

        ids = row["related_business_ids"]
        for business_id in ids:
            if business_id not in business_skills:
                errors.append(f"{name}: unknown business id {business_id}")
            elif target not in business_skills[business_id]:
                errors.append(f"{name}: business {business_id} does not require {target!r}")

        if not ids:
            errors.append(f"{name}: no related businesses")
        if not row.get("aliases") and row["source"] == "curated_extension":
            errors.append(f"{name}: curated option has no aliases")

        for alias in [name, *re.split(r"[;,|]", row.get("aliases", ""))]:
            alias = alias.strip()
            if not alias:
                continue
            alias_key = alias.lower()
            if alias_key in seen_aliases and seen_aliases[alias_key] != name:
                errors.append(f"{name}: alias {alias!r} already used by {seen_aliases[alias_key]}")
            if known_aliases and alias_key in known_aliases and known_aliases[alias_key].lower() != target.lower():
                errors.append(
                    f"{name}: alias {alias!r} conflicts with existing mapping to {known_aliases[alias_key]!r}"
                )
            seen_aliases[alias_key] = name

    if errors:
        raise ValueError("\n".join(errors))


def build_catalog():
    businesses = load_business_frame()
    aliases = load_alias_map()
    business_skills, business_names = build_business_skills(businesses, aliases)
    rows = build_base_rows(business_skills, business_names, aliases)

    existing = {row["skill_name"].lower() for row in rows}
    for extension in CURATED_EXTENSIONS:
        name = extension["skill_name"]
        if name.lower() in existing:
            raise ValueError(f"curated option duplicates an existing skill: {name}")
        rows.append(
            {
                "skill_name": name,
                "field": extension["field"],
                "maps_to": extension["maps_to"],
                "aliases": clean_aliases(name, extension["aliases"]),
                "related_business_ids": ";".join(str(value) for value in extension["related_business_ids"]),
                "related_business_types": "; ".join(business_names[value] for value in extension["related_business_ids"]),
                "source": "curated_extension",
            }
        )
        existing.add(name.lower())

    validate_rows(
        [
            {
                **row,
                "related_business_ids": [
                    int(value)
                    for value in str(row["related_business_ids"]).split(";")
                    if value.strip()
                ],
            }
            for row in rows
        ],
        business_skills,
        aliases,
    )

    order = {field: index for index, field in enumerate([*FIELD_ORDER, OTHER_FIELD])}
    rows.sort(key=lambda row: (order.get(row["field"], len(order)), row["skill_name"].lower()))
    return pd.DataFrame(rows, columns=CATALOG_COLUMNS)


if __name__ == "__main__":
    catalog = build_catalog()
    catalog.to_csv(Config.SKILL_CATALOG_CSV, index=False)
    print("SKILL CATALOG CREATED")
    print("=====================")
    print("ROWS:", len(catalog))
    print("OUTPUT:", Config.SKILL_CATALOG_CSV)
    print()
    print(catalog.groupby("field", sort=False).size().to_string())
