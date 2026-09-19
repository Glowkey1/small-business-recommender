import re

# Standard synonym & acronym mapping dictionary
SKILL_SYNONYMS = {
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "crm": "CRM",
    "seo": "SEO",
    "ux": "UX",
    "ui": "UI",
    "qa": "Quality Assurance",
    "qc": "Quality Control",
    "cad": "CAD",
    "sop": "SOP",
    "mgmt": "Management",
    "ops": "Operations",
    "dev": "Development",
    "tech": "Technology",
    "hr": "Human Resources",
    "pr": "Public Relations",
    "it": "Information Technology",
    "pos": "Point of Sale",
    "hvac": "HVAC",
    "accounting": "Accounting",
    "bookkeeping": "Bookkeeping",
    "cooking": "Cooking",
    "baking": "Baking",
    "marketing": "Marketing",
    "social media": "Social Media",
    "sales": "Sales",
    "graphic design": "Graphic Design",
    "photography": "Photography",
    "customer service": "Customer Service"
}

# Standalone generic fragments that should not be treated as distinct isolated skills
GENERIC_STOP_FRAGMENTS = {
    "fast", "green", "child", "food", "farm", "road", "wind",
    "problem", "results", "product", "market", "care", "building", "basic"
}

def normalize_skill_name(skill_str: str) -> str:
    """Normalizes skill strings for case consistency, punctuation, and known acronyms."""
    if not skill_str:
        return ""
    cleaned = re.sub(r"[^\w\s-]", "", str(skill_str)).strip()
    lower = cleaned.lower()
    if lower in SKILL_SYNONYMS:
        return SKILL_SYNONYMS[lower]
    # Check title case token transformations
    tokens = [SKILL_SYNONYMS.get(t.lower(), t.capitalize()) for t in cleaned.split()]
    return " ".join(tokens)

def parse_skills_list(raw_skills_str: str) -> list:
    """Parses delimiter-separated skill strings into clean, normalized lists."""
    if not raw_skills_str:
        return []
    # Split by comma, pipe, semicolon, or multi-space
    parts = re.split(r"[,;|\n]+", str(raw_skills_str))
    res = []
    seen = set()
    for p in parts:
        # Also handle space-separated terms if no commas were present
        subparts = [p.strip()] if "," in str(raw_skills_str) else p.strip().split()
        for sub in subparts:
            norm = normalize_skill_name(sub)
            if norm and len(norm) > 1 and norm.lower() not in seen:
                seen.add(norm.lower())
                res.append(norm)
    return res
