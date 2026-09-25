import os
import sys
import json
import time
import pytest
import psycopg

import src.app as app_module
from pathlib import Path
from src.llm_hosting import app as llm_app
from src.load_data import _clean_float
from src import load_data
from src.app import create_app
from src.models import Applicant, Session


@pytest.fixture
def db_connection():
    """Connect to the PostgreSQL database used by the application.

    The connection string is taken from ``load_data.DATABASE_URL`` when
    configured. Otherwise, the individual database connection settings
    from ``load_data`` are used.

    :returns: A PostgreSQL connection available to the test.
    """
    connection_string = load_data.DATABASE_URL or (
        f"host={load_data.DB_HOST} "
        f"port={load_data.DB_PORT} "
        f"dbname={load_data.DB_NAME} "
        f"user={load_data.DB_USER} "
        f"password={load_data.DB_PASSWORD}"
    )

    with psycopg.connect(connection_string) as conn:
        yield conn


@pytest.mark.integration
def _make_record(
    p_id,
    program,
    university,
    status="Accepted",
    term="Fall 2026",
    nationality="American",
    gpa="3.80",
    degree="PhD",
):
    """Create a test applicant record matching the scraper output format.

    The returned record contains representative applicant, admissions,
    academic, and already-normalized program and university fields.

    :param p_id: Unique Grad Café result identifier for the applicant.
    :param program: Applicant's program name.
    :param university: Applicant's university name.
    :param status: Applicant's admissions status.
    :param term: Applicant's intended or reported academic term.
    :param nationality: Applicant's nationality classification.
    :param gpa: Applicant's GPA as a string.
    :param degree: Applicant's degree type.
    :returns: A dictionary containing the scraper-style applicant record.
    """
    return {
        "program_name": program,
        "university": university,
        "comments": f"Test applicant {p_id}",
        "date_added": "09/01/2026",
        "url": f"https://www.thegradcafe.com/result/{p_id}",
        "applicant_status": status,
        "acceptance_date": "09/15/2026" if status == "Accepted" else None,
        "rejected_date": None,
        "wait_list_date": None,
        "interview_date": None,
        "start_term": term,
        "nationality": nationality,
        "gre_score": "165",
        "gre_v_score": "160",
        "degree_type": degree,
        "gpa": gpa,
        "gre_aw": "4.50",
        "llm-generated-program": program,
        "llm-generated-university": university,
    }


@pytest.fixture
def app(monkeypatch):
    """Create a Flask application configured for integration testing.

    The application's ``UPDATE_FUNCTION`` is replaced with a no-op because
    the analysis page calculates its results directly from the PostgreSQL
    data during rendering.

    :param monkeypatch: Pytest fixture used to replace ``UPDATE_FUNCTION``.
    :returns: A Flask test application.
    """
    monkeypatch.setattr(
        app_module,
        "UPDATE_FUNCTION",
        lambda: None,
        raising=False,
    )

    test_app = create_app(
        {
            "TESTING": True,
            "UPDATE_FUNCTION": lambda: None,
        }
    )

    return test_app


@pytest.fixture
def client(app):
    """Create a Flask test client for the integration test application.

    :param app: Flask application fixture.
    :returns: A Flask test client.
    """
    return app.test_client()


@pytest.fixture
def clean_data_file(tmp_path, monkeypatch):
    """Create an empty applicant-data file in an isolated temporary directory.

    The current working directory is changed to the temporary directory so
    that file paths used by the application remain isolated from the real
    project data.

    :param tmp_path: Pytest fixture providing a temporary directory.
    :param monkeypatch: Pytest fixture used to change the working directory.
    :returns: Path to the temporary applicant-data JSON file.
    """
    monkeypatch.chdir(tmp_path)

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    data_file = src_dir / "llm_extend_applicant_data.json"
    data_file.write_text("[]", encoding="utf-8")

    return data_file


@pytest.mark.integration
def _wait_for_pull_to_finish(client, timeout=30):
    """Wait for the background data-pull thread to reach a terminal state.

    The pull status endpoint is polled until the background operation reaches
    ``complete``, ``error``, or ``idle``. The test fails if the terminal state
    is not reached before the timeout.

    :param client: Flask test client used to query the pull-status endpoint.
    :param timeout: Maximum number of seconds to wait for completion.
    :returns: The final status dictionary returned by ``/pull-status``.
    """
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        response = client.get("/pull-status")

        assert response.status_code == 200

        status = response.get_json()

        if status["state"] in {"complete", "error", "idle"}:
            return status

        time.sleep(0.05)

    pytest.fail("Timed out waiting for the data pull to finish.")


