import re
import math
from config import Config

def validate_recommendation_input(form_data, market_analyzer, selectable_skills) -> tuple:
    errors = []
    clean = {}

    # 1. Capital Validation
    raw_cap = form_data.get("capital", "")
    cap_str = re.sub(r"[₱,\s]", "", str(raw_cap))
    try:
        cap_val = float(cap_str)
        if not math.isfinite(cap_val) or cap_val < 0:
            errors.append("Starting capital must be a non-negative number.")
        elif cap_val > Config.MAX_CAPITAL:
            errors.append(f"Starting capital cannot exceed ₱{Config.MAX_CAPITAL:,.0f}.")
        else:
            clean["capital"] = cap_val
    except (ValueError, TypeError):
        errors.append("Please enter a valid numeric starting capital.")

    # 2. Skills Validation
    raw_skills = form_data.getlist("skills") if hasattr(form_data, "getlist") else form_data.get("skills", [])
    valid_skill_map = {s.lower().strip(): s for s in selectable_skills}
    clean_skills = []
    for s in raw_skills:
        s_clean = str(s).strip()
        if not s_clean:
            continue
        canon = valid_skill_map.get(s_clean.lower())
        if canon:
            if canon not in clean_skills:
                clean_skills.append(canon)
        else:
            errors.append(f"Unrecognized skill: '{s_clean}'. Please select from the allowed skill list.")
    clean["skills"] = clean_skills

    # 3. Experience Validation
    exp = form_data.get("experience", "Beginner").strip()
    if exp in Config.ALLOWED_EXPERIENCE:
        clean["experience"] = exp
    else:
        errors.append(f"Experience must be one of: {', '.join(Config.ALLOWED_EXPERIENCE)}.")

    # 4. Available Time Validation
    avail_time = form_data.get("available_time", "5-6 hours/day").strip()
    if avail_time in Config.ALLOWED_TIMES:
        clean["available_time"] = avail_time
    else:
        errors.append(f"Available time must be one of: {', '.join(Config.ALLOWED_TIMES)}.")

    # 5. Preferred Setup Validation
    raw_setups = form_data.getlist("setup") if hasattr(form_data, "getlist") else form_data.get("setup", [])
    if isinstance(raw_setups, str):
        raw_setups = [raw_setups]
    clean_setups = [s.strip() for s in raw_setups if s.strip() in Config.ALLOWED_SETUPS]
    if not clean_setups:
        errors.append(f"Please select at least one preferred business setup ({', '.join(Config.ALLOWED_SETUPS)}).")
    else:
        clean["setup"] = clean_setups

    # 6. Location PSGC Validation
    loc_psgc = form_data.get("location", "").strip().zfill(10)
    if not loc_psgc:
        errors.append("Please select a Philippine City / Municipality.")
    else:
        match = market_analyzer.df_market[market_analyzer.df_market["adm3_psgc"] == loc_psgc]
        if match.empty:
            errors.append("The selected municipality PSGC code is invalid or not in the Philippine dataset.")
        else:
            clean["location"] = loc_psgc
            clean["location_display"] = match.iloc[0]["display_city"]

    return clean, errors
