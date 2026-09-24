import os
import sys
from pathlib import Path
import pandas as pd
from config import Config, validate_weights

BASE_DIR = Path(__file__).resolve().parent

def validate():
    print("=" * 75)
    print("PHILIPPINE SMALL BUSINESS RECOMMENDER — DATASET & MODEL AUDIT")
    print("=" * 75)
    has_errors = False

    try:
        validate_weights(Config.RECOMMENDATION_WEIGHTS)
        print("✓ Config.RECOMMENDATION_WEIGHTS: Sum equals 1.0.")
    except Exception as e:
        print(f"❌ Config.RECOMMENDATION_WEIGHTS Invalid: {e}")
        has_errors = True

    p_biz = Config.FINAL_BUSINESSES_CSV
    if p_biz.exists():
        df_b = pd.read_csv(p_biz)
        if len(df_b) > 0:
            print(f"✓ final_business_dataset.csv: Business catalog is non-empty ({len(df_b)} ideas present).")
        else:
            print("❌ final_business_dataset.csv: Catalog is empty.")
            has_errors = True

        if df_b["id"].duplicated().any():
            print("❌ Duplicate IDs found in business catalog.")
            has_errors = True
        else:
            print("✓ Business IDs: Unique.")

        invalid_names = (
            (df_b["business_type"].astype(str).str.strip() == "") |
            (df_b["business_type"].astype(str).str.lower() == "nan") |
            (df_b["business_type"].astype(str).str.fullmatch(r"\d+"))
        )
        if invalid_names.any():
            print("❌ Invalid business_type entries found in catalog (blank, 'nan', or all digits).")
            has_errors = True
        else:
            print("✓ Business names: Valid (no blank, 'nan', or numeric names).")

        if (df_b["min_capital"] < 0).any() or not pd.to_numeric(df_b["min_capital"]).notna().all():
            print("❌ Invalid or negative min_capital detected.")
            has_errors = True
        else:
            print(f"✓ Capital bounds: min ₱{df_b['min_capital'].min():,.0f} to max ₱{df_b['min_capital'].max():,.0f}.")
    else:
        print("❌ final_business_dataset.csv missing.")
        has_errors = True

    p_map = Config.CATEGORY_MAP_CSV
    if p_map.exists() and p_biz.exists():
        df_m = pd.read_csv(p_map)
        if len(df_m) == len(df_b):
            print(f"✓ business_market_category_map.csv: Row count matches catalog ({len(df_m)} rows).")
        else:
            print(f"❌ business_market_category_map.csv: Row count ({len(df_m)}) does not match catalog ({len(df_b)}).")
            has_errors = True

        missing_names = set(df_b["business_type"]) - set(df_m["business_type"])
        if missing_names:
            print(f"❌ Businesses missing from category map: {missing_names}")
            has_errors = True
        else:
            print("✓ Category map: Covers every business_type in the catalog.")
    else:
        print("❌ business_market_category_map.csv or catalog missing.")
        has_errors = True

    if Config.FINAL_SKILLS_CSV.exists():
        df_sk = pd.read_csv(Config.FINAL_SKILLS_CSV)
        print(f"✓ final_skill_dataset.csv: {len(df_sk)} raw skills preserved.")
    if Config.SKILL_MASTER_CSV.exists():
        df_sm = pd.read_csv(Config.SKILL_MASTER_CSV)
        print(f"✓ skill_master.csv: {len(df_sm)} standardized skills loaded.")

    if Config.DATASET_1_CLEANED_CSV.exists():
        df_d1 = pd.read_csv(Config.DATASET_1_CLEANED_CSV)
        pos = int((df_d1["success"] == 1).sum())
        neg = int((df_d1["success"] == 0).sum())
        if len(df_d1) == 250 and pos == 62 and neg == 188:
            print("✓ dataset_1_cleaned.csv: Exactly 250 records (62 Successful / 188 Non-Successful).")
        else:
            print(f"❌ dataset_1_cleaned.csv: Distribution mismatch ({pos} / {neg}).")
            has_errors = True

    if Config.MUNICIPALITY_MARKET_CSV.exists():
        df_mun = pd.read_csv(Config.MUNICIPALITY_MARKET_CSV)
        print(f"✓ municipality_market_features.csv: {len(df_mun)} municipalities loaded.")
        if df_mun["adm3_psgc"].duplicated().any():
            print("❌ Duplicate adm3_psgc codes detected in municipalities file.")
            has_errors = True
        dup_names = df_mun[df_mun["municipality_city"].duplicated(keep=False)]["municipality_city"].unique()
        print(f"  [Report] Duplicate municipality names across provinces (resolved via PSGC): {list(dup_names)}")
        missing_pop = df_mun[df_mun["population_2024"].isna()]["municipality_city"].tolist()
        print(f"  [Report] Cities with missing 2024 PSA population (handled safely): {missing_pop}")

    if Config.SUCCESS_MODEL_JOBLIB.exists():
        print("✓ models/success_model.joblib: Production model file exists.")
    else:
        print("❌ models/success_model.joblib missing. Run train_success_models.py.")
        has_errors = True

    if Config.SUCCESS_METRICS_JSON.exists():
        print("✓ models/model_metrics.json: Evaluation metrics file exists.")
    else:
        print("❌ models/model_metrics.json missing.")
        has_errors = True

    print("=" * 75)
    if has_errors:
        print("RESULT: VALIDATION FAILED WITH ERRORS.")
        sys.exit(1)
    else:
        print("RESULT: ALL VALIDATION CHECKS PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    validate()