@pytest.mark.integration
def _get_applicants():
    """Return all applicants currently stored in PostgreSQL.

    Applicants are returned in ascending order by their ``p_id`` values.

    :returns: A list of ``Applicant`` ORM objects stored in the database.
    """
    with Session() as session:
        return session.query(Applicant).order_by(Applicant.p_id).all()


@pytest.mark.integration
def test_end_to_end_pull_update_render(
    client,
    monkeypatch,
    db_connection,
    clean_data_file,
):
    """Verify the complete data-pull, cleaning, database, and analysis flow.

    The test replaces the real scraper with a fake scraper that supplies
    multiple applicant records. It then verifies that the records pass
    through the background pull process into PostgreSQL, that the analysis
    update succeeds, and that the rendered analysis contains the expected
    calculated values.

    :param client: Flask test client used to exercise application routes.
    :param monkeypatch: Pytest fixture used to replace the real scraper.
    :param db_connection: PostgreSQL connection used to inspect and restore
        database contents.
    :param clean_data_file: Temporary JSON file used by the fake scraper.
    """
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM applicants;")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.execute("TRUNCATE TABLE applicants;")
    db_connection.commit()

    records = [
        _make_record(
            p_id=900001,
            program="Computer Science",
            university="Massachusetts Institute of Technology",
            status="Accepted",
            term="Fall 2026",
            nationality="American",
            gpa="3.90",
        ),
        _make_record(
            p_id=900002,
            program="Computer Science",
            university="Stanford University",
            status="Accepted",
            term="Fall 2026",
            nationality="International (my highest degree is from outside USA)",
            gpa="3.70",
        ),
        _make_record(
            p_id=900003,
            program="Physics",
            university="West Virginia University",
            status="Rejected",
            term="Fall 2026",
            nationality="American",
            gpa="3.50",
            degree="PhD",
        ),
        _make_record(
            p_id=900004,
            program="Computer Science",
            university="Johns Hopkins University",
            status="Accepted",
            term="Fall 2026",
            nationality="American",
            gpa="3.80",
            degree="Masters",
        ),
    ]

    def fake_scraper(survey_url, authentication_event=None):
        """Write fake applicant records to the test data file.

        :param survey_url: Survey URL supplied by the application.
        :param authentication_event: Optional authentication event supplied
            by the application.
        :returns: The fake applicant records used by the integration test.
        """
        print(f"FAKE SCRAPER cwd: {os.getcwd()}")
        print(f"FAKE SCRAPER path: {clean_data_file}")
        
        with open(clean_data_file, "w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=False, indent=2)

        print(f"FILE EXISTS: {clean_data_file.exists()}")
        print(f"FILE SIZE: {clean_data_file.stat().st_size}")

        return records

    monkeypatch.setattr(
        app_module,
        "scrape_data",
        fake_scraper,
    )

    monkeypatch.setattr(
        app_module,
        "APPLICANT_DATA_FILE",
        str(clean_data_file),
    )

    response = client.post("/pull-data")

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["ok"] is True

    status = _wait_for_pull_to_finish(client)

    assert status["state"] == "complete", status
    assert status["message"] == "Data pull completed successfully."

    applicants = _get_applicants()

    assert len(applicants) == 4

    assert {applicant.p_id for applicant in applicants} == {
        900001,
        900002,
        900003,
        900004,
    }

    mit_applicant = next(
        applicant
        for applicant in applicants
        if applicant.p_id == 900001
    )

    assert mit_applicant.program == "Computer Science"
    assert (
        mit_applicant.university
        == "Massachusetts Institute of Technology"
    )
    assert mit_applicant.status == "Accepted"
    assert mit_applicant.term == "Fall 2026"

    response = client.post("/update-analysis")

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["ok"] is True
    assert response_data["state"] == "ready"

    response = client.get("/analysis")

    assert response.status_code == 200

    html = response.get_data(as_text=True)

    # Question 1:
    # All four records are Fall 2026.
    assert "Fall 2026 applicant count: 4" in html

    # Question 2:
    # One of the four records is international -> 25%.
    assert "Percent international: 25.00%" in html

    # Question 3:
    # Database averages across all four applicants.
    assert "Average GPA: 3.73" in html
    assert "Average GRE Quantitative: 165.00" in html
    assert "Average GRE Verbal: 160.00" in html
    assert "Average GRE Analytical Writing: 4.50" in html

    # Question 4:
    # American Fall 2026 GPAs are 3.90, 3.50, and 3.80.
    assert "Average Fall 2026 American applicant GPA: 3.73" in html

    # Question 6:
    # Three accepted Fall 2026 applicants, GPAs 3.90, 3.70, and 3.80.
    assert "Average Fall 2026 accepted applicant GPA: 3.80" in html

    # Question 8:
    # Two accepted Fall 2026 Computer Science PhD applicants:
    # MIT and Stanford.
    assert (
        "Fall 2026 various university Computer Science PhD "
        "acceptances: 2"
    ) in html

    with db_connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE applicants;")
        column_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))

        cursor.executemany(
            f"INSERT INTO applicants ({column_names}) VALUES ({placeholders})",
            rows
        )
    db_connection.commit()


