import os
import pandas as pd
from app import create_app
from models import db
from models.business import Business
from models.skill import Skill
from models.category import Category
from models.user import User

app = create_app()

with app.app_context():
    db.create_all()
    print("Database schema created/verified.")

    # 1. Seed Real Skills extracted from actual files
    skill_csv = os.path.join("data", "final", "final_skill_dataset.csv")
    if os.path.exists(skill_csv):
        df_skills = pd.read_csv(skill_csv)
        count_s = 0
        for _, r in df_skills.iterrows():
            name = str(r["skill_name"]).strip()
            if name and not Skill.query.filter_by(name=name).first():
                db.session.add(Skill(name=name))
                count_s += 1
        db.session.commit()
        print(f"✓ Seeded {count_s} unique skills from your real data.")
    else:
        print("⚠ Run ml/preprocessing.py first to extract skills from your data.")

    # 2. Seed Real Business Catalog from actual files
    biz_csv = os.path.join("data", "final", "final_business_dataset.csv")
    if os.path.exists(biz_csv):
        df_biz = pd.read_csv(biz_csv)
        count_b = 0
        for _, r in df_biz.iterrows():
            b_type = str(r["business_type"]).strip()
            cat = str(r.get("category", "General")).strip().title()
            
            if not Category.query.filter_by(name=cat).first():
                db.session.add(Category(name=cat))

            if not Business.query.filter_by(business_type=b_type).first():
                biz = Business(
                    business_type=b_type,
                    category=cat,
                    startup_cost_display=str(r.get("startup_cost", "Minimal")),
                    min_capital=float(r.get("min_capital", 0.0)),
                    core_skills=str(r.get("core_skills", "")),
                    people_needed=str(r.get("people_needed", "1 person")),
                    minimum_requirements=str(r.get("minimum_requirements", "")),
                    strategies=str(r.get("strategies", "")),
                    risks=str(r.get("risks", "")),
                    business_setup=str(r.get("business_setup", "Online / Home-Based")),
                    experience_required=str(r.get("experience_level", "Beginner"))
                )
                db.session.add(biz)
                count_b += 1
        db.session.commit()
        print(f"✓ Seeded {count_b} businesses from your real catalog.")
    else:
        print("⚠ Run ml/preprocessing.py first to build final_business_dataset.csv.")

    # 3. Create Default Admin
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@smallbiz.local", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("✓ Created default admin user (admin / admin123).")
