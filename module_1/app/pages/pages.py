from flask import Blueprint, render_template

bp = Blueprint(
    "pages", __name__, template_folder="templates"
)  # Creates a blueprint object


@bp.route("/")
def home():
    """
    Routes to the home page
    """
    return render_template("home.html")


@bp.route("/contact")
def contact():
    """
    Routes to the contact page
    """
    return render_template("contact.html")


@bp.route("/projects")
def projects():
    """
    Routes to the projects
    """
    return render_template("projects.html")