@pytest.mark.integration
def test_multiple_pulls_are_idempotent_for_overlapping_data(
    client,
    db_connection,
    monkeypatch,
    clean_data_file,
):
    """Verify that overlapping pulls do not create duplicate applicants.

    The first pull inserts two applicants. The second pull contains one
    applicant with an existing ``p_id`` and one new applicant. The test
    verifies that the existing applicant is updated, the new applicant is
    inserted, and the total row count is three.

    :param client: Flask test client used to exercise the pull endpoint.
    :param db_connection: PostgreSQL connection used to inspect and restore
        database contents.
    :param monkeypatch: Pytest fixture used to replace the real scraper.
    :param clean_data_file: Temporary JSON file used by the fake scraper.
    """
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM applicants;")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.execute("TRUNCATE TABLE applicants;")
    db_connection.commit()

    first_pull_records = [
        _make_record(
            p_id=910001,
            program="Computer Science",
            university="Stanford University",
            status="Accepted",
            term="Fall 2026",
            gpa="3.80",
        ),
        _make_record(
            p_id=910002,
            program="Physics",
            university="West Virginia University",
            status="Rejected",
            term="Fall 2026",
            gpa="3.40",
        ),
    ]

    second_pull_records = [
        _make_record(
            p_id=910001,
            program="Computer Science",
            university="Stanford University",
            status="Rejected",
            term="Fall 2026",
            gpa="3.90",
        ),
        _make_record(
            p_id=910003,
            program="Mathematics",
            university="University of Virginia",
            status="Accepted",
            term="Fall 2026",
            gpa="3.60",
        ),
    ]

    pull_count = 0

    def fake_scraper(survey_url, authentication_event=None):
        """Return records for the current simulated pull.

        The first invocation returns the initial records and subsequent
        invocations return the overlapping and new records used to verify
        idempotent loading behavior.

        :param survey_url: Survey URL supplied by the application.
        :param authentication_event: Optional authentication event supplied
            by the application.
        :returns: Applicant records for the current simulated pull.
        """
        nonlocal pull_count

        pull_count += 1

        records = (
            first_pull_records
            if pull_count == 1
            else second_pull_records
        )

        with open(clean_data_file, "w", encoding="utf-8") as file:
            json.dump(
                records,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return records

    monkeypatch.setattr(
        app_module,
        "scrape_data",
        fake_scraper,
    )

    monkeypatch.setattr(
        app_module,
        "APPLICANT_DATA_FILE",
        str(clean_data_file),
    )

    response = client.post("/pull-data")

    assert response.status_code == 200

    status = _wait_for_pull_to_finish(client)

    assert status["state"] == "complete", status

    applicants = _get_applicants()

    assert len(applicants) == 2

    assert {applicant.p_id for applicant in applicants} == {
        910001,
        910002,
    }

    first_applicant = next(
        applicant
        for applicant in applicants
        if applicant.p_id == 910001
    )

    assert first_applicant.status == "Accepted"
    assert float(first_applicant.gpa) == pytest.approx(3.80)

    response = client.post("/pull-data")

    assert response.status_code == 200

    status = _wait_for_pull_to_finish(client)

    assert status["state"] == "complete", status

    applicants = _get_applicants()

    assert len(applicants) == 3

    assert {applicant.p_id for applicant in applicants} == {
        910001,
        910002,
        910003,
    }

    matching = [
        applicant
        for applicant in applicants
        if applicant.p_id == 910001
    ]

    assert len(matching) == 1

    updated_applicant = matching[0]

    assert updated_applicant.status == "Rejected"
    assert float(updated_applicant.gpa) == pytest.approx(3.90)

    existing_applicant = next(
        applicant
        for applicant in applicants
        if applicant.p_id == 910002
    )

    assert existing_applicant.program == "Physics"
    assert existing_applicant.university == "West Virginia University"

    new_applicant = next(
        applicant
        for applicant in applicants
        if applicant.p_id == 910003
    )

    assert new_applicant.program == "Mathematics"
    assert new_applicant.university == "University of Virginia"

    assert pull_count == 2

    with db_connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE applicants;")
        column_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))

        cursor.executemany(
            f"INSERT INTO applicants ({column_names}) VALUES ({placeholders})",
            rows
        )
    db_connection.commit()


