import re
from urllib.parse import urlsplit
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)

def is_safe_url(target):
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    next_page = request.args.get("next")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("A valid email address is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("auth/register.html", username=username, email=email, next=next_page), 400

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already registered.", "danger")
            return render_template("auth/register.html", username=username, email=email, next=next_page), 400

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Mabuhay! Your account has been created.", "success")

        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for("rec.find"))

    return render_template("auth/register.html", next=next_page)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_page = request.args.get("next")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("rec.find"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", next=next_page)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.landing"))
