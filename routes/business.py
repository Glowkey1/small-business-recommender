from flask import Blueprint, render_template, abort
from models.business import Business

biz_bp = Blueprint("biz", __name__, url_prefix="/business")

@biz_bp.route("/<int:biz_id>")
def details(biz_id):
    b = Business.query.get_or_404(biz_id)
    return render_template("user/business_details.html", business=b)
