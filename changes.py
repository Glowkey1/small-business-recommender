# fix_user_persistence.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent

print("Fixing test database isolation and adding username/email login flexibility...")

# 1. Update app.py to accept test_config cleanly before db.init_app
app_file = ROOT / "app.py"
app_code = app_file.read_text(encoding="utf-8")
if "def create_app(config_class=Config, test_config=None):" not in app_code:
    app_code = app_code.replace(
        "def create_app(config_class=Config):",
        "def create_app(config_class=Config, test_config=None):"
    )
    app_code = app_code.replace(
        "app.config.from_object(config_class)",
        "app.config.from_object(config_class)\n    if test_config:\n        app.config.update(test_config)"
    )
    app_file.write_text(app_code, encoding="utf-8")
    print("  ✓ Updated app.py create_app to isolate test configurations")

# 2. Update routes/auth.py to allow login by either Email OR Username
auth_file = ROOT / "routes" / "auth.py"
auth_code = auth_file.read_text(encoding="utf-8")
if "user = User.query.filter_by(email=email).first()" in auth_code:
    auth_code = auth_code.replace(
        "user = User.query.filter_by(email=email).first()",
        "user = User.query.filter((User.email == email) | (User.username == email)).first()"
    )
    auth_file.write_text(auth_code, encoding="utf-8")
    print("  ✓ Updated routes/auth.py to allow login via Username OR Email")

# 3. Update test fixtures so they pass test_config directly into create_app
test_files = [
    ROOT / "tests" / "test_auth.py",
    ROOT / "tests" / "test_security.py",
    ROOT / "tests" / "test_validation.py",
    ROOT / "tests" / "test_gating_and_redesign.py"
]

for tf in test_files:
    if tf.exists():
        t_code = tf.read_text(encoding="utf-8")
        # Replace legacy fixture pattern
        t_code = t_code.replace(
            'app = create_app()\n    app.config["TESTING"] = True\n    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"',
            'app = create_app(test_config={"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})'
        )
        t_code = t_code.replace(
            'app = create_app()\n    app.config["TESTING"] = False\n    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"',
            'app = create_app(test_config={"TESTING": False, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": True})'
        )
        tf.write_text(t_code, encoding="utf-8")
        print(f"  ✓ Isolated fixture in {tf.name}")

print("\nDone! Local database is now protected from pytest wipes.")