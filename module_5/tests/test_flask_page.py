import pytest

from src.app import create_app


@pytest.mark.web
def test_app_factory_and_routes():
    """Verify that the Flask application factory registers all required routes.

    The application is created in testing mode and its URL map is inspected
    to ensure that the data-pull, authentication-resume, status, analysis,
    analysis-update, and stylesheet routes are registered.
    """
    app = create_app({"TESTING": True})

    assert app.testing is True

    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/pull-data" in routes
    assert "/resume-pull" in routes
    assert "/pull-status" in routes
    assert "/analysis" in routes
    assert "/update-analysis" in routes
    assert "/style.css" in routes


@pytest.mark.web
def test_analysis_page_loads():
    """Verify that the analysis page renders successfully.

    The test checks that the ``/analysis`` endpoint returns a successful
    response containing the page title, data-pull and analysis-update
    controls, answer output, and the expected ``data-testid`` attributes.
    """
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/analysis")

    assert response.status_code == 200
    assert b"Analysis" in response.data
    assert b"Pull Data" in response.data
    assert b"Update Analysis" in response.data
    assert b"Answer:" in response.data
    assert b'data-testid="pull-data-btn"' in response.data
    assert b'data-testid="update-analysis-btn"' in response.data


@pytest.mark.web
def test_app_main_block(monkeypatch):
    """Verify that the Flask application's main entry point executes.

    ``Flask.run`` is replaced with a no-op so that executing ``src/app.py``
    as ``__main__`` does not start a development server. The test confirms
    that the module's main block can therefore be executed successfully.

    :param monkeypatch: Pytest fixture used to replace ``Flask.run``.
    """
    monkeypatch.setattr(
        "flask.Flask.run",
        lambda self, **kwargs: None,
    )

    app_path = "src/app.py"

    with open(app_path, encoding="utf-8") as file:
        source = file.read()

    exec(
        compile(source, app_path, "exec"),
        {
            "__name__": "__main__",
            "__file__": app_path,
        },
    )