import pytest
import json
import os

from src import app as app_module, scrape, load_data
from src.app import create_app
from src.load_data import main as load_sql_data


BASE_URL = "https://www.thegradcafe.com"
RESULT_URL = f"{BASE_URL}/result/12345"
SURVEY_URL = f"{BASE_URL}/survey"

VALID_BATCH_HTML = """
<dl>
    <dd>Johns Hopkins University</dd>
    <dd>Computer Science</dd>
    <dd>PhD</dd>
    <dd>US</dd>
    <dd>Accepted</dd>
    <dd>09/23/2026</dd>
    <dd>Unused</dd>
    <dd>320</dd>
    <dd>160</dd>
    <dd>4.5</dd>
</dl>
"""

RESULT_HTML = """
<dl>
    <dd>Johns Hopkins University</dd>
    <dd>Computer Science</dd>
    <dd>PhD</dd>
    <dd>US</dd>
    <dd>Accepted</dd>
    <dd>Accepted on 09/15/2026</dd>
    <dd>Unused</dd>
    <dd>320</dd>
    <dd>160</dd>
    <dd>4.5</dd>
    <dd>Test applicant comments</dd>
</dl>
<p>Notes</p>
"""

@pytest.mark.buttons
def test_pull_data_returns_ok():
    """Verify that ``POST /pull-data`` successfully starts a data pull.

    A configured pull function is used as a lightweight stand-in for the
    real background data-pull process. The endpoint should return HTTP 200
    and a JSON response containing ``ok=True``.
    """
    def fake_pull():
        return None

    app = create_app(
        {
            "TESTING": True,
            "PULL_FUNCTION": fake_pull,
        }
    )

    with app.test_client() as client:
        response = client.post("/pull-data")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


@pytest.mark.buttons
def test_update_analysis_returns_busy_and_does_not_update():
    """Verify that analysis updates are rejected while a pull is running.

    A fake active pull thread is installed and the configured analysis
    update function is monitored. The endpoint should return HTTP 409,
    indicate that the application is busy, and avoid invoking the update
    function.
    """
    update_called = False

    def fake_update():
        nonlocal update_called
        update_called = True

    app = create_app(
        {
            "TESTING": True,
            "UPDATE_FUNCTION": fake_update,
        }
    )

    class FakeThread:
        def is_alive(self):
            return True

    app_module.pull_thread = FakeThread()

    with app.test_client() as client:
        response = client.post("/update-analysis")

    assert response.status_code == 409
    assert response.get_json()["busy"] is True
    assert update_called is False