@pytest.mark.integration
def test_load_data_invalid_p_id():
    """Verify that a record with a non-numeric result ID is rejected.

    The test supplies a result URL whose identifier is not numeric and
    verifies that ``_transform_record`` returns ``None``.

    """
    applicant = {
        "url": "https://www.thegradcafe.com/result/not-a-number",
    }

    assert load_data._transform_record(applicant) is None


@pytest.mark.integration
def test_load_data_clean_float_none():
    """Verify that cleaning a ``None`` numeric value returns ``None``."""
    assert _clean_float(None) is None


@pytest.mark.integration
def test_read_lines_missing_file():
    """Verify that reading a missing file returns an empty list."""
    assert llm_app._read_lines("definitely_missing_file_12345.txt") == []


@pytest.mark.integration
def test_load_llm_cached(monkeypatch):
    """Verify that an already-loaded LLM instance is returned unchanged.

    :param monkeypatch: Pytest fixture used to provide the cached LLM object.
    """
    cached = object()
    monkeypatch.setattr(llm_app, "_LLM", cached)

    assert llm_app._load_llm() is cached


@pytest.mark.integration
def test_load_llm_initializes(monkeypatch):
    """Verify that the LLM is initialized with the configured model settings.

    The model download and ``Llama`` constructor are replaced with test
    doubles. The test confirms that the downloaded model path and configured
    context, thread, GPU-layer, and verbosity settings are passed to the
    constructor.

    :param monkeypatch: Pytest fixture used to replace model-loading
        dependencies.
    """
    calls = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(llm_app, "_LLM", None)
    monkeypatch.setattr(
        llm_app,
        "hf_hub_download",
        lambda **kwargs: "fake-model.gguf",
    )
    monkeypatch.setattr(llm_app, "Llama", FakeLlama)

    result = llm_app._load_llm()

    assert isinstance(result, FakeLlama)
    assert calls["model_path"] == "fake-model.gguf"
    assert calls["n_ctx"] == llm_app.N_CTX
    assert calls["n_threads"] == llm_app.N_THREADS
    assert calls["n_gpu_layers"] == llm_app.N_GPU_LAYERS
    assert calls["verbose"] is False


@pytest.mark.integration
def test_best_match_branches():
    """Verify the empty-input, no-match, and exact-match branches.

    The test confirms that ``_best_match`` returns ``None`` when either
    input is empty or no candidate meets the cutoff, and returns the exact
    candidate when a valid match is found.
    """
    assert llm_app._best_match("", ["A"]) is None
    assert llm_app._best_match("A", []) is None
    assert llm_app._best_match(
        "completely different",
        ["Alpha"],
        cutoff=0.99,
    ) is None
    assert llm_app._best_match("Alpha", ["Alpha"]) == "Alpha"


@pytest.mark.integration
def test_canonical_match_branches():
    """Verify canonical matching for empty, missing, and normalized inputs."""
    assert llm_app._canonical_match("", ["Alpha"]) is None
    assert llm_app._canonical_match("Missing", ["Alpha"]) is None
    assert llm_app._canonical_match(" alpha ", ["Alpha"]) == "Alpha"


