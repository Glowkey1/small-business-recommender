import os
import secrets
from flask import Flask, request, session, abort, render_template, redirect, url_for
from flask_login import LoginManager
from config import Config
from models import db
from models.user import User
from services.seed_service import seed_database_if_empty
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
            seed_database_if_empty()
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            raise

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Create a free account or sign in to get your personalized business matches."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_csrf():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return {"csrf_token": lambda: session["csrf_token"]}

    @app.before_request
    def csrf_protect():
        if request.method == "POST" and not app.config.get("TESTING"):
            sent_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            session_token = session.get("csrf_token")
            if not sent_token or sent_token != session_token:
                abort(400, description="CSRF token missing or invalid.")

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/400.html", error=getattr(e, "description", "Bad Request")), 400

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html", error="The requested page could not be found."), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html", error="An internal server error occurred. Please try again later."), 500

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(rec_bp)
    app.register_blueprint(biz_bp)
    app.register_blueprint(admin_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode, port=5000)
