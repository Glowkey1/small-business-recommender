import logging
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

# Business Catalog Category to OSM Category Mapping
BUSINESS_TO_OSM_MAP = {
    "food": "Food",
    "food & beverage": "Food",
    "bakery": "Food",
    "restaurant": "Food",
    "cafe": "Food",
    "catering": "Food",
    "retail": "Retail",
    "e-commerce": "Retail",
    "store": "Retail",
    "merchandising": "Retail",
    "technology": "Technology",
    "digital services": "Technology",
    "it": "Technology",
    "software": "Technology",
    "education": "Education",
    "tutoring": "Education",
    "training": "Education",
    "healthcare": "Healthcare",
    "health & fitness": "Healthcare",
    "medical": "Healthcare",
    "personal services": "Personal Services",
    "services": "Personal Services",
    "laundry": "Personal Services",
    "grooming": "Personal Services",
    "cleaning": "Personal Services",
    "automotive": "Automotive",
    "car wash": "Automotive",
    "auto repair": "Automotive",
    "professional services": "Professional Services",
    "consulting": "Professional Services",
    "creative services": "Professional Services",
    "accommodation": "Accommodation",
    "hospitality": "Accommodation",
    "tourism": "Tourism",
    "travel": "Tourism",
    "skilled trades": "Skilled Trades",
    "manufacturing": "Skilled Trades",
    "artisan": "Skilled Trades",
    "crafts": "Skilled Trades"
}

class PhilippineMarketAnalyzer:
    """Preloads and queries 250 Philippine Municipality features and OSM presence."""
    def __init__(self, market_features_path: Path):
        self.market_features_path = market_features_path
        self.df_market = pd.DataFrame()
        self.locations_index = []
        self._load_data()

    def _load_data(self):
        if not self.market_features_path.exists():
            logger.warning(f"Market features file not found at: {self.market_features_path}")
            return
        try:
            self.df_market = pd.read_csv(self.market_features_path)
            # Standardize municipality names for lookup
            self.df_market["lookup_key"] = (
                self.df_market["municipality_city"].astype(str).str.strip().str.lower()
            )
            self.locations_index = sorted(self.df_market["municipality_city"].dropna().unique().tolist())
            logger.info(f"Loaded market features for {len(self.df_market)} Philippine municipalities.")
        except Exception as e:
            logger.error(f"Error loading market features: {e}")

    def get_locations(self) -> list:
        return self.locations_index

    def map_category(self, business_cat: str, business_type: str = "") -> str:
        cat_lower = str(business_cat).lower().strip()
        if cat_lower in BUSINESS_TO_OSM_MAP:
            return BUSINESS_TO_OSM_MAP[cat_lower]
        type_lower = str(business_type).lower().strip()
        for k, v in BUSINESS_TO_OSM_MAP.items():
            if k in type_lower:
                return v
        return "Retail"

    def analyze_location_market(self, municipality_name: str, business_category: str, business_type: str = "") -> dict:
        if self.df_market.empty or not municipality_name:
            return {
                "location_score": 0.50,
                "evidence_text": "National baseline market estimate (specific location not selected).",
                "osm_count": None,
                "population": None,
                "density_per_1000": None,
                "category": self.map_category(business_category, business_type)
            }

        key = str(municipality_name).strip().lower()
        match = self.df_market[self.df_market["lookup_key"] == key]

        if match.empty:
            # Fuzzy fallback match
            match = self.df_market[self.df_market["lookup_key"].str.contains(key, regex=False)]

        if match.empty:
            return {
                "location_score": 0.50,
                "evidence_text": f"Market features not indexed for {municipality_name}. Using baseline rating.",
                "osm_count": None,
                "population": None,
                "density_per_1000": None,
                "category": self.map_category(business_category, business_type)
            }

        row = match.iloc[0]
        osm_cat = self.map_category(business_category, business_type)
        cat_col = f"{osm_cat.lower().replace(' ', '_')}_count"

        osm_count = int(row[cat_col]) if cat_col in row and pd.notna(row[cat_col]) else 0
        total_osm = int(row["total_osm_records"]) if "total_osm_records" in row and pd.notna(row["total_osm_records"]) else 0

        # Safe Population Handling (PSA HUC population data may be missing for some cities like Iloilo, Lucena, Olongapo)
        pop_val = row.get("population_2024")
        pop_num = None
        density = None

        if pd.notna(pop_val) and float(pop_val) > 0:
            pop_num = float(pop_val)
            density = round((osm_count / pop_num) * 1000, 3)

        # Market presence scoring: balanced view between market validation and headroom
        if osm_count >= 20:
            presence_desc = f"Strong established market presence ({osm_count} mapped {osm_cat} businesses)"
            score = 0.85
        elif osm_count >= 5:
            presence_desc = f"Active local market presence ({osm_count} mapped {osm_cat} businesses)"
            score = 0.90
        elif osm_count >= 1:
            presence_desc = f"Emerging local presence ({osm_count} mapped {osm_cat} businesses)"
            score = 0.75
        else:
            presence_desc = f"Lower mapped local competition in available data (0 currently mapped {osm_cat} businesses)"
            score = 0.65

        if pop_num:
            evidence_text = f"{presence_desc} in {row['municipality_city']}. (2024 PSA Pop: {int(pop_num):,}, Density: {density} per 1,000 residents)."
        else:
            evidence_text = f"{presence_desc} in {row['municipality_city']}. (PSA population data unlisted for this specific municipality)."

        return {
            "location_score": score,
            "evidence_text": evidence_text,
            "osm_count": osm_count,
            "total_osm": total_osm,
            "population": pop_num,
            "density_per_1000": density,
            "category": osm_cat
        }
