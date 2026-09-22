import logging
import pandas as pd
from config import Config
from models import db
from models.business import Business
from models.skill import Skill

logger = logging.getLogger(__name__)

def seed_database_if_empty():
    try:
        biz_count = Business.query.count()
        if biz_count == 0 and Config.FINAL_BUSINESSES_CSV.exists():
            df_biz = pd.read_csv(Config.FINAL_BUSINESSES_CSV)
            for _, r in df_biz.iterrows():
                b = Business(
                    id=int(r["id"]),
                    business_type=str(r["business_type"]).strip(),
                    category=str(r.get("category", "General")).strip(),
                    startup_cost_display=str(r.get("startup_cost", "Minimal")).strip(),
                    min_capital=float(r.get("min_capital", 0.0)),
                    core_skills=str(r.get("core_skills", "")).strip(),
                    people_needed=str(r.get("people_needed", "1 person")).strip(),
                    minimum_requirements=str(r.get("minimum_requirements", "")).strip(),
                    strategies=str(r.get("strategies", "")).strip(),
                    risks=str(r.get("risks", "")).strip(),
                    business_setup=str(r.get("business_setup", "Online / Home-Based")).strip(),
                    experience_required=str(r.get("experience_level", "Beginner")).strip()
                )
                db.session.add(b)
            db.session.commit()
            logger.info(f"Seeded {len(df_biz)} catalog businesses into database.")

        skill_count = Skill.query.count()
        if skill_count == 0:
            skills_to_seed = set()
            for p in [Config.FINAL_SKILLS_CSV, Config.SKILL_MASTER_CSV]:
                if p.exists():
                    df_s = pd.read_csv(p)
                    col = df_s.columns[0]
                    for val in df_s[col].dropna():
                        s_name = str(val).strip()
                        if s_name:
                            skills_to_seed.add(s_name)
            for s in sorted(list(skills_to_seed)):
                db.session.add(Skill(name=s))
            db.session.commit()
            logger.info(f"Seeded {len(skills_to_seed)} unique skills into database.")
    except Exception as e:
        logger.error(f"Error during startup database seeding: {e}")
        db.session.rollback()
