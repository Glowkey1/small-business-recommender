REMOVED_SKILL_MATCHES = {
    "Menu": "Cooking",
    "Nutrition": "Cooking",
    "Recipe": "Cooking",
    "Agriculture": "Gardening",
    "Chemical": "Formulation",
    "Crop": "Gardening",
    "Feed": "Animal Care",
    "Soil": "Gardening",
    "Solar": "Electrical",
    "Event": "Planning",
    "Trends": "Analytics",
    "Artificial Intelligence": "Development",
    "Hardware": "Maintenance",
    "Infrastructure": "Development",
    "Software": "Development",
    "Technology": "Development",
    "Building": "Carpentry",
    "Control": "Quality Control",
    "Machine": "Maintenance",
    "Materials": "Sourcing",
    "Purity": "Quality Control",
    "Setup": "Maintenance",
    "Temperature": "Quality Control",
    "Vehicle": "Vehicle Detailing",
    "Facility": "Operations",
    "Handling": "Operations",
    "Order": "Operations",
    "Supply": "Sourcing",
    "Consistency": "Quality Control",
    "Execution": "Operations",
    "Innovation": "Strategy",
    "Process": "Operations",
    "Risk": "Compliance",
    "Speed": "Delivery",
    "Community": "Communication",
    "Culture": "Communication",
    "Placement": "Hiring",
    "Service": "Customer Service",
    "Solving": "Strategy",
    "Support": "Customer Service",
    "Trust": "Customer Service",
    "Knowledge": "Training",
    "Reading": "Training",
    "Syllabus": "Curriculum",
    "Care": "Customer Service",
    "Medicine": "Hygiene",
}

SKILL_SYNONYM_MERGES = {
    "Analysis": "Analytics",
    "Cost Management": "Costing",
    "Quality Assurance": "Quality Control",
    "Quality Inspection": "Quality Control",
    "Quality Management": "Quality Control",
    "Creation": "Creativity",
    "Document Formatting": "Documentation",
    "Route": "Routing",
    "Diagnosis": "Diagnostics",
    "Flying": "Piloting",
    "Stock": "Inventory Management",
    "Detailing": "Vehicle Detailing",
    **REMOVED_SKILL_MATCHES,
}

FIELD_ORDER = [
    "Food & Beverage",
    "Agriculture & Environment",
    "Retail & Sales",
    "Marketing & Creative",
    "Technology & Data",
    "Trades & Manufacturing",
    "Logistics & Operations",
    "Business & Finance",
    "Customer & People",
    "Education & Training",
    "Health & Personal Care",
]

FIELD_SKILLS = {
    "Food & Beverage": [
        "Baking", "Cooking", "Food Costing",
    ],
    "Agriculture & Environment": [
        "Animal Care", "Gardening", "Plant Care", "Propagation",
    ],
    "Retail & Sales": [
        "Booking", "Demo", "Fashion Curation", "Inventory Management",
        "Merchandising", "Pricing", "Sales",
    ],
    "Marketing & Creative": [
        "Advertising", "Audio", "Branding", "Cinematography", "Content Creation",
        "Creativity", "Design", "Editing", "Filming", "Marketing",
        "Photography", "Presentation", "Printing", "Scripting", "SEO",
        "Shooting", "Social Media", "Storytelling", "Styling", "Writing",
    ],
    "Technology & Data": [
        "Analytics", "CAD", "Computer Literacy", "CRM", "Data Management",
        "Deployment", "Development", "Integration", "Optimization", "Piloting",
        "Programming", "Prototyping", "Testing",
    ],
    "Trades & Manufacturing": [
        "Carpentry", "Diagnostics", "Electrical", "Estimation", "Finishing",
        "Formulation", "Maintenance", "Processing", "Production", "Quality Control",
        "Safety", "Soldering", "Standardization", "Vehicle Detailing", "Welding",
        "Wiring",
    ],
    "Logistics & Operations": [
        "Coordination", "Delivery", "Distribution", "Logistics", "Packaging",
        "Routing", "Scheduling", "Sourcing", "Storage", "Tracking",
    ],
    "Business & Finance": [
        "Basic Bookkeeping", "Billing", "Compliance", "Consulting", "Costing",
        "Documentation", "Evaluation", "Management", "Operations", "Planning",
        "Project", "SOP", "Strategy",
    ],
    "Customer & People": [
        "Client Management", "Communication", "Customer Service", "Hiring",
        "Interviewing", "Leadership", "Negotiation", "Onboarding", "Retention",
    ],
    "Education & Training": [
        "Curriculum", "Guidance", "Teaching", "Training",
    ],
    "Health & Personal Care": [
        "Cleaning", "Grooming", "Hygiene",
    ],
}

REMOVED_SKILLS = {
    "Menu", "Nutrition", "Recipe",
    "Agriculture", "Chemical", "Crop", "Feed", "Soil", "Solar",
    "Event", "Trends",
    "Artificial Intelligence", "Hardware", "Infrastructure", "Software",
    "Technology",
    "Building", "Control", "Machine", "Materials", "Purity", "Setup",
    "Temperature", "Vehicle",
    "Facility", "Handling", "Order", "Supply",
    "Consistency", "Execution", "Innovation", "Process", "Risk", "Speed",
    "Community", "Culture", "Placement", "Service", "Solving", "Support",
    "Trust",
    "Knowledge", "Reading", "Syllabus",
    "Care", "Medicine",
}

OTHER_FIELD = "Other Skills"


def canonical_skill(name):
    current = str(name).strip()
    seen = set()
    while current in SKILL_SYNONYM_MERGES and current not in seen:
        seen.add(current)
        current = SKILL_SYNONYM_MERGES[current]
    return current


def build_skill_groups(selectable_skills):
    from ml.skill_catalog import get_skill_groups

    catalog_groups = get_skill_groups(selectable_skills, FIELD_ORDER)
    if catalog_groups:
        return catalog_groups

    canonical = []
    seen = set()
    for skill in selectable_skills:
        name = canonical_skill(skill)
        if not name or name in REMOVED_SKILLS or name in seen:
            continue
        seen.add(name)
        canonical.append(name)

    grouped = []
    assigned = set()
    for field in FIELD_ORDER:
        members = sorted(
            (s for s in canonical if s in FIELD_SKILLS[field]),
            key=str.lower,
        )
        if members:
            grouped.append({"field": field, "skills": members})
            assigned.update(members)

    remaining = sorted((s for s in canonical if s not in assigned), key=str.lower)
    if remaining:
        grouped.append({"field": OTHER_FIELD, "skills": remaining})

    return grouped
