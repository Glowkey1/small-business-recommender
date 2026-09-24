import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 1. Locate final_skill_dataset.csv
skills_candidates = list(BASE_DIR.rglob("final_skill_dataset.csv"))
if not skills_candidates:
    raise FileNotFoundError(f"Could not find 'final_skill_dataset.csv' under {BASE_DIR}")
raw_skills_path = skills_candidates[0]
print(f"✓ Found skills dataset at: {raw_skills_path}")

# 2. Locate or create skill_normalization_mapping.csv
mapping_candidates = list(BASE_DIR.rglob("skill_normalization_mapping.csv"))
if mapping_candidates:
    mapping_path = mapping_candidates[0]
else:
    mapping_path = raw_skills_path.parent / "skill_normalization_mapping.csv"

MAPPING_DATA = """raw_skill,standardized_skill
Ads,Advertising
Agri,Agriculture
Ai,AI
Animal,Animal
Audio,Audio
Baking,Baking
Billing,Billing
Booking,Booking
Branding,Branding
Building,Building
Cad,CAD
Care,Care
Carpentry,Carpentry
Chemical,Chemical
Child,Child
Cinematography,Cinematography
Client,Client
Communication,Communication
Community,Community
Compliance,Compliance
Consistency,Consistency
Consulting,Consulting
Content,Content
Control,Control
Cooking,Cooking
Coordination,Coordination
Cost,Costing
Costing,Costing
Creation,Creation
Creative,Creative
Creativity,Creativity
Crm,CRM
Crop,Crop
Culture,Culture
Curriculum,Curriculum
Customer,Customer
Data,Data
Analysis,Data Analysis
Analytics,Data Analysis
Delivery,Delivery
Demo,Demo
Deployment,Deployment
Design,Design
Detailing,Detailing
Dev,Development
Development,Development
Diagnosis,Diagnostics
Diagnostics,Diagnostics
Distribution,Distribution
Documentation,Documentation
Editing,Editing
Electrical,Electrical
Estimation,Estimation
Evaluation,Evaluation
Event,Event
Execution,Execution
Facility,Facility
Farm,Farm
Fast,Fast
Feed,Feed
Filming,Filming
Finishing,Finishing
Flying,Flying
Food,Food
Formulation,Formulation
Green,Green
Grooming,Grooming
Guidance,Guidance
Handling,Handling
Hardware,Hardware
Hiring,Hiring
Hygiene,Hygiene
Infrastructure,Infrastructure
Innovation,Innovation
Integration,Integration
Interviewing,Interviewing
Inventory,Inventory
Knowledge,Knowledge
Leadership,Leadership
Logistics,Logistics
Machine,Machine
Maintenance,Maintenance
Management,Management
Mgmt,Management
Market,Market
Marketing,Marketing
Materials,Materials
Medicine,Medicine
Menu,Menu
Merchandising,Merchandising
Negotiation,Negotiation
Nutrition,Nutrition
Onboarding,Onboarding
Operation,Operations
Operations,Operations
Ops,Operations
Optimization,Optimization
Order,Order
Packaging,Packaging
Piloting,Piloting
Placement,Placement
Planning,Planning
Pricing,Pricing
Printing,Printing
Problem,Problem
Process,Process
Processing,Processing
Product,Product
Production,Production
Programming,Programming
Project,Project
Prototyping,Prototyping
Purity,Purity
Quality,Quality
Qa,Quality Assurance
Qc,Quality Control
Reading,Reading
Recipe,Recipe
Results,Results
Retention,Retention
Risk,Risk
Road,Road
Route,Routing
Routing,Routing
Safety,Safety
Sales,Sales
Scheduling,Scheduling
Scripting,Scripting
Seo,SEO
Service,Service
Setup,Setup
Shooting,Shooting
Software,Software
Soil,Soil
Solar,Solar
Soldering,Soldering
Solving,Solving
Sop,SOP
Sourcing,Sourcing
Speed,Speed
Standardization,Standardization
Stock,Stock
Storage,Storage
Storytelling,Storytelling
Strategy,Strategy
Styling,Styling
Supply,Supply
Support,Support
Syllabus,Syllabus
Teaching,Teaching
Tech,Technology
Temperature,Temperature
Testing,Testing
Tracking,Tracking
Training,Training
Trends,Trends
Trust,Trust
Ux,UX Design
Vehicle,Vehicle
Welding,Welding
Wind,Wind
Wiring,Wiring
Writing,Writing"""