@pytest.mark.buttons
def test_pull_data_triggers_loader_with_scraper_rows(monkeypatch, tmp_path):
    """Verify that the pull pipeline passes scraper data to the SQL loader.

    The scraper and intermediate cleaning functions are replaced with
    test doubles. The fake scraper writes applicant rows to the configured
    JSON data file, and the fake loader reads that file. The rows received
    by the loader must match the rows produced by the scraper.

    :param monkeypatch: Pytest fixture used to replace application
        dependencies.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    scraper_rows = [
        {"url": "test1"},
        {"url": "test2"},
    ]
    loaded_rows = None

    data_file = tmp_path / "llm_extend_applicant_data.json"

    def fake_scrape(*args, **kwargs):
        data_file.write_text(
            json.dumps(scraper_rows),
            encoding="utf-8",
        )

    def fake_load_clean_data(path):
        return json.loads(
            data_file.read_text(encoding="utf-8")
        )

    def fake_clean(data):
        return data

    def fake_loader():
        nonlocal loaded_rows
        loaded_rows = json.loads(
            data_file.read_text(encoding="utf-8")
        )

    monkeypatch.setattr(
        app_module,
        "APPLICANT_DATA_FILE",
        str(data_file),
    )
    monkeypatch.setattr(app_module, "scrape_data", fake_scrape)
    monkeypatch.setattr(app_module, "load_clean_data", fake_load_clean_data)
    monkeypatch.setattr(app_module, "clean_data", fake_clean)
    monkeypatch.setattr(app_module, "load_sql_data", fake_loader)

    app_module._run_pull()

    assert loaded_rows == scraper_rows


@pytest.mark.buttons
def test_pull_data_returns_busy_while_pull_is_running():
    """Verify that ``POST /pull-data`` rejects a concurrent data pull.

    When the global pull thread reports that it is still alive, the
    endpoint should return HTTP 409 with ``busy=True`` rather than starting
    another pull.
    """
    def fake_pull():
        return None

    app = create_app(
        {
            "TESTING": True,
            "PULL_FUNCTION": fake_pull,
        }
    )

    class FakeThread:
        def is_alive(self):
            return True

    app_module.pull_thread = FakeThread()

    with app.test_client() as client:
        response = client.post("/pull-data")

    assert response.status_code == 409
    assert response.get_json()["busy"] is True


@pytest.fixture(autouse=True)
def reset_pull_thread():
    """Reset the global pull thread before and after each test.

    The application stores the active pull thread in a module-level
    variable. Resetting it prevents state from one test from affecting
    another test.
    """
    app_module.pull_thread = None
    yield
    app_module.pull_thread = None


@pytest.mark.buttons
def test_update_analysis_returns_ok_when_not_busy():
    """Verify that analysis updates succeed when no pull is active.

    The endpoint should return HTTP 200 and a JSON response containing
    ``ok=True``.
    """
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.post("/update-analysis")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


@pytest.mark.buttons
def test_run_pull_completes_successfully(monkeypatch, tmp_path):
    """Verify that the pull pipeline reaches the completed state.

    Scraping and cleaning are replaced with test doubles while the real
    SQL loader is invoked with transaction rollback enabled. After the
    pipeline finishes, the global pull status should indicate successful
    completion.

    :param monkeypatch: Pytest fixture used to replace application
        dependencies.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    test_json = tmp_path / "llm_extend_applicant_data.json"

    monkeypatch.setattr(
        app_module,
        "APPLICANT_DATA_FILE",
        str(test_json),
    )

    monkeypatch.setattr(
        app_module,
        "scrape_data",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        app_module,
        "load_clean_data",
        lambda *args, **kwargs: [{"url": "test"}],
    )

    monkeypatch.setattr(
        app_module,
        "clean_data",
        lambda data: data,
    )

    monkeypatch.setattr(
        app_module,
        "load_sql_data",
        lambda: load_sql_data(rollback=True),
    )

    app_module._run_pull()

    assert app_module.pull_status["state"] == "complete"
    assert (
        app_module.pull_status["message"]
        == "Data pull completed successfully."
    )


@pytest.mark.buttons
def test_run_pull_handles_error(monkeypatch):
    """Verify that a pull exception is recorded as an error state.

    A scraper failure is injected into the pull pipeline. The global pull
    status should contain the ``error`` state and include the original
    exception message.

    :param monkeypatch: Pytest fixture used to replace the scraper.
    """
    def failing_scrape(*args, **kwargs):
        raise RuntimeError("test failure")

    monkeypatch.setattr(app_module, "scrape_data", failing_scrape)

    app_module._run_pull()

    assert app_module.pull_status["state"] == "error"
    assert app_module.pull_status["message"] == "Pull failed: test failure"


@pytest.mark.buttons
def test_pull_status_returns_status():
    """Verify that ``GET /pull-status`` returns the current pull status.

    The response should be successful and contain both ``state`` and
    ``message`` fields.
    """
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/pull-status")

    assert response.status_code == 200
    data = response.get_json()

    assert "state" in data
    assert "message" in data


@pytest.mark.buttons
def test_resume_pull_returns_ok():
    """Verify that ``POST /resume-pull`` returns a successful response.

    The endpoint should return HTTP 200 and include ``ok=True`` in its
    JSON response.
    """
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.post("/resume-pull")

    assert response.status_code == 200
    data = response.get_json()

    assert data["ok"] is True


@pytest.mark.buttons
def test_resume_pull_when_authenticating():
    """Verify that an authentication-paused pull can be resumed.

    When the pull status is ``authenticating``, the endpoint should change
    the state to ``scraping``, update the status message, and signal the
    application's authentication event.
    """
    app = create_app({"TESTING": True})

    app_module.pull_status["state"] = "authenticating"
    app_module.pull_status["message"] = "Waiting for authentication."

    with app.test_client() as client:
        response = client.post("/resume-pull")

    assert response.status_code == 200

    data = response.get_json()
    assert data["ok"] is True
    assert data["state"] == "scraping"
    assert data["message"] == "Resuming scraping..."
    assert app_module.authentication_event.is_set()

    app_module.authentication_event.clear()


@pytest.mark.web
def test_style_route():
    """Verify that the stylesheet endpoint returns CSS successfully.

    ``GET /style.css`` should return HTTP 200 with a content type beginning
    with ``text/css``.
    """
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/style.css")

    assert response.status_code == 200
    assert response.content_type.startswith("text/css")


