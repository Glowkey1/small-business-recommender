import os
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

REQUIRED_FILES = {
    "final_business_dataset.csv": BASE_DIR / "data" / "final" / "final_business_dataset.csv",
    "final_skill_dataset.csv": BASE_DIR / "data" / "final" / "final_skill_dataset.csv",
    "skill_master.csv": BASE_DIR / "data" / "final" / "skill_master.csv",
    "businesses_with_psa_population.csv": BASE_DIR / "data" / "processed" / "businesses_with_psa_population.csv",
    "municipality_market_features.csv": BASE_DIR / "data" / "processed" / "municipality_market_features.csv",
    "dataset_1_cleaned.csv": BASE_DIR / "data" / "processed" / "dataset_1_cleaned.csv",
}

def validate():
    print("=" * 70)
    print("PHILIPPINE DATASET AUDIT & VALIDATION REPORT")
    print("=" * 70)
    all_ok = True

    for name, path in REQUIRED_FILES.items():
        if not path.exists():
            print(f"❌ MISSING: {name} at {path}")
            all_ok = False
            continue
        try:
            df = pd.read_csv(path)
            rows, cols = df.shape
            print(f"✓ {name:<36} | Rows: {rows:>7,} | Cols: {cols:>2}")
            # Specific domain checks
            if name == "final_business_dataset.csv":
                assert rows >= 119, "Expected at least 119 business ideas"
                assert "min_capital" in df.columns, "Missing min_capital column"
                assert (df["min_capital"] >= 0).all(), "Negative capital values detected"
            elif name == "dataset_1_cleaned.csv":
                assert rows == 250, "Expected 250 records in dataset 1"
                assert "success" in df.columns, "Missing success label"
            elif name == "municipality_market_features.csv":
                assert rows >= 200, "Expected at least 200 municipalities"
        except Exception as e:
            print(f"⚠ ERROR parsing {name}: {e}")
            all_ok = False

    print("=" * 70)
    print(f"Result: {'ALL AUDITED FILES VALID AND PRESENT' if all_ok else 'VALIDATION FAILED - CHECK MISSING FILES'}")
    print("=" * 70)
    return all_ok

if __name__ == "__main__":
    validate()
