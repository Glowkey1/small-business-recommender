import os
from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db
from models.user import User
from routes.main import main_bp
from routes.auth import auth_bp
from routes.user import user_bp
from routes.recommendation import rec_bp
from routes.business import biz_bp
from routes.admin import admin_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"❌ Could not initialize database at: {app.config['SQLALCHEMY_DATABASE_URI']}")
            print(f"   Reason: {e}")
            raise

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Create a free account or sign in to get your personalized business matches."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(rec_bp)
    app.register_blueprint(biz_bp)
    app.register_blueprint(admin_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
