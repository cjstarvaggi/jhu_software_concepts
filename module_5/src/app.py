"""Flask application for applicant data collection and analysis."""

import json
import os
import threading

from flask import Flask, jsonify, render_template, request, send_from_directory

from clean import clean_data, load_data as load_clean_data
import load_data
from load_data import main as load_sql_data
from models import SESSION_FACTORY
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
from scrape import scrape_data, SURVEY_URL

APPLICANT_DATA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "llm_extend_applicant_data.json",
)

pull_status = {
    "state": "idle",
    "message": "Ready to pull data.",
}

pull_runtime = {
    "thread": None,
}

authentication_event = threading.Event()


def create_app(test_config=None):
    """
    Create and configure the Flask application.

    :param test_config: Optional configuration values to apply to the Flask
        application.
    :type test_config: dict or None
    :returns: Configured Flask application instance.
    :rtype: flask.Flask
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
    """
    Run the complete applicant data-pull pipeline.

    The pipeline scrapes applicant data, waits for manual authentication,
    cleans the resulting data, writes the cleaned data to JSON, and loads
    it into PostgreSQL.
    """
    try:
        pull_status["state"] = "authenticating"
        pull_status["message"] = (
            "Chrome opened. Complete Cloudflare authentication, "
            "then click Resume Pulling."
        )

        print("SCRAPE MODULE:", scrape_data.__module__)
        print("SCRAPE FILE:", scrape_data.__code__.co_filename)

        scrape_data(
            SURVEY_URL,
            authentication_event=authentication_event,
            data_file=APPLICANT_DATA_FILE,
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
        pull_status["message"] = "Loading new applicant data into PostgreSQL..."

        previous_data_file = load_data.DATA_FILE

        try:
            load_data.DATA_FILE = APPLICANT_DATA_FILE
            load_sql_data()
        finally:
            load_data.DATA_FILE = previous_data_file

        pull_status["state"] = "complete"
        pull_status["message"] = "Data pull completed successfully."

    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        pull_status["state"] = "error"
        pull_status["message"] = f"Pull failed: {exc}"

    finally:
        authentication_event.clear()


def _is_pull_running():
    """
    Check whether the data-pull background thread is currently running.

    :returns: True when a pull thread exists and is alive; otherwise False.
    :rtype: bool
    """
    thread = pull_runtime["thread"]
    return thread is not None and thread.is_alive()


def register_routes(flask_app):
    """
    Register all application routes on a Flask application instance.

    :param flask_app: Flask application instance.
    :type flask_app: flask.Flask
    :returns: None
    :rtype: None
    """

    @flask_app.route("/pull-data", methods=["POST"])
    def pull_data():
        """
        Start the applicant data-pull process in a background thread.

        :returns: JSON response describing whether the pull was started.
        :rtype: tuple[flask.Response, int]
        """
        if _is_pull_running():
            return (
                jsonify(
                    {
                        "busy": True,
                        "state": pull_status["state"],
                        "message": pull_status["message"],
                    }
                ),
                409,
            )

        authentication_event.clear()

        pull_status["state"] = "starting"
        pull_status["message"] = "Starting data pull..."

        pull_runtime["thread"] = threading.Thread(
            target=flask_app.config["PULL_FUNCTION"],
            daemon=True,
        )
        pull_runtime["thread"].start()

        return (
            jsonify(
                {
                    "ok": True,
                    "state": pull_status["state"],
                    "message": pull_status["message"],
                }
            ),
            200,
        )

    @flask_app.route("/resume-pull", methods=["POST"])
    def resume_pull():
        """
        Resume the scraping process after manual authentication.

        :returns: JSON response containing the current or resumed pull state.
        :rtype: flask.Response
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
        Return the current state and status message for the data pull.

        :returns: JSON response containing the current pull state.
        :rtype: flask.Response
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
        Display the applicant analysis results.

        All eleven ORM analysis queries are executed using a shared
        SQLAlchemy session.
        """
        with SESSION_FACTORY() as session:
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

        return render_template(
            "index.html",
            results=results,
            updated=updated,
        )

    @flask_app.route("/update-analysis", methods=["POST"])
    def update_analysis():
        """
        Refresh the analysis using the latest PostgreSQL data.

        :returns: JSON response indicating whether the refresh was started.
        :rtype: tuple[flask.Response, int]
        """
        if _is_pull_running():
            return (
                jsonify(
                    {
                        "busy": True,
                        "state": "busy",
                        "message": (
                            "New data is currently being retrieved. "
                            "Analysis was not refreshed."
                        ),
                    }
                ),
                409,
            )

        flask_app.config["UPDATE_FUNCTION"]()

        return (
            jsonify(
                {
                    "ok": True,
                    "state": "ready",
                    "message": (
                        "Refreshing analysis using the latest " "data in PostgreSQL..."
                    ),
                }
            ),
            200,
        )

    @flask_app.route("/style.css")
    def style():
        """
        Serve the application's CSS stylesheet.

        :returns: The application's CSS stylesheet.
        :rtype: flask.Response
        """
        return send_from_directory(".", "style.css")


if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, use_reloader=False)