@pytest.mark.buttons
def _mock_driver(monkeypatch):
    """Replace Chrome initialization with a lightweight fake driver.

    The helper prevents scraper tests from launching a real Chrome process
    or connecting to an actual browser.

    :param monkeypatch: Pytest fixture used to replace Chrome-related
        scraper functions.
    """
    class FakeDriver:
        def quit(self):
            pass

    monkeypatch.setattr(scrape, "_initialize_chrome", lambda url: object())
    monkeypatch.setattr(scrape, "_commandeer_chrome", lambda: FakeDriver())


@pytest.mark.buttons
def test_scrape_data_stops_when_existing_data_reached(monkeypatch, tmp_path):
    """Verify that scraping stops when an existing result boundary is reached.

    Existing applicant data contains a result URL that is encountered by
    the survey scraper. No new records should be processed, and the
    existing records should be returned unchanged.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    path = tmp_path / "data.json"
    existing = {"url": f"{BASE_URL}/result/100"}

    path.write_text(json.dumps([existing]), encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    monkeypatch.setattr(scrape, "_scrape_survey_page",
        lambda driver, url: (
            [],
            [existing["url"]],
            None,
        ),
    )

    assert scrape.scrape_data(SURVEY_URL) == [existing]


@pytest.mark.buttons
def test_scrape_data_processes_new_results(monkeypatch, tmp_path):
    """Verify that newly discovered result URLs are processed.

    The survey page supplies a new result URL and associated metadata.
    The result-processing function is mocked to return a parsed applicant
    record, which should appear in the final scraper output.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    url = f"{BASE_URL}/result/200"

    monkeypatch.setattr(scrape, "_scrape_survey_page",
        lambda driver, page: (
            [{
                "date_added": "Sep 23, 2026",
                "gpa": "3.8",
                "term": "Fall 2026",
            }],
            [url],
            None,
        ),
    )

    monkeypatch.setattr(scrape, "_process_batch",
        lambda driver, batch, existing_urls: [{
            "url": url,
            "program_name": "Computer Science",
        }],
    )

    result = scrape.scrape_data(SURVEY_URL)

    assert result[0]["url"] == url
    assert result[0]["program_name"] == "Computer Science"


@pytest.mark.buttons
def test_scrape_data_moves_to_next_page(monkeypatch, tmp_path):
    """Verify that the scraper follows survey pagination.

    The first survey page returns a second survey URL. The scraper should
    request both pages in order and stop when the second page has no next
    URL.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    first = SURVEY_URL
    second = f"{BASE_URL}/survey?page=2"
    calls = []

    def fake_scrape_page(driver, url):
        calls.append(url)

        return (
            ([], [], second)
            if url == first
            else ([], [], None)
        )

    monkeypatch.setattr(scrape, "_scrape_survey_page", fake_scrape_page)

    assert scrape.scrape_data(first) == []
    assert calls == [first, second]


@pytest.mark.buttons
def test_scrape_data_retries_after_survey_error(monkeypatch, tmp_path, capsys):
    """Verify that a survey-page failure is retried after five seconds.

    The first page request raises an exception and the second succeeds.
    The scraper should sleep for five seconds, save a checkpoint, print
    the expected error and retry messages, and ultimately return an empty
    result set.

    :param monkeypatch: Pytest fixture used to replace scraper behavior
        and the sleep function.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    :param capsys: Pytest fixture used to capture standard output.
    """
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    sleep_calls = []
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    calls = {"count": 0}

    def fake_scrape_page(driver, url):
        calls["count"] += 1

        if calls["count"] == 1:
            raise RuntimeError("temporary survey failure")

        return ([], [], None)

    monkeypatch.setattr(scrape, "_scrape_survey_page", fake_scrape_page)

    result = scrape.scrape_data(SURVEY_URL)

    assert result == []
    assert calls["count"] == 2
    assert sleep_calls == [5]

    output = capsys.readouterr().out

    assert "ERROR loading survey page 1:" in output
    assert "temporary survey failure" in output
    assert "Data checkpoint saved" in output
    assert "Retrying in 5 seconds..." in output


@pytest.mark.buttons
def test_scrape_data_skips_invalid_and_existing_urls(monkeypatch, tmp_path):
    """Verify that invalid and already processed result URLs are skipped.

    A survey page containing both an invalid URL and an existing URL should
    not cause either URL to be passed to the batch processor.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    path = tmp_path / "data.json"
    existing_url = f"{BASE_URL}/result/200"
    existing = {"url": existing_url}

    path.write_text(json.dumps([existing]), encoding="utf-8")
    monkeypatch.setattr(scrape, "data_file_name", str(path))

    _mock_driver(monkeypatch)

    monkeypatch.setattr(scrape, "_get_highest_result_id", lambda data: 100,)

    monkeypatch.setattr(scrape, "_scrape_survey_page",
        lambda driver, url: (
            [],
            ["not-a-result-url", existing_url],
            None,
        ),
    )

    monkeypatch.setattr(scrape, "_process_batch",
        lambda *args: pytest.fail("Existing URL should be skipped"),
    )

    assert scrape.scrape_data(SURVEY_URL) == [existing]


