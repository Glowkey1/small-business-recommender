import io
import pandas as pd

# Load datasets
raw_skills_path = "final_skill_dataset.csv"
mapping_path = "skill_normalization_mapping.csv"

df_skills = pd.read_csv(raw_skills_path)
df_map = pd.read_csv(mapping_path)

# 1. Build lookup dictionary (lowercase, stripped keys)
mapping_dict = dict(
    zip(
        df_map["raw_skill"].astype(str).str.strip().str.lower(),
        df_map["standardized_skill"].astype(str).str.strip(),
    )
)

# 2. Record metrics before mapping
unique_before = df_skills["skill_name"].dropna().unique().shape[0]
rows_before = len(df_skills)

# 3. Apply normalization while preserving original column for auditing
df_skills["skill_name_original"] = df_skills["skill_name"]


def normalize_skill(val):
    if pd.isna(val):
        return val
    cleaned_key = str(val).strip().lower()
    return mapping_dict.get(cleaned_key, val)


df_skills["skill_name"] = df_skills["skill_name_original"].apply(
    normalize_skill
)

# 4. Audit changed skills
changed_mask = df_skills["skill_name"] != df_skills["skill_name_original"]
changed_df = df_skills[changed_mask]
changed_summary = (
    changed_df.groupby(["skill_name_original", "skill_name"])
    .size()
    .reset_index(name="count")
)

# 5. Drop exact duplicate rows (all columns identical)
# Note: If deduplicating solely by standardized name across records, use subset=['skill_name']
df_fixed = df_skills.drop_duplicates(subset=["skill_name"]).reset_index(
    drop=True
)

unique_after = df_fixed["skill_name"].dropna().unique().shape[0]
rows_after = len(df_fixed)

# 6. Check unmapped mapping entries
raw_in_data = set(
    df_skills["skill_name_original"].astype(str).str.strip().str.lower()
)
unfound_mappings = [
    raw
    for raw in df_map["raw_skill"].astype(str).str.strip().str.lower()
    if raw not in raw_in_data
]

# Print Validation Report
print("=" * 60)
print("VALIDATION REPORT")
print("=" * 60)
print(
    f"Unique skills before vs. after: {unique_before} -> {unique_after} (Expected: 163 -> 155)"
)
print(f"Row count before vs. after:     {rows_before} -> {rows_after}")
print(f"Total skills modified:          {len(changed_df)}")
print(f"Mapping entries not found:      {len(unfound_mappings)}")
if unfound_mappings:
    print(f"Unfound entries sample:         {unfound_mappings[:10]}")
print("=" * 60)

# Save result
df_fixed[["skill_name", "skill_name_original"]].to_csv(
    "final_skill_dataset_fixed.csv", index=False
)
print("Successfully generated: final_skill_dataset_fixed.csv")