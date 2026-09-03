from flask import Flask
from app.pages import pages


def create_app():
    """
    Creates a flask object and registers
    the blueprint from app/pages/pages.py
    """
    app = Flask(__name__)
    app.register_blueprint(pages.bp)

    return app