@pytest.mark.buttons
def test_scrape_data_skips_invalid_result_id(monkeypatch, tmp_path):
    """Verify that result URLs with non-numeric IDs are ignored.

    The scraper should ignore an invalid result URL while processing the
    page normally. No applicant records are expected from the mocked batch
    processor.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    valid_url = f"{BASE_URL}/result/200"
    invalid_url = f"{BASE_URL}/result/not-a-number"

    monkeypatch.setattr(scrape, "_scrape_survey_page",
        lambda driver, url: (
            [],
            [invalid_url, valid_url],
            None,
        ),
    )

    monkeypatch.setattr(scrape, "_process_batch",
        lambda driver, batch, existing_urls: [],
    )

    assert scrape.scrape_data(SURVEY_URL) == []


@pytest.mark.buttons
def test_scrape_data_stops_when_next_url_matches_current_url(monkeypatch, tmp_path, capsys):
    """Verify that repeated pagination URLs do not cause an infinite loop.

    When a survey page reports itself as its own next page, the scraper
    should stop and print a warning explaining that the repeated URL is
    preventing further pagination.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    :param capsys: Pytest fixture used to capture standard output.
    """
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    first_url = SURVEY_URL

    monkeypatch.setattr(scrape,"_scrape_survey_page",
        lambda driver, url: (
            [],
            [],
            first_url,
        ),
    )

    result = scrape.scrape_data(first_url)

    assert result == []

    output = capsys.readouterr().out

    assert "WARNING: Next URL is the same " in output
    assert "Stopping to prevent an infinite loop" in output


@pytest.mark.buttons
def test_scrape_data_stops_when_next_url_is_same(monkeypatch, tmp_path, capsys):
    """Verify that an unchanged next-page URL terminates scraping.

    This test covers the same loop-protection behavior using the current
    page URL supplied directly by the mocked survey-page scraper.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    :param capsys: Pytest fixture used to capture standard output.
    """
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    monkeypatch.setattr(scrape,"_scrape_survey_page",
        lambda driver, url: (
            [],
            [],
            url,
        ),
    )

    assert scrape.scrape_data(SURVEY_URL) == []

    output = capsys.readouterr().out

    assert "WARNING: Next URL is the same as the current URL" in output
    assert "Stopping to prevent an infinite loop" in output


@pytest.mark.buttons
def test_scrape_data_waits_for_authentication(monkeypatch, tmp_path):
    """Verify that scraping waits for a supplied authentication event.

    A fake authentication event records whether its ``wait()`` method was
    called. The scraper should wait for the event before processing the
    survey page.

    :param monkeypatch: Pytest fixture used to replace scraper behavior.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    class FakeAuthenticationEvent:
        def __init__(self):
            self.wait_called = False

        def wait(self):
            self.wait_called = True

    event = FakeAuthenticationEvent()

    monkeypatch.setattr(scrape, "_scrape_survey_page",
        lambda driver, url: (
            [],
            [],
            None,
        ),
    )

    assert scrape.scrape_data(SURVEY_URL, authentication_event=event) == []

    assert event.wait_called is True


@pytest.mark.buttons
def test_new_applicant_item_defaults():
    """Verify the default structure of a newly created applicant record.

    The scraper's empty applicant record should contain exactly 17 fields,
    with every value initialized to ``None``.
    """
    item = scrape._new_applicant_item()

    assert len(item) == 17
    assert all(value is None for value in item.values())

    for key in ["program_name", "university", "gre_score", "gpa"]:
        assert item[key] is None


