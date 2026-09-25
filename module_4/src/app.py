import json
import threading

from flask import Flask, jsonify, render_template, request, send_from_directory

from clean import clean_data, load_data as load_clean_data
from load_data import main as load_sql_data
from models import Session
from orm_queries import (
    _question_1,
    _question_2,
    _question_3,
    _question_4,
    _question_5,
    _question_6,
    _question_7,
    _question_8,
    _question_9,
    _question_10,
    _question_11,
)
from scrape import scrape_data, survey_url

APPLICANT_DATA_FILE = r"src\llm_extend_applicant_data.json"

pull_status = {
    "state": "idle",
    "message": "Ready to pull data.",
}

authentication_event = threading.Event()
pull_thread = None


def create_app(test_config=None):
    """
    The application factory for creating the Flask
    application.
    """
    flask_app = Flask(
        __name__,
        template_folder=".",
        static_folder=".",
    )

    if test_config:
        flask_app.config.update(test_config)

    flask_app.config.setdefault("PULL_FUNCTION", _run_pull)
    flask_app.config.setdefault("UPDATE_FUNCTION", lambda: None)
    

    register_routes(flask_app)

    return flask_app


def _run_pull():
    global pull_status

    try:
        pull_status["state"] = "authenticating"
        pull_status["message"] = (
            "Chrome opened. Complete Cloudflare authentication, "
            "then click Resume Pulling."
        )

        scrape_data(
            survey_url,
            authentication_event=authentication_event,
        )

        pull_status["state"] = "cleaning"
        pull_status["message"] = "Cleaning new applicant data..."

        data = load_clean_data(APPLICANT_DATA_FILE)
        cleaned_data = clean_data(data)

        with open(
            APPLICANT_DATA_FILE,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                cleaned_data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        pull_status["state"] = "loading"
        pull_status["message"] = (
            "Loading new applicant data into PostgreSQL..."
        )

        load_sql_data()

        pull_status["state"] = "complete"
        pull_status["message"] = "Data pull completed successfully."

    except Exception as e:
        pull_status["state"] = "error"
        pull_status["message"] = f"Pull failed: {e}"

    finally:
        authentication_event.clear()

def _is_pull_running():
    """
    Checks whether the Pull Data process is currently running.
    """
    return pull_thread is not None and pull_thread.is_alive()


def register_routes(flask_app):
    """
    Registers all application routes on a Flask application instance.
    """

    @flask_app.route("/pull-data", methods=["POST"])
    def pull_data():
        """
        Starts the data pulling process.
        """
        global pull_thread

        if pull_thread is not None and pull_thread.is_alive():
            return jsonify(
                {
                    "busy": True,
                    "state": pull_status["state"],
                    "message": pull_status["message"],
                }
            ), 409

        authentication_event.clear()

        pull_status["state"] = "starting"
        pull_status["message"] = "Starting data pull..."

        pull_thread = threading.Thread(
            target=flask_app.config["PULL_FUNCTION"],
            daemon=True,
        )
        pull_thread.start()

        return jsonify(
            {
                "ok": True,
                "state": pull_status["state"],
                "message": pull_status["message"],
            }
        ), 200

    @flask_app.route("/resume-pull", methods=["POST"])
    def resume_pull():
        """
        Resumes the scraping process after manual authentication.
        """
        if pull_status["state"] != "authenticating":
            return jsonify(
                {
                    "ok": True,
                    "state": pull_status["state"],
                    "message": pull_status["message"],
                }
            )

        authentication_event.set()

        pull_status["state"] = "scraping"
        pull_status["message"] = "Resuming scraping..."

        return jsonify(
            {
                "ok": True,
                "state": pull_status["state"],
                "message": pull_status["message"],
            }
        )

    @flask_app.route("/pull-status")
    def pull_status_route():
        """
        Returns the current state of the data pull.
        """
        return jsonify(
            {
                "state": pull_status["state"],
                "message": pull_status["message"],
            }
        )

    @flask_app.route("/")
    @flask_app.route("/analysis")
    def index():
        """
        Displays all required analysis results.
        """

        with Session() as session:
            results = {
                "question_1": _question_1(session, print_string=False),
                "question_2": _question_2(session, print_string=False),
                "question_3": _question_3(session, print_string=False),
                "question_4": _question_4(session, print_string=False),
                "question_5": _question_5(session, print_string=False),
                "question_6": _question_6(session, print_string=False),
                "question_7": _question_7(session, print_string=False),
                "question_8": _question_8(session, print_string=False),
                "question_9": _question_9(session, print_string=False),
                "question_10": _question_10(session, print_string=False),
                "question_11": _question_11(session, print_string=False),
            }

        updated = request.args.get("updated") == "true"

        return render_template("index.html", results=results, updated=updated)

    @flask_app.route("/update-analysis", methods=["POST"])
    def update_analysis():
        if _is_pull_running():
            return jsonify(
                {
                    "busy": True,
                    "state": "busy",
                    "message": (
                        "New data is currently being retrieved. "
                        "Analysis was not refreshed."
                    ),
                }
            ), 409

        flask_app.config["UPDATE_FUNCTION"]()

        return jsonify(
            {
                "ok": True,
                "state": "ready",
                "message": (
                    "Refreshing analysis using the latest "
                    "data in PostgreSQL..."
                ),
            }
        ), 200

    @flask_app.route("/style.css")
    def style():
        """
        Retrieves the styling.
        """
        return send_from_directory(".", "style.css")


if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, use_reloader=False)