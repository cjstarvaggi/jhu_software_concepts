import pytest
import json

from src import app as app_module, scrape
from src.app import create_app
from src.load_data import main as load_sql_data


BASE_URL = "https://www.thegradcafe.com"
RESULT_URL = f"{BASE_URL}/result/12345"
SURVEY_URL = f"{BASE_URL}/survey"


@pytest.mark.buttons
def test_pull_data_returns_ok():
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
    app_module.pull_thread = None
    yield
    app_module.pull_thread = None


@pytest.mark.buttons
def test_update_analysis_returns_ok_when_not_busy():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.post("/update-analysis")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


@pytest.mark.buttons
def test_run_pull_completes_successfully(monkeypatch, tmp_path):
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

    # Use the REAL database loader, but roll back its transaction.
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
    def failing_scrape(*args, **kwargs):
        raise RuntimeError("test failure")

    monkeypatch.setattr(app_module, "scrape_data", failing_scrape)

    app_module._run_pull()

    assert app_module.pull_status["state"] == "error"
    assert app_module.pull_status["message"] == "Pull failed: test failure"


@pytest.mark.buttons
def test_pull_status_returns_status():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/pull-status")

    assert response.status_code == 200
    data = response.get_json()

    assert "state" in data
    assert "message" in data


@pytest.mark.buttons
def test_resume_pull_returns_ok():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.post("/resume-pull")

    assert response.status_code == 200
    data = response.get_json()

    assert data["ok"] is True


@pytest.mark.buttons
def test_resume_pull_when_authenticating():
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
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/style.css")

    assert response.status_code == 200
    assert response.content_type.startswith("text/css")

@pytest.mark.buttons
def _mock_driver(monkeypatch):
    class FakeDriver:
        def quit(self):
            pass

    monkeypatch.setattr(scrape, "_initialize_chrome", lambda url: object())
    monkeypatch.setattr(scrape, "_commandeer_chrome", lambda: FakeDriver())

@pytest.mark.buttons
def test_scrape_data_stops_when_existing_data_reached(monkeypatch, tmp_path):
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

    monkeypatch.setattr(scrape, "_scrape_survey_page",fake_scrape_page)

    assert scrape.scrape_data(first) == []
    assert calls == [first, second]


@pytest.mark.buttons
def test_scrape_data_retries_after_survey_error(monkeypatch, tmp_path, capsys):
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
def test_scrape_data_stops_when_next_url_is_same(monkeypatch, tmp_path,capsys):
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(scrape, "data_file_name", str(path))
    _mock_driver(monkeypatch)

    monkeypatch.setattr(scrape, "_scrape_survey_page",
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
    item = scrape._new_applicant_item()

    assert len(item) == 17
    assert all(value is None for value in item.values())

    for key in ["program_name", "university", "gre_score", "gpa"]:
        assert item[key] is None

@pytest.mark.buttons
def test_scrape_load_data(tmp_path, monkeypatch):
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
    assert scrape._get_result_id(url) == expected

@pytest.mark.buttons
def test_scrape_get_highest_result_id():
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
def test_scrape_result_page_html():
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


@pytest.mark.parametrize(
    "status, expected_key",
    [
        ("Rejected", "rejected_date"),
        ("Wait listed", "wait_list_date"),
        ("Interview", "interview_date"),
    ],
)
def test_scrape_result_page_html_status_dates(status, expected_key):
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
    class FakeDriver:
        def execute_async_script(self, *args):
            raise AssertionError("Browser script should not run")

    assert scrape._fetch_pages_in_browser(FakeDriver(), []) == []


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

@pytest.mark.buttons
def test_process_batch_adds_valid_records(monkeypatch):
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