@pytest.mark.buttons
def test_scrape_load_data(tmp_path, monkeypatch):
    """Verify loading and validation of the scraper's JSON data file.

    A missing file should produce an empty list. A JSON list should be
    returned unchanged, while a dictionary-shaped document should raise a
    ``ValueError``.

    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    :param monkeypatch: Pytest fixture used to configure the scraper's
        data-file path.
    """
    path = tmp_path / "applicants.json"
    monkeypatch.setattr(scrape, "data_file_name", str(path))

    assert scrape._load_data() == []

    data = [{"url": f"{BASE_URL}/result/12345"}]
    path.write_text(json.dumps(data), encoding="utf-8")

    assert scrape._load_data() == data

    path.write_text(json.dumps({"rows": data}), encoding="utf-8")

    with pytest.raises(ValueError, match="Applicant data must be a list of records."):
        scrape._load_data()


@pytest.mark.buttons
def test_scrape_save_data(tmp_path, monkeypatch):
    """Verify that applicant data is persisted as valid JSON.

    The saved JSON should contain the supplied records, and the temporary
    ``.tmp`` file used during saving should not remain after the operation.

    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    :param monkeypatch: Pytest fixture used to configure the scraper's
        data-file path.
    """
    path = tmp_path / "applicants.json"
    monkeypatch.setattr(scrape, "data_file_name", str(path))

    data = [
        {"url": f"{BASE_URL}/result/12345"},
        {"url": f"{BASE_URL}/result/12346"},
    ]

    scrape.save_data(data)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert not (tmp_path / "applicants.json.tmp").exists()


@pytest.mark.buttons
@pytest.mark.parametrize(
    "url, expected",
    [
        (f"{BASE_URL}/result/12345", 12345),
        ("", None),
        (None, None),
        (f"{BASE_URL}/result/abc", None),
        (f"{BASE_URL}/result/12345/", None),
    ],
)
def test_scrape_get_result_id(url, expected):
    """Verify extraction and validation of Grad Cafe result IDs.

    Valid result URLs should return their numeric ID. Empty, ``None``,
    non-numeric, and trailing-slash URLs should return ``None``.

    :param url: Result URL supplied to the parser.
    :type url: str or None
    :param expected: Expected numeric result ID or ``None``.
    :type expected: int or None
    """
    assert scrape._get_result_id(url) == expected


@pytest.mark.buttons
def test_scrape_get_highest_result_id():
    """Verify that the highest valid result ID is selected.

    Invalid URLs and missing URL values should be ignored. An empty data
    collection should produce ``0``.
    """
    data = [
        {"url": f"{BASE_URL}/result/123"},
        {"url": f"{BASE_URL}/result/456"},
        {"url": f"{BASE_URL}/result/789"},
        {"url": None},
        {"url": "not-a-result-url"},
    ]

    assert scrape._get_highest_result_id(data) == 789
    assert scrape._get_highest_result_id([]) == 0


@pytest.mark.buttons
def test_scrape_initialize_chrome(monkeypatch):
    """Verify the Chrome command used by the scraper.

    ``subprocess.Popen`` is replaced with a fake implementation so the test
    can inspect the exact command-line arguments used to start Chrome.

    :param monkeypatch: Pytest fixture used to replace ``subprocess.Popen``.
    """
    captured = {}

    class FakeProcess:
        pass

    monkeypatch.setattr(scrape.subprocess, "Popen",
        lambda command: (
            captured.update(command=command) or FakeProcess()
        ),
    )

    process = scrape._initialize_chrome("https://example.com", port=9999)

    assert isinstance(process, FakeProcess)
    assert captured["command"] == [
        scrape.chrome_path,
        "--remote-debugging-port=9999",
        f"--user-data-dir={scrape.chrome_profile}",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
        "https://example.com",
    ]


@pytest.mark.buttons
def test_scrape_commandeer_chrome(monkeypatch):
    """Verify Selenium's connection to the remote Chrome debugger.

    The test confirms that the configured debugger address uses the
    requested port and that Selenium is configured with an eager page-load
    strategy.

    :param monkeypatch: Pytest fixture used to replace Selenium's Chrome
        constructor.
    """
    captured = {}

    class FakeDriver:
        pass

    def fake_chrome(options):
        captured["options"] = options
        return FakeDriver()

    monkeypatch.setattr(scrape.webdriver, "Chrome", fake_chrome)

    driver = scrape._commandeer_chrome(port=9999)

    assert isinstance(driver, FakeDriver)
    assert (
        captured["options"]
        .experimental_options["debuggerAddress"]
        == "127.0.0.1:9999"
    )
    assert captured["options"].page_load_strategy == "eager"