@pytest.mark.integration
def test_post_normalize_program_branches(monkeypatch):
    """Verify program normalization across canonical and fuzzy matches.

    :param monkeypatch: Pytest fixture used to provide a controlled canonical
        program list.
    """
    monkeypatch.setattr(
        llm_app,
        "CANON_PROGS",
        ["Information Studies", "Mathematics"],
    )

    assert (
        llm_app._post_normalize_program("Information Studies")
        == "Information Studies"
    )

    assert llm_app._post_normalize_program("  mathematics  ") == "Mathematics"

    assert llm_app._post_normalize_program("Mathematic") == "Mathematics"

    assert llm_app._post_normalize_program("Something Completely New") == (
        "Something Completely New"
    )


@pytest.mark.integration
def test_post_normalize_university_branches(monkeypatch):
    """Verify university normalization across matching and fallback cases.

    The test covers fuzzy abbreviations, misspellings, whitespace and
    case normalization, canonical values, unknown universities, and an
    empty input.

    :param monkeypatch: Pytest fixture used to provide a controlled canonical
        university list.
    """
    monkeypatch.setattr(
        llm_app,
        "CANON_UNIS",
        [
            "McGill University",
            "University of British Columbia",
            "University of Toronto",
        ],
    )

    assert llm_app._post_normalize_university("McG") == "McGill University"

    assert llm_app._post_normalize_university("UBC") == (
        "University of British Columbia"
    )

    assert llm_app._post_normalize_university("McGiill University") == (
        "McGill University"
    )

    assert llm_app._post_normalize_university("McGill University") == (
        "McGill University"
    )

    assert llm_app._post_normalize_university(" university of toronto ") == (
        "University of Toronto"
    )

    assert llm_app._post_normalize_university("University of Toront") == (
        "University of Toronto"
    )

    assert llm_app._post_normalize_university("Unknown University") == (
        "Unknown University"
    )

    assert llm_app._post_normalize_university("") == "Unknown"


@pytest.mark.integration
def test_call_llm_invalid_json_and_no_normalization(monkeypatch):
    """Verify that invalid LLM JSON falls back to the original input values.

    Normalization is disabled for both fields, so the original program and
    university values should be returned when the LLM response cannot be
    parsed as valid JSON.

    :param monkeypatch: Pytest fixture used to replace the LLM loader.
    """
    class FakeLLM:
        def create_chat_completion(self, **kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "this is not valid json",
                        }
                    }
                ]
            }

    monkeypatch.setattr(llm_app, "_load_llm", lambda: FakeLLM())

    result = llm_app._call_llm(
        "Original Program",
        "Original University",
        normalize_program=False,
        normalize_university=False,
    )

    assert result == {
        "standardized_program": "Original Program",
        "standardized_university": "Original University",
    }


@pytest.mark.integration
def test_call_llm_json_object_with_normalization(monkeypatch):
    """Verify that parsed LLM output is normalized against canonical values.

    The fake LLM returns an embedded JSON object containing abbreviated or
    non-canonical values. The test verifies that the returned values are
    normalized to the configured canonical program and university names.

    :param monkeypatch: Pytest fixture used to replace the LLM loader and
        canonical value lists.
    """
    class FakeLLM:
        def create_chat_completion(self, **kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                'Here is the result: '
                                '{"standardized_program": "Mathematic", '
                                '"standardized_university": "McG"}'
                            ),
                        }
                    }
                ]
            }

    monkeypatch.setattr(llm_app, "_load_llm", lambda: FakeLLM())
    monkeypatch.setattr(llm_app, "CANON_PROGS", ["Mathematics"])
    monkeypatch.setattr(llm_app, "CANON_UNIS", ["McGill University"])

    result = llm_app._call_llm(
        "Mathematic",
        "McG",
        normalize_program=True,
        normalize_university=True,
    )

    assert result == {
        "standardized_program": "Mathematics",
        "standardized_university": "McGill University",
    }


@pytest.mark.integration
def test_normalize_input_branches():
    """Verify supported input shapes and invalid-input handling.

    The test confirms that lists are returned unchanged, dictionaries with
    a list under ``rows`` are unwrapped, and invalid ``rows`` values or
    ``None`` result in an empty list.
    """
    rows = [{"program_name": "Math"}]

    assert llm_app._normalize_input(rows) is rows
    assert llm_app._normalize_input({"rows": rows}) is rows
    assert llm_app._normalize_input({"rows": "not a list"}) == []
    assert llm_app._normalize_input(None) == []


@pytest.mark.integration
def test_health_endpoint():
    """Verify that the LLM service health endpoint returns a successful response."""
    client = llm_app.app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