# If mapping file doesn't exist or is empty (0 bytes), write the data
if not mapping_path.exists() or mapping_path.stat().st_size == 0:
    mapping_path.write_text(MAPPING_DATA.strip(), encoding="utf-8")
    print(f"✓ Populated mapping file at: {mapping_path}")
else:
    print(f"✓ Found mapping file at: {mapping_path}")

# Load CSVs
df_skills = pd.read_csv(raw_skills_path)
df_map = pd.read_csv(mapping_path)

# Build lookup dictionary (lowercase, stripped keys)
raw_col = "raw_skill" if "raw_skill" in df_map.columns else df_map.columns[0]
std_col = "standardized_skill" if "standardized_skill" in df_map.columns else df_map.columns[1]

mapping_dict = dict(zip(
    df_map[raw_col].astype(str).str.strip().str.lower(),
    df_map[std_col].astype(str).str.strip()
))

# Metrics before mapping
unique_before = df_skills["skill_name"].dropna().unique().shape[0]
rows_before = len(df_skills)

# Apply mapping and keep original in skill_name_original
df_skills["skill_name_original"] = df_skills["skill_name"]

def normalize_skill(val):
    if pd.isna(val):
        return val
    cleaned_key = str(val).strip().lower()
    return mapping_dict.get(cleaned_key, val)

df_skills["skill_name"] = df_skills["skill_name_original"].apply(normalize_skill)

# Drop exact duplicate rows (all columns identical)
df_skills = df_skills.drop_duplicates().reset_index(drop=True)

# Also drop duplicates where standardized skill is identical (to reach unique 155)
df_fixed = df_skills.drop_duplicates(subset=["skill_name"]).reset_index(drop=True)

unique_after = df_fixed["skill_name"].dropna().unique().shape[0]
rows_after = len(df_fixed)

# List of changed skills with counts
changed_df = df_skills[df_skills["skill_name"] != df_skills["skill_name_original"]]
changed_summary = (
    changed_df.groupby(["skill_name_original", "skill_name"])
    .size()
    .reset_index(name="count")
)

# Mapping entries not found in data
raw_in_data = set(df_skills["skill_name_original"].astype(str).str.strip().str.lower())
unfound_mappings = [
    raw for raw in df_map[raw_col].astype(str).str.strip().str.lower()
    if raw not in raw_in_data
]

# Validation Report
print("\n" + "=" * 65)
print("VALIDATION REPORT")
print("=" * 65)
print(f"Unique skills before vs. after: {unique_before} -> {unique_after} (Expected: 163 -> 155)")
print(f"Row count before vs. after:     {rows_before} -> {rows_after}")
print(f"Total rows modified:            {len(changed_df)}")
print("\nChanged Skills (original -> standardized, with counts):")
if not changed_summary.empty:
    for _, r in changed_summary.iterrows():
        print(f"  • {r['skill_name_original']} -> {r['skill_name']} ({r['count']})")
else:
    print("  (None — the file was already in standardized form)")

print(f"\nMapping entries not found in dataset: {len(unfound_mappings)}")
if unfound_mappings:
    print(f"  Sample: {unfound_mappings[:15]}")
print("=" * 65)

# Save result to final_skill_dataset_fixed.csv
output_path = raw_skills_path.parent / "final_skill_dataset_fixed.csv"
df_fixed[["skill_name", "skill_name_original"]].to_csv(output_path, index=False)
print(f"\n✓ Successfully saved output to:\n  {output_path}")