@pytest.mark.buttons
def test_scrape_survey_page():
    """Verify parsing of survey-page metadata, result URLs, and pagination.

    The fake survey page contains applicant metadata rows, result links,
    and a next-page link. The parser should extract dates, GPAs, terms,
    absolute result URLs, and the next survey URL while skipping an
    incomplete row.
    """
    class FakeDriver:
        page_source = """
        <table>
            <tr>
                <td>A</td><td>B</td>
                <td>Sep 23, 2026</td>
                <td>D</td><td>E</td>
            </tr>
            <tr><td>GPA 3.85 Fall 2026</td></tr>
            <tr>
                <td>A</td><td>B</td>
                <td>Sep 22, 2026</td>
                <td>D</td><td>E</td>
            </tr>
            <tr><td>GPA 3.70</td></tr>
            <tr>
                <td>Only three cells</td>
                <td>Not enough</td>
                <td>cells</td>
            </tr>
        </table>
        <a href="/result/12345">Result 1</a>
        <a href="/result/12346">Result 2</a>
        <a href="/survey?page=2">Next</a>
        """

        def get(self, url):
            self.requested_url = url

    driver = FakeDriver()

    info, results, next_url = scrape._scrape_survey_page(driver, SURVEY_URL)

    assert driver.requested_url == SURVEY_URL
    assert info == [
        {
            "date_added": "Sep 23, 2026",
            "gpa": "3.85",
            "term": "Fall 2026",
        },
        {
            "date_added": "Sep 22, 2026",
            "gpa": "3.70",
            "term": None,
        },
    ]
    assert results == [
        f"{BASE_URL}/result/12345",
        f"{BASE_URL}/result/12346",
    ]
    assert next_url == f"{BASE_URL}/survey?page=2"


@pytest.mark.buttons
def test_scrape_survey_page_skips_row_without_sibling():
    """Verify that incomplete survey rows are ignored.

    A survey row without the expected sibling metadata row should not
    produce applicant information, result URLs, or a pagination URL.
    """
    class FakeDriver:
        page_source = """
        <table>
            <tr>
                <td>A</td><td>B</td>
                <td>Sep 23, 2026</td>
                <td>D</td><td>E</td>
            </tr>
        </table>
        """

        def get(self, url):
            self.requested_url = url

    info, results, next_url = scrape._scrape_survey_page(FakeDriver(), SURVEY_URL)

    assert info == []
    assert results == []
    assert next_url is None


@pytest.mark.buttons
def test_scrape_result_page_html():
    """Verify extraction of applicant fields from a result page.

    The parser should extract university, program, degree, nationality,
    status, acceptance date, GRE values, GPA, term, date added, URL, and
    comments from the supplied result-page HTML.
    """
    result = scrape._scrape_result_page_html(
        RESULT_HTML,
        RESULT_URL,
        date_added="Sep 23, 2026",
        gpa="3.8",
        start_term="Fall 2026",
    )

    expected = {
        "university": "Johns Hopkins University",
        "program_name": "Computer Science",
        "degree_type": "PhD",
        "nationality": "US",
        "applicant_status": "Accepted",
        "acceptance_date": "09/15/2026",
        "gre_score": "320",
        "gre_v_score": "160",
        "gre_aw": "4.5",
        "gpa": "3.8",
        "start_term": "Fall 2026",
        "date_added": "09/23/2026",
        "url": RESULT_URL,
        "comments": "Test applicant comments",
    }

    for key, value in expected.items():
        assert result[key] == value


@pytest.mark.buttons
@pytest.mark.parametrize(
    "status, expected_key",
    [
        ("Rejected", "rejected_date"),
        ("Wait listed", "wait_list_date"),
        ("Interview", "interview_date"),
    ],
)
def test_scrape_result_page_html_status_dates(status, expected_key):
    """Verify extraction of status-specific dates.

    Rejected, wait-listed, and interview statuses should store their
    associated date under the corresponding status-specific field.

    :param status: Applicant status represented in the result page.
    :param expected_key: Dictionary key where the status date should be
        stored.
    """
    html = f"""
    <dl>
        <dd>University</dd>
        <dd>Program</dd>
        <dd>PhD</dd>
        <dd>US</dd>
        <dd>{status}</dd>
        <dd>Status date 09/15/2026</dd>
        <dd>Unused</dd>
        <dd>320</dd>
        <dd>160</dd>
        <dd>4.5</dd>
    </dl>
    """

    result = scrape._scrape_result_page_html(html, RESULT_URL)

    assert result[expected_key] == "09/15/2026"