@pytest.mark.integration
def test_standardize_endpoint(monkeypatch):
    """Verify standardization behavior for known and unknown input values.

    Known canonical values should disable normalization when passed to the
    LLM, while unknown values should request normalization for both the
    program and university.

    :param monkeypatch: Pytest fixture used to replace the LLM call and
        canonical value lists.
    """
    calls = []

    def fake_call_llm(
        program_name,
        university,
        normalize_program,
        normalize_university,
    ):
        """Record normalization arguments and return standardized values.

        :param program_name: Program value supplied to the LLM.
        :param university: University value supplied to the LLM.
        :param normalize_program: Whether program normalization was requested.
        :param normalize_university: Whether university normalization was
            requested.
        :returns: Standardized program and university values.
        """
        calls.append(
            (
                program_name,
                university,
                normalize_program,
                normalize_university,
            )
        )
        return {
            "standardized_program": "Standard Program",
            "standardized_university": "Standard University",
        }

    monkeypatch.setattr(llm_app, "_call_llm", fake_call_llm)
    monkeypatch.setattr(llm_app, "CANON_PROGS", ["Known Program"])
    monkeypatch.setattr(llm_app, "CANON_UNIS", ["Known University"])

    client = llm_app.app.test_client()

    response = client.post(
        "/standardize",
        json={
            "rows": [
                {
                    "program_name": "Known Program",
                    "university": "Known University",
                },
                {
                    "program_name": "Unknown Program",
                    "university": "Unknown University",
                },
            ]
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["rows"][0]["llm-generated-program"] == "Standard Program"
    assert data["rows"][0]["llm-generated-university"] == "Standard University"
    assert data["rows"][1]["llm-generated-program"] == "Standard Program"
    assert data["rows"][1]["llm-generated-university"] == "Standard University"

    assert calls == [
        (
            "Known Program",
            "Known University",
            False,
            False,
        ),
        (
            "Unknown Program",
            "Unknown University",
            True,
            True,
        ),
    ]


@pytest.mark.integration
def test_cli_process_file_to_stdout(monkeypatch, tmp_path, capsys):
    """Verify that CLI file processing writes standardized records to stdout.

    :param monkeypatch: Pytest fixture used to replace the LLM call.
    :param tmp_path: Pytest fixture providing a temporary directory.
    :param capsys: Pytest fixture used to capture standard output.
    """
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "program_name": "Math",
                        "university": "JHU",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        llm_app,
        "_call_llm",
        lambda **kwargs: {
            "standardized_program": "Mathematics",
            "standardized_university": "Johns Hopkins University",
        },
    )

    llm_app._cli_process_file(
        str(input_path),
        None,
        append=False,
        to_stdout=True,
    )

    output = capsys.readouterr().out
    row = json.loads(output.strip())

    assert row["program_name"] == "Math"
    assert row["university"] == "JHU"
    assert row["llm-generated-program"] == "Mathematics"
    assert row["llm-generated-university"] == "Johns Hopkins University"


@pytest.mark.integration
def test_cli_process_file_writes_and_appends(monkeypatch, tmp_path):
    """Verify that CLI file processing writes and appends JSONL output.

    The first invocation creates the output file and writes one record. The
    second invocation uses append mode and verifies that the file then
    contains two records.

    :param monkeypatch: Pytest fixture used to replace the LLM call.
    :param tmp_path: Pytest fixture providing temporary input and output
        paths.
    """
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.jsonl"

    input_path.write_text(
        json.dumps(
            [
                {
                    "program_name": "Math",
                    "university": "JHU",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        llm_app,
        "_call_llm",
        lambda **kwargs: {
            "standardized_program": "Mathematics",
            "standardized_university": "Johns Hopkins University",
        },
    )

    llm_app._cli_process_file(
        str(input_path),
        str(output_path),
        append=False,
        to_stdout=False,
    )

    first_output = output_path.read_text(encoding="utf-8").strip()
    assert len(first_output.splitlines()) == 1

    llm_app._cli_process_file(
        str(input_path),
        str(output_path),
        append=True,
        to_stdout=False,
    )

    second_output = output_path.read_text(encoding="utf-8").strip()
    assert len(second_output.splitlines()) == 2


@pytest.mark.integration
def test_cli_process_file_default_output_path(monkeypatch, tmp_path):
    """Verify that CLI processing derives the default JSONL output path.

    :param monkeypatch: Pytest fixture used to replace the LLM call.
    :param tmp_path: Pytest fixture providing the temporary input directory.
    """
    input_path = tmp_path / "input.json"

    input_path.write_text(
        json.dumps([]),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        llm_app,
        "_call_llm",
        lambda **kwargs: {
            "standardized_program": "Program",
            "standardized_university": "University",
        },
    )

    llm_app._cli_process_file(
        str(input_path),
        None,
        append=False,
        to_stdout=False,
    )

    assert (tmp_path / "input.json.jsonl").exists()


@pytest.mark.integration
def test_cli_process_file_closes_sink_on_error(monkeypatch, tmp_path):
    """Verify that CLI processing leaves the output file available after an error.

    The LLM call is forced to raise an exception. The test verifies that the
    exception propagates while the output file has still been created.

    :param monkeypatch: Pytest fixture used to replace the LLM call.
    :param tmp_path: Pytest fixture providing temporary input and output
        paths.
    """
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.jsonl"

    input_path.write_text(
        json.dumps(
            [
                {
                    "program_name": "Math",
                    "university": "JHU",
                }
            ]
        ),
        encoding="utf-8",
    )

    def fail(**kwargs):
        """Raise a controlled error to simulate an LLM processing failure.

        :raises RuntimeError: Always raised to simulate an LLM failure.
        """
        raise RuntimeError("LLM failure")

    monkeypatch.setattr(llm_app, "_call_llm", fail)

    with pytest.raises(RuntimeError):
        llm_app._cli_process_file(
            str(input_path),
            str(output_path),
            append=False,
            to_stdout=False,
        )

    assert output_path.exists()


@pytest.mark.integration
def test_main_serve_entrypoint(monkeypatch):
    """Verify the ``--serve`` CLI entry point starts Flask with the expected settings.

    :param monkeypatch: Pytest fixture used to replace ``app.run``, modify
        command-line arguments, and configure the port environment variable.
    """
    called = {}

    def fake_run(**kwargs):
        """Record the arguments passed to the Flask application runner.

        :param kwargs: Keyword arguments supplied to ``app.run``.
        """
        called.update(kwargs)

    monkeypatch.setattr(llm_app.app, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["llm_app.py", "--serve"])
    monkeypatch.setenv("PORT", "8123")

    source = Path(llm_app.__file__).read_text(encoding="utf-8")
    entrypoint = source[source.index('if __name__ == "__main__":') :]

    namespace = {
        "__name__": "__main__",
        "__file__": llm_app.__file__,
        "app": llm_app.app,
        "os": os,
        "sys": sys,
    }

    exec(compile(entrypoint, llm_app.__file__, "exec"), namespace)

    assert called == {
        "host": "0.0.0.0",
        "port": 8123,
        "debug": False,
    }


@pytest.mark.integration
def test_main_file_entrypoint(monkeypatch, tmp_path):
    """Verify the ``--file`` CLI entry point passes the expected arguments.

    The file-processing function is replaced with a test double so that the
    test can verify the parsed input path, output path, append flag, and
    stdout flag without performing actual LLM processing.

    :param monkeypatch: Pytest fixture used to replace the file processor and
        configure command-line arguments.
    :param tmp_path: Pytest fixture providing temporary input and output paths.
    """
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.jsonl"

    input_path.write_text("[]", encoding="utf-8")

    calls = {}

    def fake_process_file(**kwargs):
        """Record the arguments passed to the CLI file processor.

        :param kwargs: Keyword arguments supplied by the CLI entry point.
        """
        calls.update(kwargs)

    monkeypatch.setattr(llm_app, "_cli_process_file", fake_process_file)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm_app.py",
            "--file",
            str(input_path),
            "--out",
            str(output_path),
            "--append",
            "--stdout",
        ],
    )

    source = Path(llm_app.__file__).read_text(encoding="utf-8")
    entrypoint = source[source.index('if __name__ == "__main__":') :]

    namespace = {
        "__name__": "__main__",
        "__file__": llm_app.__file__,
        "app": llm_app.app,
        "os": os,
        "sys": sys,
        "_cli_process_file": fake_process_file,
    }

    exec(compile(entrypoint, llm_app.__file__, "exec"), namespace)

    assert calls == {
        "in_path": str(input_path),
        "out_path": str(output_path),
        "append": True,
        "to_stdout": True,
    }