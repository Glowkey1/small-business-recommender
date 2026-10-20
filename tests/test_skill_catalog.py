import pytest

from create_skill_catalog import build_business_skills, load_alias_map, load_business_frame
from ml.recommendation_engine import HybridBusinessRecommender
from ml.skill_catalog import load_skill_catalog, catalog_skill_names
from ml.skill_fields import FIELD_ORDER, build_skill_groups

from app import create_app
from models import db
from models.user import User


@pytest.fixture(scope="module")
def engine():
    return HybridBusinessRecommender()


@pytest.fixture
def app_instance():
    app = create_app(
        test_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        user = User(username="skill_user", email="skills@test.ph")
        user.set_password("validpassword123")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    c = app_instance.test_client()
    c.post(
        "/login",
        data={"email": "skills@test.ph", "password": "validpassword123"},
        follow_redirects=True,
    )
    return c


def test_catalog_schema_and_counts():
    df = load_skill_catalog()
    assert list(df.columns) == [
        "skill_name",
        "field",
        "maps_to",
        "aliases",
        "related_business_ids",
        "related_business_types",
        "source",
    ]
    assert len(df) == 154
    assert len(df[df["source"] == "catalog_core_skill"]) == 102
    assert len(df[df["source"] == "curated_extension"]) == 52
    assert set(df["field"]).issubset(set(FIELD_ORDER))
    assert df["skill_name"].str.lower().is_unique
    assert (df["related_business_ids"].str.len() > 0).all()


def test_every_option_maps_to_a_real_business_skill():
    businesses = load_business_frame()
    aliases = load_alias_map()
    business_skills, _ = build_business_skills(businesses, aliases)
    df = load_skill_catalog()

    for _, row in df.iterrows():
        target = row["maps_to"]
        supported = [business_id for business_id, skills in business_skills.items() if target in skills]
        assert supported, f"{row['skill_name']} maps to unused skill {target!r}"

        listed = [
            int(value)
            for value in row["related_business_ids"].split(";")
            if value.strip()
        ]
        assert listed, f"{row['skill_name']} has no related businesses"
        for business_id in listed:
            assert business_id in business_skills, f"{row['skill_name']} references unknown id {business_id}"
            assert target in business_skills[business_id], (
                f"{row['skill_name']} lists business {business_id} but it does not use {target!r}"
            )


def test_engine_selectable_skills_match_catalog(engine):
    catalog_names = catalog_skill_names()
    assert len(catalog_names) == 154
    assert set(engine.selectable_skills) == set(catalog_names)
    for name in catalog_names:
        assert name in engine.selectable_skills


def test_all_catalog_skills_are_grouped(engine):
    groups = build_skill_groups(engine.selectable_skills)
    assert sum(len(group["skills"]) for group in groups) == 154
    assert all(group["field"] != "Other Skills" for group in groups)


def test_catalog_aliases_resolve_to_mapped_skill(engine):
    assert engine.skill_alias_map["cash handling"] == "Sales"
    assert engine.skill_alias_map["food safety"] == "Hygiene"
    assert engine.skill_alias_map["ui/ux design"] == "UX"
    assert engine.skill_alias_map["accounting"] == "Basic Bookkeeping"


def test_new_skills_match_business_requirements(engine):
    _, matched, _ = engine.calculate_skill_score(["Cash Handling"], "sales pricing")
    assert "Sales" in matched

    _, matched, _ = engine.calculate_skill_score(["Food Safety"], "baking inventory hygiene")
    assert "Hygiene" in matched

    _, matched, _ = engine.calculate_skill_score(["UI/UX Design"], "programming ux testing")
    assert "UX" in matched


def test_find_form_shows_new_catalog_options(client):
    res = client.get("/find")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    for option in [
        "Food Safety",
        "Cash Handling",
        "UI/UX Design",
        "Accounting",
        "Pet First Aid",
        "Fleet Management",
    ]:
        assert option in html


def test_validation_accepts_new_catalog_option(client, engine):
    location = engine.market_analyzer.df_market.iloc[0]["adm3_psgc"]
    res = client.post(
        "/find",
        data={
            "capital": "50000",
            "skills": ["Cash Handling"],
            "experience": "Beginner",
            "available_time": "5-6 hours/day",
            "setup": ["Online"],
            "location": location,
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Unrecognized skill" not in res.data
