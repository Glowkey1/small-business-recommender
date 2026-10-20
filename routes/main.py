from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def landing():
    from routes.recommendation import coverage_context
    return render_template("main/landing.html", **coverage_context())
