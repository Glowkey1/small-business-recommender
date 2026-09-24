import os
import re
import glob
import logging
import pandas as pd
import numpy as np
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

RAW_D1_DIR = Config.RAW_D1_PATH
RAW_D2_DIR = Config.RAW_D2_PATH
PROCESSED_DIR = Config.PROCESSED_PATH
FINAL_DIR = Config.FINAL_PATH

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

old_attr_file = os.path.join(RAW_D2_DIR, "business_attributes.csv")
if os.path.exists(old_attr_file):
    os.remove(old_attr_file)

def standardize_cols(df):
    df.columns = [re.sub(r"[^\w\s]", "", c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def parse_cost(val):
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace(",", "")
    nums = re.findall(r"\d+(?:\.\d+)?", val_str)
    return float(nums[0]) if nums else 0.0

def parse_people_needed(text):
    if pd.isna(text) or text is None:
        return None
    cleaned = str(text).strip().lower()

    if "solo" in cleaned or cleaned in {"1", "single", "individual"}:
        return (1, 1)

    m_range = re.search(r"(\d+)\s*[-–—to]+\s*(\d+)", cleaned)
    if m_range:
        return (int(m_range.group(1)), int(m_range.group(2)))

    m_plus = re.search(r"(\d+)\s*\+", cleaned)
    if m_plus:
        n = int(m_plus.group(1))
        return (n, int(n * 2))

    m_single = re.search(r"\b(\d+)\b", cleaned)
    if m_single:
        n = int(m_single.group(1))
        return (n, n)

    return None

def capital_tier(min_people, max_people):
    avg = (min_people + max_people) / 2.0
    if avg <= 1:
        return 5000.0, "₱5,000 - ₱15,000", "Online / Home-Based"
    if avg <= 3:
        return 15000.0, "₱15,000 - ₱30,000", "Home-Based"
    if avg <= 6:
        return 35000.0, "₱35,000 - ₱60,000", "Physical Store"
    if avg <= 12:
        return 75000.0, "₱75,000 - ₱120,000", "Physical Store"
    return 150000.0, "₱150,000 - ₱250,000+", "Physical Store / Commercial"

EXPERIENCED_KEYWORDS = [
    "certified", "certification", "license", "licensed", "regulatory", "compliance",
    "consultancy", "consultant", "architect", "engineering", "legal", "clinical",
    "manufacturing", "factory", "plant", "heavy equipment", "specialized"
]

INTERMEDIATE_KEYWORDS = [
    "studio", "agency", "commercial kitchen", "technician", "commercial equipment",
    "workshop", "inventory management", "staff management", "portfolio", "permits",
    "machinery", "professional", "advanced", "specialist", "salon", "kitchen space"
]

def derive_experience_level(reqs_text):
    if pd.isna(reqs_text) or not reqs_text:
        return "Beginner", True

    text = str(reqs_text).lower()
    for kw in EXPERIENCED_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text):
            return "Experienced", False

    for kw in INTERMEDIATE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text):
            return "Intermediate", False

    return "Beginner", True

PHYSICAL_STORE_KEYWORDS = [
    "shop", "store", "kitchen", "space", "warehouse", "facility", "outlet",
    "salon", "restaurant", "center", "centre", "clinic", "counter", "premises"
]

SERVICE_MOBILE_KEYWORDS = [
    "vehicle", "transport", "van", "truck", "motorcycle", "bike", "on-site",
    "mobile", "cleaning equipment", "field", "visiting", "tools bag"
]

ONLINE_HOME_KEYWORDS = [
    "laptop", "internet", "computer", "phone", "smartphone", "desk", "wifi",
    "software", "pc", "online", "digital", "camera"
]

def derive_business_setup(reqs_text, baseline_setup):
    if pd.isna(reqs_text) or not reqs_text:
        return baseline_setup, True

    text = str(reqs_text).lower()
    has_physical = any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in PHYSICAL_STORE_KEYWORDS)
    has_mobile = any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in SERVICE_MOBILE_KEYWORDS)
    has_online = any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in ONLINE_HOME_KEYWORDS)

    if has_physical:
        return "Physical Store", False
    if has_mobile:
        return "Service / Mobile", False
    if has_online:
        return "Online / Home-Based", False

    return baseline_setup, True

def process_dataset_1():
    files = glob.glob(os.path.join(RAW_D1_DIR, "*.csv"))
    if not files:
        logging.warning("No CSV found in dataset_1 raw folder.")
        return None

    df = pd.read_csv(files[0])
    df = standardize_cols(df).drop_duplicates().reset_index(drop=True)

    success_col = next((c for c in df.columns if "success" in c), None)
    if success_col:
        df[success_col] = df[success_col].astype(str).str.lower().map({
            "yes": 1, "no": 0, "1": 1, "0": 0, "true": 1, "false": 0, "successful": 1
        }).fillna(0).astype(int)

    cap_col = next((c for c in df.columns if "capital" in c), None)
    if cap_col:
        df[cap_col] = df[cap_col].apply(parse_cost)

    out = os.path.join(PROCESSED_DIR, "dataset_1_cleaned.csv")
    df.to_csv(out, index=False)
    logging.info(f"Dataset 1 cleaned ({len(df)} rows). Saved to {out}")
    return df

