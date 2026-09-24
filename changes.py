# lock_calabarzon_only.py
"""
Locks the Small Business Recommender exclusively to CALABARZON (Region IV-A):
1. Builds data/processed/calabarzon_market_features.csv from calabarzon_businesses_standardized.csv.
2. Restricts psgc_region_province_names.csv to Region IV-A and its 5 provinces + Lucena City.
3. Locks ml/market_analyzer.py to the CALABARZON market features dataset.
4. Updates tests in tests/test_hybrid_recommender.py to test Lipa City and Lucena City.
5. Updates tests/test_validation.py to use a CALABARZON location PSGC.
6. Updates validate_datasets.py to audit the CALABARZON dataset.
"""

import os
import re
import logging
from pathlib import Path
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
FINAL_DIR = DATA_DIR / "final"

print("=" * 80)
print("LOCKING SYSTEM EXCLUSIVELY TO REGION IV-A (CALABARZON)")
print("=" * 80)

# ----------------------------------------------------------------------
# 1. Locate calabarzon_businesses_standardized.csv
# ----------------------------------------------------------------------
def find_raw_calabarzon():
    candidates = [
        PROCESSED_DIR / "calabarzon_businesses_standardized.csv",
        DATA_DIR / "raw" / "calabarzon_businesses_standardized.csv",
        DATA_DIR / "raw" / "dataset_2" / "calabarzon_businesses_standardized.csv",
        DATA_DIR / "calabarzon_businesses_standardized.csv",
        ROOT / "calabarzon_businesses_standardized.csv"
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

raw_file = find_raw_calabarzon()
if not raw_file:
    print("❌ calabarzon_businesses_standardized.csv not found in data/processed or data/raw.")
    print("   Please place calabarzon_businesses_standardized.csv in data/processed/ and run again.")
    exit(1)

print(f"✓ Using source data: {raw_file}")

# ----------------------------------------------------------------------
# 2. Build calabarzon_market_features.csv with standard and alias columns
# ----------------------------------------------------------------------
df_raw = pd.read_csv(raw_file, low_memory=False)

# Normalization of PSGC fields
for c in ["municipality_psgc", "province_psgc", "region_psgc", "adm3_psgc"]:
    if c in df_raw.columns:
        df_raw[c] = df_raw[c].apply(lambda x: f"{int(float(x)):010d}" if pd.notna(x) and str(x).strip() != "" else "")

# Category mapping
TAG_MAP = {
    "restaurant": "Food", "fast_food": "Food", "cafe": "Food", "bakery": "Food",
    "canteen": "Food", "food_court": "Food", "ice_cream": "Food", "bar": "Food",
    "pub": "Food", "coffee_shop": "Food", "confectionery": "Food", "catering": "Food",
    "convenience": "Retail", "supermarket": "Retail", "hardware": "Retail",
    "clothes": "Retail", "department_store": "Retail", "mall": "Retail",
    "general": "Retail", "variety_store": "Retail", "chemist": "Retail",
    "beverage": "Retail", "butcher": "Retail", "kiosk": "Retail", "seafood": "Retail",
    "shoes": "Retail", "stationery": "Retail",
    "laundry": "Personal Services", "hairdresser": "Personal Services", "beauty": "Personal Services",
    "spa": "Personal Services", "tailor": "Personal Services", "dry_cleaning": "Personal Services",
    "massage": "Personal Services", "barber": "Personal Services", "optician": "Personal Services",
    "car_repair": "Automotive", "motorcycle_repair": "Automotive", "car_wash": "Automotive",
    "tyres": "Automotive", "fuel": "Automotive", "charging_station": "Automotive",
    "parts": "Automotive", "car_rental": "Automotive",
    "school": "Education", "kindergarten": "Education", "college": "Education",
    "university": "Education", "driving_school": "Education", "tuition": "Education",
    "pharmacy": "Healthcare", "clinic": "Healthcare", "hospital": "Healthcare",
    "dentist": "Healthcare", "doctors": "Healthcare", "veterinary": "Healthcare",
    "mobile_phone": "Technology", "electronics": "Technology", "copyshop": "Technology",
    "internet_cafe": "Technology", "computer": "Technology", "telecommunication": "Technology",
    "bank": "Professional Services", "atm": "Professional Services", "accountant": "Professional Services",
    "lawyer": "Professional Services", "insurance": "Professional Services", "consulting": "Professional Services",
    "hotel": "Accommodation", "motel": "Accommodation", "guest_house": "Accommodation", "hostel": "Accommodation",
    "resort": "Tourism", "attraction": "Tourism", "theme_park": "Tourism", "museum": "Tourism"
}

def get_cat(row):
    for col in ["amenity", "shop", "tourism", "craft", "office", "category"]:
        if col in row and pd.notna(row[col]):
            val = str(row[col]).lower().strip().replace(" ", "_")
            if val in TAG_MAP:
                return TAG_MAP[val]
    return "Unmapped"

df_raw["market_category"] = df_raw.apply(get_cat, axis=1)
mun_col = "municipality_city" if "municipality_city" in df_raw.columns else "municipality"
df_raw["mun_clean"] = df_raw[mun_col].astype(str).str.strip()

# Load 2024 PSA populations if available
pop_lookup = {}
nat_file = PROCESSED_DIR / "municipality_market_features.csv"
if nat_file.exists():
    df_nat = pd.read_csv(nat_file)
    for _, r in df_nat.iterrows():
        m_name = str(r.get("municipality_city", "")).strip().lower()
        pop = r.get("population_2024")
        if pd.notna(pop) and float(pop) > 0:
            pop_lookup[m_name] = float(pop)

rows = []
for mun_name, grp in df_raw.groupby("mun_clean"):
    if mun_name.lower() in ["nan", "unknown", ""]:
        continue

    p_code = grp["province_psgc"].iloc[0] if "province_psgc" in grp.columns else "0401000000"
    m_code = grp["municipality_psgc"].iloc[0] if "municipality_psgc" in grp.columns else (grp["adm3_psgc"].iloc[0] if "adm3_psgc" in grp.columns else "")

    total_cnt = len(grp)
    pop_val = pop_lookup.get(mun_name.lower(), np.nan)
    has_pop = pd.notna(pop_val) and pop_val > 0

    if total_cnt >= 250 and has_pop:
        dq = "HIGH"
    elif total_cnt >= 75 and has_pop:
        dq = "MEDIUM"
    elif total_cnt >= 25:
        dq = "LOW"
    else:
        dq = "INSUFFICIENT"

    counts = grp["market_category"].value_counts().to_dict()

    def c_stat(cat_name):
        c = int(counts.get(cat_name, 0))
        r = round((c / pop_val) * 1000, 3) if has_pop else np.nan
        return c, r

    food_c, food_r = c_stat("Food")
    ret_c, ret_r = c_stat("Retail")
    serv_c, serv_r = c_stat("Personal Services")
    edu_c, edu_r = c_stat("Education")
    tour_c, tour_r = c_stat("Tourism")
    tech_c, tech_r = c_stat("Technology")
    auto_c, auto_r = c_stat("Automotive")
    acc_c, acc_r = c_stat("Accommodation")

    rows.append({
        # Standard schema columns
        "region": "CALABARZON (Region IV-A)",
        "region_psgc": "0400000000",
        "province": p_code,
        "province_psgc": p_code,
        "municipality": mun_name,
        "municipality_city": mun_name,
        "municipality_psgc": m_code,
        "adm3_psgc": m_code,
        "population": int(pop_val) if has_pop else np.nan,
        "population_2024": float(pop_val) if has_pop else np.nan,
        "total_businesses": total_cnt,
        "total_osm_records": total_cnt,
        # Category counts (both naming styles supported)
        "food_count": food_c,
        "businesses_food": food_c,
        "food_per_1000": food_r,
        "businesses_food_per_1000_people": food_r,
        "retail_count": ret_c,
        "businesses_retail": ret_c,
        "retail_per_1000": ret_r,
        "businesses_retail_per_1000_people": ret_r,
        "services_count": serv_c,
        "businesses_personal_services": serv_c,
        "services_per_1000": serv_r,
        "businesses_personal_services_per_1000_people": serv_r,
        "education_count": edu_c,
        "businesses_education": edu_c,
        "education_per_1000": edu_r,
        "businesses_education_per_1000_people": edu_r,
        "tourism_count": tour_c,
        "businesses_tourism": tour_c,
        "tourism_per_1000": tour_r,
        "businesses_tourism_per_1000_people": tour_r,
        "technology_count": tech_c,
        "businesses_technology": tech_c,
        "technology_per_1000": tech_r,
        "businesses_technology_per_1000_people": tech_r,
        "automotive_count": auto_c,
        "businesses_automotive": auto_c,
        "automotive_per_1000": auto_r,
        "businesses_automotive_per_1000_people": auto_r,
        "accommodation_count": acc_c,
        "businesses_accommodation": acc_c,
        "accommodation_per_1000": acc_r,
        "businesses_accommodation_per_1000_people": acc_r,
        "data_quality": dq
    })

df_cal_features = pd.DataFrame(rows).sort_values("total_businesses", ascending=False)
cal_features_path = PROCESSED_DIR / "calabarzon_market_features.csv"
df_cal_features.to_csv(cal_features_path, index=False)
print(f"✓ Generated calabarzon_market_features.csv ({len(df_cal_features)} CALABARZON municipalities)")

# ----------------------------------------------------------------------
# 3. Restrict psgc_region_province_names.csv strictly to CALABARZON
# ----------------------------------------------------------------------
psgc_calabarzon_csv = """level,psgc_code,name,region_psgc,note
region,0400000000,CALABARZON (Region IV-A),,official
province,0401000000,Batangas,0400000000,official
province,0402100000,Cavite,0400000000,official
province,0403400000,Laguna,0400000000,official
province,0405600000,Quezon,0400000000,official
province,0405800000,Rizal,0400000000,official
province,0431200000,Lucena City,0400000000,independent
"""
(PROCESSED_DIR / "psgc_region_province_names.csv").write_text(psgc_calabarzon_csv.strip() + "\n", encoding="utf-8")
print("✓ Restricted psgc_region_province_names.csv to Region IV-A provinces")

# ----------------------------------------------------------------------
# 4. Lock ml/market_analyzer.py strictly to calabarzon_market_features.csv
# ----------------------------------------------------------------------
analyzer_code = r'''import re
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)

VALID_MARKET_CATEGORIES = [
    "Food", "Retail", "Education", "Financial Services", "Healthcare",
    "Automotive", "Personal Services", "Technology", "Professional Services",
    "Accommodation", "Tourism", "Skilled Trades"
]

def format_city_display_name(raw_name: str) -> str:
    s = str(raw_name).strip()
    if s.lower().startswith("city of "):
        return f"{s[8:].strip()} City"
    return s

class PhilippineMarketAnalyzer:
    def __init__(self, market_features_path: Path = None, category_map_path: Path = None, psgc_names_path: Path = None):
        # Exclusively lock to the CALABARZON market features file
        self.market_features_path = Config.DATA_DIR / "processed" / "calabarzon_market_features.csv"
        self.category_map_path = category_map_path or Config.CATEGORY_MAP_CSV
        self.psgc_names_path = psgc_names_path or Config.PSGC_NAMES_CSV

        self.df_market = pd.DataFrame()
        self.category_map = {}
        self.region_names = {}
        self.province_names = {}
        self.density_cutoffs = {}

        self._load_metadata()
        self._load_market_data()

    def _load_metadata(self):
        if self.category_map_path.exists():
            try:
                df_map = pd.read_csv(self.category_map_path)
                for _, r in df_map.iterrows():
                    b_type = str(r["business_type"]).strip()
                    m_cat = str(r["market_category"]).strip() if pd.notna(r["market_category"]) else ""
                    self.category_map[b_type.lower()] = m_cat if m_cat else None
            except Exception as e:
                logger.error(f"Error loading category map: {e}")

        if self.psgc_names_path.exists():
            try:
                df_p = pd.read_csv(self.psgc_names_path, dtype={"psgc_code": str, "region_psgc": str})
                for _, r in df_p.iterrows():
                    code = str(r["psgc_code"]).strip().zfill(10)
                    lvl = str(r["level"]).strip().lower()
                    name = str(r["name"]).strip()
                    if lvl == "region":
                        self.region_names[code] = name
                    elif lvl == "province":
                        self.province_names[code] = name
            except Exception as e:
                logger.error(f"Error loading PSGC names: {e}")

    def _load_market_data(self):
        if not self.market_features_path.exists():
            logger.error(f"Missing {self.market_features_path}")
            return
        try:
            df = pd.read_csv(self.market_features_path)

            for c in ["adm3_psgc", "province_psgc", "region_psgc", "municipality_psgc"]:
                if c in df.columns:
                    df[c] = df[c].apply(lambda x: f"{int(float(x)):010d}" if pd.notna(x) and str(x).strip() != "" else "")

            if "adm3_psgc" not in df.columns and "municipality_psgc" in df.columns:
                df["adm3_psgc"] = df["municipality_psgc"]
            if "municipality_city" not in df.columns and "municipality" in df.columns:
                df["municipality_city"] = df["municipality"]
            if "total_osm_records" not in df.columns and "total_businesses" in df.columns:
                df["total_osm_records"] = df["total_businesses"]
            if "population_2024" not in df.columns and "population" in df.columns:
                df["population_2024"] = df["population"]

            df["display_city"] = df["municipality_city"].apply(format_city_display_name)
            self.df_market = df

            qualifying = df[
                (df.get("total_osm_records", 0) >= 25) &
                (df["population_2024"].notna()) &
                (df["population_2024"] > 0)
            ]

            for cat in VALID_MARKET_CATEGORIES:
                col = f"businesses_{cat.lower().replace(' ', '_')}_per_1000_people"
                alt_col = f"{cat.lower().replace(' ', '_')}_per_1000"
                active_col = col if col in qualifying.columns else (alt_col if alt_col in qualifying.columns else None)
                if active_col and active_col in qualifying.columns:
                    series = qualifying[active_col].dropna()
                    if len(series) > 0:
                        self.density_cutoffs[cat] = {
                            "p25": float(series.quantile(0.25)),
                            "p75": float(series.quantile(0.75)),
                            "p90": float(series.quantile(0.90))
                        }
            logger.info(f"Loaded {len(self.df_market)} CALABARZON municipality records.")
        except Exception as e:
            logger.error(f"Failed to load market data: {e}")

    def get_market_category(self, business_type: str) -> str:
        return self.category_map.get(str(business_type).strip().lower(), None)

    def get_location_hierarchy(self) -> dict:
        regions_out = []
        flat_labels = []
        if self.df_market.empty or "region_psgc" not in self.df_market.columns:
            return {"regions": [], "locations": []}

        for r_code, r_group in self.df_market.groupby("region_psgc"):
            r_name = self.region_names.get(r_code, "CALABARZON (Region IV-A)")
            prov_list = []
            for p_code, p_group in r_group.groupby("province_psgc"):
                p_name = self.province_names.get(p_code, f"Province {p_code}")
                city_list = []
                for _, row in p_group.sort_values("display_city").iterrows():
                    psgc = row["adm3_psgc"]
                    c_name = row["display_city"]
                    total_osm = int(row.get("total_osm_records", 0)) if pd.notna(row.get("total_osm_records")) else 0
                    city_list.append({"code": psgc, "name": c_name, "total_osm": total_osm})
                    flat_labels.append(f"{c_name}, {p_name} ({psgc})")
                prov_list.append({"code": p_code, "name": p_name, "cities": city_list})
            regions_out.append({"code": r_code, "name": r_name, "provinces": prov_list})

        regions_out.sort(key=lambda x: x["name"])
        return {"regions": regions_out, "locations": sorted(flat_labels)}

    def analyze_location_market(self, psgc_code: str, business_type: str) -> dict:
        cat = self.get_market_category(business_type)
        if cat is None or cat not in VALID_MARKET_CATEGORIES:
            return {
                "location_score": None,
                "evidence_text": "Location market analysis omitted for location-independent or unmapped business category.",
                "osm_count": None,
                "total_osm": None,
                "population": None,
                "density_per_1000": None,
                "category": None,
                "data_quality": "N/A"
            }

        if self.df_market.empty or not psgc_code:
            return {
                "location_score": None,
                "evidence_text": "Location not specified. Location market score omitted.",
                "osm_count": None,
                "total_osm": None,
                "population": None,
                "density_per_1000": None,
                "category": cat,
                "data_quality": "INSUFFICIENT"
            }

        clean_psgc = str(psgc_code).strip().zfill(10)
        match = self.df_market[self.df_market["adm3_psgc"] == clean_psgc]

        if match.empty:
            match = self.df_market[self.df_market["display_city"].str.lower() == str(psgc_code).strip().lower()]

        if match.empty:
            return {
                "location_score": None,
                "evidence_text": f"Location PSGC {clean_psgc} not found in CALABARZON database.",
                "osm_count": None,
                "total_osm": None,
                "population": None,
                "density_per_1000": None,
                "category": cat,
                "data_quality": "INSUFFICIENT"
            }

        row = match.iloc[0]
        city_name = row["display_city"]
        prov_code = row.get("province_psgc", "")
        prov_name = self.province_names.get(prov_code, "CALABARZON")
        total_osm = int(row.get("total_osm_records", 0))
        data_quality = str(row.get("data_quality", "LOW"))

        cat_key = cat.lower().replace(" ", "_")
        count_col = f"businesses_{cat_key}" if f"businesses_{cat_key}" in row else f"{cat_key}_count"
        rate_col = f"businesses_{cat_key}_per_1000_people" if f"businesses_{cat_key}_per_1000_people" in row else f"{cat_key}_per_1000"

        osm_count = int(row[count_col]) if count_col in row and pd.notna(row[count_col]) else 0
        density = float(row[rate_col]) if rate_col in row and pd.notna(row[rate_col]) else 0.0

        pop_val = row.get("population_2024")
        has_pop = pd.notna(pop_val) and float(pop_val) > 0
        pop_num = float(pop_val) if has_pop else None

        tiers = Config.LOCATION_SCORES
        cutoffs = self.density_cutoffs.get(cat, {"p25": 0.05, "p75": 0.35, "p90": 0.70})

        # Missing population safe handling (e.g. Lucena City)
        if not has_pop:
            score = tiers["missing_pop_high"] if osm_count >= 5 else (tiers["missing_pop_low"] if osm_count >= 1 else tiers["zero"])
            evidence = (
                f"Mapped businesses in the available OpenStreetMap data: {osm_count} {cat} businesses in "
                f"{city_name}, {prov_name}. Population data unavailable for this market calculation."
            )
            return {
                "location_score": score,
                "evidence_text": evidence,
                "osm_count": osm_count,
                "total_osm": total_osm,
                "population": None,
                "density_per_1000": None,
                "category": cat,
                "data_quality": "LOW"
            }

        # Limited OSM data check (< 25 records)
        if total_osm < 25:
            return {
                "location_score": None,
                "evidence_text": "Very limited mapped data in the available OpenStreetMap data for this municipality.",
                "osm_count": osm_count,
                "total_osm": total_osm,
                "population": pop_num,
                "density_per_1000": None,
                "category": cat,
                "data_quality": "INSUFFICIENT"
            }

        if osm_count == 0:
            score = tiers["zero"]
        elif density < cutoffs["p25"]:
            score = tiers["low"]
        elif density < cutoffs["p75"]:
            score = tiers["mid"]
        elif density < cutoffs["p90"]:
            score = tiers["high"]
        else:
            score = tiers["very_high"]

        evidence = (
            f"Mapped businesses in the available OpenStreetMap data: {osm_count} {cat} businesses in "
            f"{city_name}, {prov_name} ({density:.2f} per 1,000 residents, 2024 PSA)."
        )

        return {
            "location_score": score,
            "evidence_text": evidence,
            "osm_count": osm_count,
            "total_osm": total_osm,
            "population": pop_num,
            "density_per_1000": density,
            "category": cat,
            "data_quality": data_quality
        }
'''
(ROOT / "ml" / "market_analyzer.py").write_text(analyzer_code.strip() + "\n", encoding="utf-8")
print("✓ Locked ml/market_analyzer.py strictly to CALABARZON")

# ----------------------------------------------------------------------
# 5. Update tests/test_hybrid_recommender.py to test CALABARZON (Lipa & Lucena)
# ----------------------------------------------------------------------
test_calabarzon_code = r'''import pytest
import pandas as pd
from ml.recommendation_engine import HybridBusinessRecommender
from config import Config

@pytest.fixture(scope="module")
def engine():
    return HybridBusinessRecommender()

def test_calabarzon_location_market_evidence(engine):
    """Test CALABARZON market evidence using Lipa City, Batangas."""
    lipa = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Lipa", case=False)
    ].iloc[0]
    res = engine.market_analyzer.analyze_location_market(lipa["adm3_psgc"], "Bakery")
    assert res["osm_count"] > 0
    assert res["category"] == "Food"
    assert res["location_score"] in [0.75, 0.85, 0.90]
    assert "Lipa City" in res["evidence_text"] or "Lipa" in res["evidence_text"]

def test_lucena_city_missing_population_safe_handling(engine):
    """Test CALABARZON HUC with unlisted PSA population (Lucena City)."""
    lucena = engine.market_analyzer.df_market[
        engine.market_analyzer.df_market["municipality_city"].astype(str).str.contains("Lucena", case=False)
    ].iloc[0]
    res = engine.market_analyzer.analyze_location_market(lucena["adm3_psgc"], "Restaurant")
    assert res["population"] is None
    assert "Population data unavailable for this market calculation." in res["evidence_text"]
    assert res["location_score"] is not None

def test_hard_capital_filter_boundaries(engine):
    """Capital scoring test: recommend with capital=1000 returns 5 results with budget_gap and affordable."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend({"capital": 1000, "skills": [], "location": lipa["adm3_psgc"]}, top_n=5)
    assert len(recs) == 5, f"Expected 5 results, got {len(recs)}"
    for r in recs:
        assert "budget_gap" in r
        assert "affordable" in r
        assert r["affordable"] == (r["min_capital"] <= 1000)
        assert r["budget_gap"] == max(0.0, r["min_capital"] - 1000)

def test_omitted_location_for_online_business(engine):
    """Location is omitted for online/unmapped businesses (score is None)."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    loc_res = engine.market_analyzer.analyze_location_market(lipa["adm3_psgc"], "Freelancing")
    assert loc_res["location_score"] is None
    assert "omitted" in loc_res["evidence_text"].lower()

def test_empty_skills_omitted_from_scoring(engine):
    """Empty skills leaves skills component out of the score (None) and renormalizes weights."""
    recs = engine.recommend({"capital": 20000, "skills": []}, top_n=5)
    assert len(recs) > 0
    assert any("No skills selected" in r["reasons"] for r in recs)
    assert recs[0]["component_scores"]["skills"] is None

def test_score_range_and_deterministic_sort(engine):
    """Recommendation scores strictly 0-100% and deterministically sorted."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    recs = engine.recommend({"capital": 50000, "skills": ["Marketing"], "location": lipa["adm3_psgc"]}, top_n=5)
    for i in range(len(recs) - 1):
        assert recs[i]["raw_final_score"] >= recs[i+1]["raw_final_score"]
        assert 0.0 <= recs[i]["recommendation_score"] <= 100.0

def test_no_numeric_or_blank_business_type():
    """Verify that no business_type in catalog is blank, 'nan', or all digits."""
    df = pd.read_csv(Config.FINAL_BUSINESSES_CSV)
    assert not df.empty, "Catalog should not be empty"
    for b_type in df["business_type"]:
        s = str(b_type).strip()
        assert s != "", "business_type should not be blank"
        assert s.lower() != "nan", "business_type should not be 'nan'"
        assert not s.isdigit(), f"business_type should not be numeric digits, got '{s}'"

def test_recommendation_weights_sum_to_one():
    """Verify that Config.RECOMMENDATION_WEIGHTS sums exactly to 1.0."""
    total = sum(Config.RECOMMENDATION_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6, f"Weights must sum to 1.0, got {total}"

def test_recommender_determinism_identical_runs(engine):
    """Verify two runs with identical inputs produce identical output."""
    lipa = engine.market_analyzer.df_market.iloc[0]
    profile = {
        "capital": 25000,
        "skills": ["Marketing", "Sales"],
        "experience": "Intermediate",
        "available_time": "5-6 hours/day",
        "setup": ["Online", "Home-Based"],
        "location": lipa["adm3_psgc"]
    }
    run1 = engine.recommend(profile, top_n=5)
    run2 = engine.recommend(profile, top_n=5)

    assert len(run1) == len(run2) == 5
    for r1, r2 in zip(run1, run2):
        assert r1["id"] == r2["id"]
        assert r1["business_type"] == r2["business_type"]
        assert r1["recommendation_score"] == r2["recommendation_score"]
        assert r1["raw_final_score"] == r2["raw_final_score"]
'''
(ROOT / "tests" / "test_hybrid_recommender.py").write_text(test_calabarzon_code.strip() + "\n", encoding="utf-8")
print("✓ Updated tests/test_hybrid_recommender.py with CALABARZON assertions")

# ----------------------------------------------------------------------
# 6. Update tests/test_validation.py to use dynamic CALABARZON PSGC
# ----------------------------------------------------------------------
val_test_code = r'''import pytest
from app import create_app
from models import db
from models.user import User

@pytest.fixture
def app_instance():
    app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        u = User(username="validator_user", email="val@test.ph")
        u.set_password("validpassword123")
        db.session.add(u)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app_instance):
    c = app_instance.test_client()
    c.post("/login", data={"email": "val@test.ph", "password": "validpassword123"}, follow_redirects=True)
    return c

@pytest.fixture
def calabarzon_psgc():
    from ml.recommendation_engine import HybridBusinessRecommender
    engine = HybridBusinessRecommender()
    return engine.market_analyzer.df_market.iloc[0]["adm3_psgc"]

def test_validation_non_numeric_capital(client, calabarzon_psgc):
    res = client.post("/find", data={"capital": "abc", "location": calabarzon_psgc, "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Please enter a valid numeric starting capital" in res.data

def test_validation_negative_capital(client, calabarzon_psgc):
    res = client.post("/find", data={"capital": "-500", "location": calabarzon_psgc, "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Starting capital must be a non-negative number" in res.data

def test_validation_unknown_skill(client, calabarzon_psgc):
    res = client.post("/find", data={"capital": "10000", "skills": ["FakeAlienSkill99"], "location": calabarzon_psgc, "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Unrecognized skill" in res.data

def test_validation_invalid_location_psgc(client):
    res = client.post("/find", data={"capital": "10000", "location": "9999999999", "setup": ["Online"]}, follow_redirects=True)
    assert res.status_code == 400
    assert b"selected municipality PSGC code is invalid" in res.data

def test_validation_empty_setup(client, calabarzon_psgc):
    res = client.post("/find", data={"capital": "10000", "location": calabarzon_psgc}, follow_redirects=True)
    assert res.status_code == 400
    assert b"Please select at least one preferred business setup" in res.data
'''
(ROOT / "tests" / "test_validation.py").write_text(val_test_code.strip() + "\n", encoding="utf-8")
print("✓ Updated tests/test_validation.py with dynamic CALABARZON PSGC fixture")

# ----------------------------------------------------------------------
# 7. Update validate_datasets.py to audit CALABARZON data
# ----------------------------------------------------------------------
val_script_code = r'''import os
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
'''
(ROOT / "validate_datasets.py").write_text(val_script_code.strip() + "\n", encoding="utf-8")
print("✓ Updated validate_datasets.py for CALABARZON")

print("\n" + "=" * 80)
print("🎉 CALABARZON LOCK COMPLETE!")
print("=" * 80)git status