import pandas as pd
import re

skill_file = "data/final/final_skill_dataset.csv"
business_file = "data/final/final_business_dataset.csv"
output_file = "data/final/skill_master.csv"

skills_df = pd.read_csv(skill_file)
business_df = pd.read_csv(business_file)

skill_map = {
    "ai": "Artificial Intelligence",
    "ads": "Advertising",
    "agri": "Agriculture",
    "animal": "Animal Care",
    "booking": "Booking",
    "cad": "CAD",
    "crm": "CRM",
    "client": "Client Management",
    "customer": "Customer Service",
    "dev": "Development",
    "mgmt": "Management",
    "ops": "Operations",
    "tech": "Technology",
    "ux": "UX",
    "qa": "Quality Assurance",
    "qc": "Quality Control",
    "seo": "SEO",
    "sop": "SOP",
    "analysis": "Analysis",
    "analytics": "Analytics",
    "communication": "Communication",
    "content": "Content Creation",
    "creative": "Creativity",
    "creation": "Creation",
    "cost": "Cost Management",
    "costing": "Costing",
    "data": "Data Management",
    "design": "Design",
    "development": "Development",
    "diagnosis": "Diagnosis",
    "diagnostics": "Diagnostics",
    "documentation": "Documentation",
    "inventory": "Inventory Management",
    "logistics": "Logistics",
    "maintenance": "Maintenance",
    "management": "Management",
    "marketing": "Marketing",
    "operation": "Operations",
    "operations": "Operations",
    "planning": "Planning",
    "production": "Production",
    "quality": "Quality Management",
    "service": "Service",
    "software": "Software",
    "sourcing": "Sourcing",
    "strategy": "Strategy",
    "support": "Support",
    "teaching": "Teaching",
    "training": "Training",
    "writing": "Writing"
}

raw_skills = skills_df["skill_name"].dropna().astype(str).str.strip()

master = {}

for skill in raw_skills:
    key = skill.lower()
    standardized = skill_map.get(key, skill.title())
    master.setdefault(standardized, set()).add(skill)

for value in business_df["core_skills"].dropna().astype(str):
    terms = re.split(r"[,;/|]+", value)

    if len(terms) == 1:
        terms = value.split()

    for term in terms:
        term = term.strip()

        if not term:
            continue

        key = term.lower()
        standardized = skill_map.get(key, term.title())
        master.setdefault(standardized, set()).add(term)

rows = []

for skill_name in sorted(master):
    rows.append({
        "skill_name": skill_name,
        "source_terms": ", ".join(sorted(master[skill_name]))
    })

result = pd.DataFrame(rows)

result.to_csv(output_file, index=False)

print("SKILL MASTER CREATED")
print("====================")
print("ROWS:", len(result))
print("OUTPUT:", output_file)
print()
print(result.to_string(index=False))