def process_dataset_2():
    def _find_business_files():
        def _scan(directory):
            if not directory or not os.path.exists(directory):
                return []
            pattern = os.path.join(directory, "*.csv")
            return sorted(
                [
                    f for f in glob.glob(pattern)
                    if "business" in os.path.basename(f).lower()
                    and "attribute" not in os.path.basename(f).lower()
                ],
                key=lambda x: os.path.basename(x).lower()
            )

        # 1. Search RAW_D2_DIR first
        files = _scan(RAW_D2_DIR)
        if files:
            return files

        # 2. Fallback to data/backup
        data_dir = getattr(Config, "DATA_DIR", os.path.abspath(os.path.join(str(RAW_D2_DIR), "..", "..")))
        backup_dir = os.path.join(str(data_dir), "backup")
        return _scan(backup_dir)

    biz_files = _find_business_files()
    if not biz_files:
        logging.error("No valid business CSV files found in dataset_2 or backup directories.")
        return None, None

    dfs = [standardize_cols(pd.read_csv(f)) for f in biz_files]
    merged = pd.concat(dfs, ignore_index=True)

    name_col = next((c for c in merged.columns if "type" in c or "name" in c or c == "business"), None)
    if name_col is None:
        logging.error("No valid business name/type column found in the business files. Aborting.")
        return None, None

    merged = merged.drop_duplicates(subset=[name_col]).reset_index(drop=True)

    col_map = {}
    for c in merged.columns:
        if "skill" in c: col_map[c] = "core_skills"
        elif "requirement" in c: col_map[c] = "minimum_requirements"
        elif "strateg" in c: col_map[c] = "strategies"
        elif "risk" in c: col_map[c] = "risks"
        elif "people" in c: col_map[c] = "people_needed"
        elif "category" in c: col_map[c] = "category"

    merged = merged.rename(columns=col_map)
    merged["business_type"] = merged[name_col].astype(str).str.strip()

    invalid_mask = (
        (merged["business_type"] == "") |
        (merged["business_type"].str.lower() == "nan") |
        merged["business_type"].str.fullmatch(r"\d+")
    )
    if invalid_mask.any():
        bad_sample = merged.loc[invalid_mask, "business_type"].iloc[0]
        logging.error(f"Invalid business_type values found ('{bad_sample}'). Aborting to protect existing catalog.")
        return None, None

    if "id" in merged.columns:
        merged = merged.drop(columns=["id"])
    merged.insert(0, "id", range(1, len(merged) + 1))

    unparseable_people_count = 0
    exp_default_count = 0
    setup_default_count = 0

    min_caps = []
    startup_costs = []
    setups = []
    exp_levels = []

    for _, row in merged.iterrows():
        p_raw = row.get("people_needed", "")
        reqs_raw = row.get("minimum_requirements", "")

        headcount = parse_people_needed(p_raw)
        if headcount is None:
            unparseable_people_count += 1
            min_p, max_p = (1, 2)
        else:
            min_p, max_p = headcount

        tier_cap, tier_cost_str, baseline_setup = capital_tier(min_p, max_p)
        exp_lvl, exp_is_default = derive_experience_level(reqs_raw)
        if exp_is_default:
            exp_default_count += 1

        setup, setup_is_default = derive_business_setup(reqs_raw, baseline_setup)
        if setup_is_default:
            setup_default_count += 1

        min_caps.append(tier_cap)
        startup_costs.append(tier_cost_str)
        setups.append(setup)
        exp_levels.append(exp_lvl)

    merged["min_capital"] = min_caps
    merged["startup_cost"] = startup_costs
    merged["business_setup"] = setups
    merged["experience_level"] = exp_levels

    if "category" not in merged.columns:
        merged["category"] = "General"
    else:
        merged["category"] = merged["category"].fillna("General")

    for col, default_val in [
        ("core_skills", ""),
        ("minimum_requirements", "Basic workspace and standard equipment."),
        ("strategies", "Focus on customer satisfaction and cash flow control."),
        ("risks", "Competition and operational delays.")
    ]:
        if col not in merged.columns:
            merged[col] = default_val
        else:
            merged[col] = merged[col].fillna(default_val)

    final_biz_path = os.path.join(FINAL_DIR, "final_business_dataset.csv")
    merged.to_csv(final_biz_path, index=False)
    logging.info(f"Final Business Catalog saved to {final_biz_path}")

    skill_set = set()
    for raw_s in merged["core_skills"].dropna():
        for token in re.split(r"[,;\n|•/\s]+", str(raw_s)):
            c = re.sub(r"[^\w-]", "", token).strip().title()
            if len(c) > 1 and not c.isdigit():
                skill_set.add(c)

    skills_df = pd.DataFrame({"skill_name": sorted(list(skill_set))})
    skill_out = os.path.join(FINAL_DIR, "final_skill_dataset.csv")
    skills_df.to_csv(skill_out, index=False)
    logging.info(f"Final Skill Dataset saved ({len(skills_df)} skills).")

    return merged, skills_df

if __name__ == "__main__":
    print("Starting preprocessing...")
    process_dataset_1()
    df, _ = process_dataset_2()
    if df is not None:
        print("\n" + "=" * 60)
        print(f"RESULTING CATALOG DISTRIBUTIONS (N={len(df)})")
        print("=" * 60)
        print("\n--- min_capital value_counts ---")
        print(df['min_capital'].value_counts())
        print("\n--- business_setup value_counts ---")
        print(df['business_setup'].value_counts())
        print("\n--- experience_level value_counts ---")
        print(df['experience_level'].value_counts())
        print("=" * 60)
    else:
        print("❌ process_dataset_2() returned None.")