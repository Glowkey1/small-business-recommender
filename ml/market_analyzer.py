import re
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
