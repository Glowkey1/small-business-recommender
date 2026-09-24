import os
import sys
from pathlib import Path
import pandas as pd
from config import Config, validate_weights

BASE_DIR = Path(__file__).resolve().parent

def validate():
    print("=" * 75)
    print("CALABARZON SMALL BUSINESS RECOMMENDER — AUDIT")
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
        print(f"✓ final_business_dataset.csv: {len(df_b)} business models in catalog.")
    else:
        print("❌ final_business_dataset.csv missing.")
        has_errors = True

    p_cal = Config.DATA_DIR / "processed" / "calabarzon_market_features.csv"
    if p_cal.exists():
        df_c = pd.read_csv(p_cal)
        print(f"✓ calabarzon_market_features.csv: {len(df_c)} CALABARZON municipalities loaded.")
        missing_pop = df_c[df_c["population_2024"].isna()]["municipality_city"].tolist()
        print(f"  [Report] Unlisted 2024 PSA population handled safely: {missing_pop}")
    else:
        print("❌ calabarzon_market_features.csv missing.")
        has_errors = True

    print("=" * 75)
    if has_errors:
        print("RESULT: AUDIT FAILED.")
        sys.exit(1)
    else:
        print("RESULT: CALABARZON DATASET VERIFICATION PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    validate()
