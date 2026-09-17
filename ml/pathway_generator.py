class BusinessPathwayGenerator:
    @staticmethod
    def generate(business_data, user_profile):
        cap = float(user_profile.get("capital", 0))
        gaps = business_data.get("skill_gaps", [])
        matched = business_data.get("matched_skills", [])
        reqs = business_data.get("minimum_requirements", "Standard workspace equipment")
        strat = business_data.get("strategies", "Carefully monitor expenses and prioritize customer satisfaction.")
        risks = business_data.get("risks", "Competitive shifts and cash flow delays.")

        steps = [
            {
                "phase": "Phase 1: Financial & Demand Validation",
                "title": "Allocate Capital & Confirm Market",
                "description": f"Ringfence your available ₱{cap:,.2f} for mandatory startup items only. Confirm demand through 10-15 prospective customer interviews."
            },
            {
                "phase": "Phase 2: Competency & Workspace Setup",
                "title": "Bridge Skill Gaps & Prepare Workspace",
                "description": f"Focus immediately on learning: {', '.join(gaps) if gaps else 'Core competencies already met.'}. Requirements: {reqs}."
            },
            {
                "phase": "Phase 3: Pilot & Soft Launch",
                "title": "Start With Low-Risk Channels",
                "description": f"Establish {business_data.get('business_setup', 'Online / Home-Based')} channels. Take pre-orders to avoid excess inventory."
            },
            {
                "phase": "Phase 4: Risk Control & Defense",
                "title": "Deploy Strategy Against Primary Risks",
                "description": f"Address catalog risks: {risks}. Maintain operational survival strategy: {strat}."
            },
            {
                "phase": "Phase 5: Scaling & Reinvestment",
                "title": "Sustainable Growth",
                "description": "Reinvest 30-50% of monthly net margins into enhanced marketing and better supplier wholesale terms."
            }
        ]

        return {
            "business_type": business_data.get("business_type"),
            "matched_skills": matched,
            "skill_gaps": gaps,
            "steps": steps
        }