@pytest.mark.buttons
def test_scrape_result_page_html_edge_cases():
    """Verify handling of missing dates and invalid numeric values.

    An invalid acceptance date should produce ``None`` for the acceptance
    date, while an explicitly supplied invalid ``date_added`` value is
    preserved. Invalid GRE values should also become ``None``.
    """
    html = """
    <dl>
        <dd>University</dd>
        <dd>Program</dd>
        <dd>PhD</dd>
        <dd>US</dd>
        <dd>Accepted</dd>
        <dd>No date here</dd>
        <dd>Unused</dd>
        <dd>Not provided</dd>
        <dd>Not provided</dd>
        <dd>Not provided</dd>
    </dl>
    """

    result = scrape._scrape_result_page_html(
        html,
        RESULT_URL,
        date_added="not a date",
    )

    assert result["acceptance_date"] is None
    assert result["date_added"] == "not a date"

    for key in ["gre_score", "gre_v_score", "gre_aw"]:
        assert result[key] is None


@pytest.mark.buttons
def test_scrape_result_page_html_rejects_unexpected_structure():
    """Verify that malformed result-page HTML raises ``ValueError``.

    HTML that does not contain the expected applicant result-page
    structure should be rejected with an error identifying the unexpected
    structure.
    """
    with pytest.raises(
        ValueError,
        match="Unexpected result page structure",
    ):
        scrape._scrape_result_page_html(
            "<html><body><dd>Only one field</dd></body></html>",
            RESULT_URL,
        )


@pytest.mark.buttons
def test_fetch_pages_in_browser():
    """Verify that multiple result pages are fetched in the browser.

    The browser's asynchronous JavaScript execution should receive the
    requested URLs and use ``Promise.all`` to fetch them concurrently.
    The returned browser results should preserve the URL, status, and HTML
    for each request.
    """
    class FakeDriver:
        def execute_async_script(self, script, urls):
            self.script = script
            self.urls = urls
            return [
                {"url": url, "status": 200, "html": "<html></html>"}
                for url in urls
            ]

    urls = [
        f"{BASE_URL}/result/12345",
        f"{BASE_URL}/result/12346",
    ]

    driver = FakeDriver()

    assert scrape._fetch_pages_in_browser(driver, urls) == [
        {"url": urls[0], "status": 200, "html": "<html></html>"},
        {"url": urls[1], "status": 200, "html": "<html></html>"},
    ]

    assert driver.urls == urls
    assert "Promise.all" in driver.script


@pytest.mark.buttons
def test_fetch_pages_in_browser_empty_urls():
    """Verify that an empty URL collection avoids browser execution.

    No asynchronous browser script should be executed when there are no
    result URLs to fetch.
    """
    class FakeDriver:
        def execute_async_script(self, *args):
            raise AssertionError("Browser script should not run")

    assert scrape._fetch_pages_in_browser(FakeDriver(), []) == []


@pytest.mark.buttons
def test_process_batch_adds_valid_records(monkeypatch):
    """Verify that valid result pages become applicant records.

    A successful browser response containing valid result-page HTML should
    be parsed into an applicant record. The processed URL should also be
    added to the set of existing URLs.

    :param monkeypatch: Pytest fixture used to replace browser fetching.
    """
    batch = [{
        "url": RESULT_URL,
        "date_added": "Sep 23, 2026",
        "gpa": "3.8",
        "term": "Fall 2026",
    }]

    monkeypatch.setattr(scrape,"_fetch_pages_in_browser",
        lambda driver, urls: [{
            "url": urls[0],
            "status": 200,
            "html": VALID_BATCH_HTML,
        }],
    )

    existing_urls = set()

    records = scrape._process_batch(object(), batch, existing_urls)

    assert len(records) == 1
    assert records[0]["url"] == RESULT_URL
    assert records[0]["program_name"] == "Computer Science"
    assert RESULT_URL in existing_urls


@pytest.mark.buttons
def test_process_batch_skips_failed_and_existing_records(monkeypatch, capsys):
    """Verify that failed HTTP requests and existing records are skipped.

    An already processed URL should not produce a new record. A result
    page returning HTTP 500 should also be skipped and reported to standard
    output.

    :param monkeypatch: Pytest fixture used to replace browser fetching.
    :param capsys: Pytest fixture used to capture standard output.
    """
    existing_url = f"{BASE_URL}/result/11111"
    failed_url = f"{BASE_URL}/result/22222"

    batch = [
        {
            "url": existing_url,
            "date_added": None,
            "gpa": None,
            "term": None,
        },
        {
            "url": failed_url,
            "date_added": None,
            "gpa": None,
            "term": None,
        },
    ]

    monkeypatch.setattr(scrape,"_fetch_pages_in_browser",
        lambda driver, urls: [
            {
                "url": existing_url,
                "status": 200,
                "html": "<html>ignored</html>",
            },
            {
                "url": failed_url,
                "status": 500,
                "html": None,
            },
        ],
    )

    assert scrape._process_batch(object(), batch, {existing_url}) == []

    output = capsys.readouterr().out

    assert "FAILED:" in output
    assert "(HTTP 500)" in output


@pytest.mark.buttons
def test_process_batch_skips_parse_errors(monkeypatch, capsys):
    """Verify that malformed result pages are skipped after fetch.

    A successful HTTP response containing invalid result-page HTML should
    not produce an applicant record. The parser failure should be reported
    as a parse error containing the affected URL.

    :param monkeypatch: Pytest fixture used to replace browser fetching.
    :param capsys: Pytest fixture used to capture standard output.
    """
    url = f"{BASE_URL}/result/33333"

    monkeypatch.setattr(
        scrape,
        "_fetch_pages_in_browser",
        lambda driver, urls: [{
            "url": url,
            "status": 200,
            "html": "<html>invalid result page</html>",
        }],
    )

    assert scrape._process_batch(object(),
        [{
            "url": url,
            "date_added": None,
            "gpa": None,
            "term": None,
        }],
        set(),
    ) == []

    output = capsys.readouterr().out

    assert "PARSE ERROR:" in output
    assert url in output


@pytest.mark.integration
def test_main_rolls_back_on_exception(monkeypatch, tmp_path):
    """
    Verify that ``main`` rolls back the database transaction when an
    exception occurs during database processing.

    The test replaces the database connection with a fake connection whose
    cursor raises a ``RuntimeError``. It verifies that ``main`` re-raises the
    exception and calls ``rollback`` on the database connection.

    :param monkeypatch: Pytest fixture used to replace module dependencies.
    :type monkeypatch: pytest.MonkeyPatch
    :param tmp_path: Pytest fixture providing a temporary directory for the
        test input JSON file.
    :type tmp_path: pathlib.Path
    :raises AssertionError: If the transaction is not rolled back or if
        ``commit`` is called.
    """

    data_file = tmp_path / "applicants.json"
    data_file.write_text(
        json.dumps(
            [
                {
                    "url": "https://www.thegradcafe.com/result/12345",
                    "program_name": "Computer Science",
                    "university": "Johns Hopkins University",
                }
            ]
        ),
        encoding="utf-8",
    )

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, *args, **kwargs):
            raise RuntimeError("database error")

    class FakeConnection:
        def __init__(self):
            self.rollback_called = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rollback_called = True

        def commit(self):
            raise AssertionError("commit should not be called")

    connection = FakeConnection()

    monkeypatch.setattr(load_data, "DATA_FILE", str(data_file))
    monkeypatch.setattr(load_data, "DATABASE_URL", "fake-database-url")
    monkeypatch.setattr(
        load_data.psycopg,
        "connect",
        lambda connection_string: connection,
    )

    with pytest.raises(RuntimeError, match="database error"):
        load_data.main()

    assert connection.rollback_called

@pytest.mark.buttons
def test_run_pull_restores_missing_data_file(monkeypatch, tmp_path):
    """
    Verify that DATA_FILE is removed when it was not set before the pull.

    The test replaces the scraper, cleaning functions, and SQL loader with
    test doubles, then runs the pull pipeline with DATA_FILE initially absent.
    After the pull completes, DATA_FILE should be removed from the environment
    rather than leaving the temporary applicant data path behind.

    :param monkeypatch: Pytest fixture used to replace application
        dependencies and modify environment variables.
    :param tmp_path: Pytest fixture providing a temporary filesystem path.
    """
    data_file = tmp_path / "llm_extend_applicant_data.json"

    monkeypatch.delenv("DATA_FILE", raising=False)

    monkeypatch.setattr(
        app_module,
        "APPLICANT_DATA_FILE",
        str(data_file),
    )

    monkeypatch.setattr(
        app_module,
        "scrape_data",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        app_module,
        "load_clean_data",
        lambda *args, **kwargs: [{"url": "test"}],
    )

    monkeypatch.setattr(
        app_module,
        "clean_data",
        lambda data: data,
    )

    monkeypatch.setattr(
        app_module,
        "load_sql_data",
        lambda: None,
    )

    app_module._run_pull()

    assert "DATA_FILE" not in os.environ
    assert app_module.pull_status["state"] == "complete"