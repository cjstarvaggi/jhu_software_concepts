import json
import pytest
import psycopg

from sqlalchemy import text

from datetime import date
from src.models import Session
from src.load_data import _get_p_id, _transform_record, _clean_float
from src import clean, load_data
from src.models import Session
import src.orm_queries as orm_queries


BASE_URL = "https://www.thegradcafe.com"
RESULT_URL = f"{BASE_URL}/result/12345"
SURVEY_URL = f"{BASE_URL}/survey"
REQUIRED_FIELDS = [
    "p_id",
    "program",
    "university",
    "comments",
    "date_added",
    "url",
    "status",
    "term",
    "us_or_international",
    "gpa",
    "gre",
    "gre_v",
    "gre_aw",
    "degree",
    "llm_generated_program",
    "llm_generated_university",
]


@pytest.fixture
@pytest.mark.db
def db_connection():
    """Connect to the PostgreSQL database used by the application.

    :returns: A PostgreSQL connection configured from the application's
        database settings.
    :rtype: psycopg.Connection
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


@pytest.mark.db
def test_insert_on_pull(db_connection, monkeypatch, tmp_path):
    """Verify that a valid applicant record is inserted into PostgreSQL.

    The test writes a valid applicant record to a temporary JSON file,
    runs the database loader, and verifies that the transformed record
    is inserted into the ``applicants`` table with all expected fields
    populated.

    :param db_connection: Connection to the application's PostgreSQL
        database.
    :param monkeypatch: Pytest fixture used to replace the application's
        input data path.
    :param tmp_path: Temporary directory used for the applicant JSON file.
    """
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM applicants;")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.execute("TRUNCATE TABLE applicants;")
    db_connection.commit()

    applicant_data = [
        {
            "url": "https://www.thegradcafe.com/result/123456",
            "program_name": "Computer Science",
            "university": "Example University",
            "comments": "Test applicant",
            "date_added": "09/24/2026",
            "applicant_status": "Accepted",
            "start_term": "Fall 2026",
            "nationality": "American",
            "gpa": "3.8",
            "gre_score": "320",
            "gre_v_score": "160",
            "gre_aw": "4.5",
            "degree_type": "PhD",
            "llm-generated-program": "Computer Science",
            "llm-generated-university": "Example University",
        }
    ]

    data_file = tmp_path / "applicants.json"
    data_file.write_text(json.dumps(applicant_data), encoding="utf-8")

    monkeypatch.setattr(load_data, "DATA_FILE", str(data_file))

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM applicants;")
        assert cursor.fetchone()[0] == 0

    load_data.main()

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM applicants;")
        assert cursor.fetchone()[0] == 1

        cursor.execute(
            """
            SELECT
                p_id,
                program,
                university,
                comments,
                date_added,
                url,
                status,
                term,
                us_or_international,
                gpa,
                gre,
                gre_v,
                gre_aw,
                degree,
                llm_generated_program,
                llm_generated_university
            FROM applicants
            WHERE p_id = 123456;
            """
        )

        row = cursor.fetchone()

    assert row is not None
    assert all(value is not None for value in row)

    with db_connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE applicants;")
        column_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))

        cursor.executemany(
            f"INSERT INTO applicants ({column_names}) VALUES ({placeholders})",
            rows
        )
    db_connection.commit()


@pytest.mark.db
def test_duplicate_pull_does_not_create_duplicates(
    db_connection, monkeypatch, tmp_path
):
    """Verify that loading the same applicant twice does not duplicate it.

    The applicant data is loaded twice using the same ``p_id``.  The test
    verifies that only one database row exists for that applicant after
    both loads.

    :param db_connection: Connection to the application's PostgreSQL
        database.
    :param monkeypatch: Pytest fixture used to replace the input data path.
    :param tmp_path: Temporary directory used for the applicant JSON file.
    """
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM applicants;")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.execute("TRUNCATE TABLE applicants;")
    db_connection.commit()

    applicant_data = [
        {
            "url": "https://www.thegradcafe.com/result/123456",
            "program_name": "Computer Science",
            "university": "Example University",
            "comments": "Test applicant",
            "date_added": "09/24/2026",
            "applicant_status": "Accepted",
            "start_term": "Fall 2026",
            "nationality": "American",
            "gpa": "3.8",
            "gre_score": "320",
            "gre_v_score": "160",
            "gre_aw": "4.5",
            "degree_type": "PhD",
            "llm-generated-program": "Computer Science",
            "llm-generated-university": "Example University",
        }
    ]

    data_file = tmp_path / "applicants.json"
    data_file.write_text(json.dumps(applicant_data), encoding="utf-8")

    monkeypatch.setattr(load_data, "DATA_FILE", str(data_file))

    load_data.main()

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM applicants;")
        first_count = cursor.fetchone()[0]

    load_data.main()

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM applicants;")
        second_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM applicants WHERE p_id = 123456;"
        )
        matching_p_id_count = cursor.fetchone()[0]

    assert first_count == 1
    assert second_count == 1
    assert matching_p_id_count == 1

    with db_connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE applicants;")
        column_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))

        cursor.executemany(
            f"INSERT INTO applicants ({column_names}) VALUES ({placeholders})",
            rows
        )
    db_connection.commit()


@pytest.mark.db
def test_get_applicant_returns_expected_dict(db_connection):
    """Verify that ``get_applicant`` returns all required applicant fields.

    A known applicant is inserted into the database, retrieved through
    :func:`src.orm_queries.get_applicant`, and checked for the expected
    dictionary keys and representative field values.

    :param db_connection: Connection to the application's PostgreSQL
        database.
    """
    applicant_data = {
        "p_id": 90000000,
        "program": "Computer Science",
        "university": "Example University",
        "comments": "Test applicant",
        "date_added": "2026-09-24",
        "url": "https://www.thegradcafe.com/result/90000000",
        "status": "Accepted",
        "term": "Fall 2026",
        "us_or_international": "American",
        "gpa": 3.8,
        "gre": 320.0,
        "gre_v": 160.0,
        "gre_aw": 4.5,
        "degree": "PhD",
        "llm_generated_program": "Computer Science",
        "llm_generated_university": "Example University",
    }

    with db_connection.cursor() as cursor:
        cursor.execute(load_data.CREATE_TABLE_SQL)
        cursor.execute(load_data.INSERT_SQL, applicant_data)

    db_connection.commit()

    result = orm_queries.get_applicant(90000000)

    assert isinstance(result, dict)

    expected_keys = {
        "p_id",
        "program",
        "university",
        "comments",
        "date_added",
        "url",
        "status",
        "term",
        "us_or_international",
        "gpa",
        "gre",
        "gre_v",
        "gre_aw",
        "degree",
        "llm_generated_program",
        "llm_generated_university",
    }

    assert set(result.keys()) == expected_keys

    assert result["p_id"] == 90000000
    assert result["program"] == "Computer Science"
    assert result["university"] == "Example University"
    assert result["degree"] == "PhD"
    assert result["term"] == "Fall 2026"

    with db_connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM applicants WHERE p_id = %s",
            (90000000,)
        )

    db_connection.commit()


@pytest.mark.db
def test_applicants_table_can_be_queried():
    """Verify that the ``applicants`` table can be queried successfully.

    The test executes a simple row-count query through the application's
    SQLAlchemy session and verifies that the resulting count is non-negative.
    """
    with Session() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM applicants")
        ).scalar()

    assert count >= 0


@pytest.mark.db
def test_transform_record_creates_database_record():
    """Verify that a scraper record is transformed into database fields.

    The test checks that the Grad Café result ID becomes ``p_id`` and that
    the program, university, and URL are preserved in the transformed
    database record.
    """
    applicant = {
        "url": RESULT_URL + "/",
        "program_name": "Computer Science",
        "university": "Johns Hopkins University",
        "comments": "Test applicant",
        "date_added": "2026-09-23",
        "applicant_status": "Accepted",
        "start_term": "Fall 2026",
        "nationality": "US",
        "gpa": "3.8",
        "gre_score": "320",
        "gre_v_score": "160",
        "gre_aw": "4.5",
        "degree_type": "PhD",
        "llm-generated-program": "Computer Science",
        "llm-generated-university": "Johns Hopkins University",
    }

    record = _transform_record(applicant)

    assert record["p_id"] == 12345
    assert record["program"] == "Computer Science"
    assert record["university"] == "Johns Hopkins University"
    assert record["url"] == applicant["url"]


@pytest.mark.db
@pytest.mark.parametrize(
    "url, expected",
    [
        (f"{BASE_URL}/result/12345/", 12345),
        ("", None),
        (None, None),
        ("not-a-number", None),
    ],
)
def test_get_p_id_handles_invalid_urls(url, expected):
    """Verify extraction of numeric result IDs from supported URLs.

    Valid Grad Café result URLs produce their numeric result ID. Empty,
    missing, malformed, or non-numeric URLs return ``None``.

    :param url: URL value passed to :func:`src.load_data._get_p_id`.
    :param expected: Expected numeric ID or ``None`` for invalid input.
    """
    assert _get_p_id(url) == expected


@pytest.mark.db
def test_get_applicant(monkeypatch):
    """Verify that ``get_applicant`` maps an ORM object to a dictionary.

    A fake SQLAlchemy session and applicant object are used to verify that
    the function queries the expected model, returns every applicant field,
    and closes the session afterward.

    :param monkeypatch: Pytest fixture used to replace the session factory.
    """
    class FakeApplicant:
        p_id = 123
        program = "Computer Science"
        university = "Johns Hopkins University"
        comments = "Great program"
        date_added = "2026-09-24"
        url = "https://example.com"
        status = "Accepted"
        term = "Fall 2026"
        us_or_international = "US"
        gpa = 3.8
        gre = 320
        gre_v = 160
        gre_aw = 4.5
        degree = "Masters"
        llm_generated_program = "Computer Science"
        llm_generated_university = "Johns Hopkins University"

    class FakeSession:
        def __init__(self):
            self.closed = False

        def get(self, model, p_id):
            assert model is orm_queries.Applicant
            assert p_id == 123
            return FakeApplicant()

        def close(self):
            self.closed = True

    session = FakeSession()
    monkeypatch.setattr(orm_queries, "Session", lambda: session)

    result = orm_queries.get_applicant(123)

    assert result == {
        "p_id": 123,
        "program": "Computer Science",
        "university": "Johns Hopkins University",
        "comments": "Great program",
        "date_added": "2026-09-24",
        "url": "https://example.com",
        "status": "Accepted",
        "term": "Fall 2026",
        "us_or_international": "US",
        "gpa": 3.8,
        "gre": 320,
        "gre_v": 160,
        "gre_aw": 4.5,
        "degree": "Masters",
        "llm_generated_program": "Computer Science",
        "llm_generated_university": "Johns Hopkins University",
    }

    assert session.closed is True


@pytest.mark.db
def test_get_applicant_not_found(monkeypatch):
    """Verify that ``get_applicant`` returns ``None`` for a missing applicant.

    A fake session returns no ORM object for the requested ID. The test
    verifies that the function returns ``None`` and still closes the session.

    :param monkeypatch: Pytest fixture used to replace the session factory.
    """
    class FakeSession:
        def __init__(self):
            self.closed = False

        def get(self, model, p_id):
            assert model is orm_queries.Applicant
            assert p_id == 999
            return None

        def close(self):
            self.closed = True

    session = FakeSession()
    monkeypatch.setattr(orm_queries, "Session", lambda: session)

    result = orm_queries.get_applicant(999)

    assert result is None
    assert session.closed is True


@pytest.mark.db
def test_clean_load_data(tmp_path):
    """Verify that the cleaning loader accepts supported JSON structures.

    A JSON list is loaded directly, a ``limit`` restricts the number of
    records, and a dictionary containing a ``rows`` list is also accepted.
    Invalid dictionary structures must raise ``ValueError``.

    :param tmp_path: Temporary directory used for test JSON files.
    """
    data = [{"id": 1}, {"id": 2}]
    path = tmp_path / "data.json"

    path.write_text(json.dumps(data), encoding="utf-8")

    assert clean.load_data(path) == data
    assert clean.load_data(path, limit=1) == [{"id": 1}]

    path.write_text(json.dumps({"rows": data}), encoding="utf-8")
    assert clean.load_data(path) == data

    path.write_text(json.dumps({"not_rows": data}), encoding="utf-8")

    with pytest.raises(ValueError, match="Input data must be a list"):
        clean.load_data(path)


@pytest.mark.db
def test_clean_canonical_helpers():
    """Verify canonical comparison and lookup helper behavior.

    The comparison key must normalize case and repeated whitespace, while
    canonical lookup helpers must map known programs and universities to
    their canonical values.
    """
    assert clean._comparison_key("  Computer   Science  ") == (
        "computer science"
    )
    assert clean._comparison_key(None) == ""

    lookup = clean._build_canonical_lookup(
        ["Computer Science", "Data Science"]
    )

    assert lookup == {
        "computer science": "Computer Science",
        "data science": "Data Science",
    }

    assert clean._get_canonical_program(
        "Computer Science"
    ) == "Computer Science"
    assert clean._get_canonical_university(
        "Johns Hopkins University"
    ) == "Johns Hopkins University"


@pytest.mark.db
@pytest.mark.parametrize(
    "program, university, expected",
    [
        ("Computer Science", "Johns Hopkins University", True),
        ("", "Johns Hopkins University", False),
        ("Computer Science", None, False),
    ],
)
def test_clean_already_cleaned(program, university, expected):
    """Verify detection of records with both generated fields populated.

    A record is considered already cleaned only when both the generated
    program and generated university values are present.

    :param program: Generated program value to place in the test record.
    :param university: Generated university value to place in the test
        record.
    :param expected: Expected result from
        :func:`src.clean._is_already_cleaned`.
    """
    row = {
        "llm-generated-program": program,
        "llm-generated-university": university,
    }

    assert clean._is_already_cleaned(row) is expected


@pytest.mark.db
@pytest.mark.parametrize(
    "program_ok, university_ok, program, university, "
    "llm_program, llm_university, expected",
    [
        (
            True,
            True,
            "Computer Science",
            "Johns Hopkins University",
            "Computer Science",
            "Johns Hopkins University",
            (
                "Computer Science",
                "Johns Hopkins University",
                0, 1, 1, 1, 1,
            ),
        ),
        (
            False,
            False,
            None,
            None,
            "data science",
            "test university",
            (
                "Data Science",
                "Test University",
                1, 0, 0, 0, 0,
            ),
        ),
        (
            True,
            False,
            "Computer Science",
            None,
            "Computer Science",
            "unknown university",
            (
                "Computer Science",
                "Test University",
                1, 0, 1, 0, 0,
            ),
        ),
        (
            False,
            True,
            None,
            "Johns Hopkins University",
            "unknown program",
            "Johns Hopkins University",
            (
                "Data Science",
                "Johns Hopkins University",
                1, 0, 0, 1, 0,
            ),
        ),
    ],
)
def test_clean_canon_check(
    monkeypatch,
    program_ok,
    university_ok,
    program,
    university,
    llm_program,
    llm_university,
    expected,
):
    """Verify canonical and LLM-derived cleaning branches.

    The test exercises the combinations where the program, university,
    neither, or both values already match canonical values. It verifies
    the standardized values and all cleaning statistics returned by
    :func:`src.clean._canon_check`.

    :param monkeypatch: Pytest fixture used to provide a deterministic
        LLM response.
    :param program_ok: Whether the input program has a canonical match.
    :param university_ok: Whether the input university has a canonical match.
    :param program: Existing program value.
    :param university: Existing university value.
    :param llm_program: Program value returned by the LLM.
    :param llm_university: University value returned by the LLM.
    :param expected: Expected standardized values and cleaning counters.
    """
    monkeypatch.setattr(
        clean,
        "_call_llm",
        lambda **kwargs: {
            "standardized_program": "Data Science",
            "standardized_university": "Test University",
        },
    )

    result = clean._canon_check(
        program_ok,
        university_ok,
        program,
        university,
        llm_program,
        llm_university,
        0, 0, 0, 0, 0,
    )

    assert result == expected


@pytest.mark.db
def test_final_cleaning_stats(monkeypatch, capsys):
    """Verify the formatting of the cleaning summary statistics.

    The test fixes the current time so that elapsed time and processing
    rate are deterministic, then verifies that all summary counters are
    printed with their expected labels and formatting.

    :param monkeypatch: Pytest fixture used to replace ``time.time``.
    :param capsys: Pytest fixture used to capture standard output.
    """
    monkeypatch.setattr("src.clean.time.time", lambda: 101.0)

    clean._final_cleaning_stats(
        start_time=100.0,
        total=10,
        program_matches=6,
        university_matches=7,
        both_matches=5,
        llm_calls=3,
        skipped_llm=2,
        already_cleaned=1,
    )

    output = capsys.readouterr().out

    for text in [
        "Cleaning summary",
        "Total records:                10",
        "Program canonical matches:    6",
        "University canonical matches: 7",
        "Both canonical:                5",
        "LLM calls:                     3",
        "Skipped LLM calls:             2",
        "Already cleaned:               1",
        "Elapsed time:                  1.0s",
        "Average rate:                  10.00 records/sec",
    ]:
        assert text in output


@pytest.mark.db
def test_clean_data_empty():
    """Verify that cleaning an empty record list returns an empty list."""
    assert clean.clean_data([]) == []


@pytest.mark.db
def test_clean_data_already_cleaned_record():
    """Verify that an already-cleaned record is returned unchanged.

    Records containing both generated program and university values should
    bypass additional cleaning and remain identical to their input form.
    """
    row = {
        "program_name": "Computer Science",
        "university": "Johns Hopkins University",
        "llm-generated-program": "Computer Science",
        "llm-generated-university": "Johns Hopkins University",
    }

    assert clean.clean_data([row]) == [row]


@pytest.mark.db
def test_clean_data_canonical_record():
    """Verify that canonical program and university values are populated.

    A record whose original program and university already match canonical
    values should receive those canonical values in the generated fields.
    """
    row = {
        "program_name": "Computer Science",
        "university": "Johns Hopkins University",
    }

    assert clean.clean_data([row]) == [{
        **row,
        "llm-generated-program": "Computer Science",
        "llm-generated-university": "Johns Hopkins University",
    }]


@pytest.mark.db
def test_save_cleaned_data(tmp_path, capsys):
    """Verify that cleaned records are written to a JSON file.

    The test confirms that the output file is created, contains the supplied
    records, and that the save operation reports the number of records
    written.

    :param tmp_path: Temporary directory used for the output JSON file.
    :param capsys: Pytest fixture used to capture standard output.
    """
    path = tmp_path / "cleaned.json"
    data = [{"program_name": "Computer Science"}]

    clean.save_cleaned_data(data, str(path))

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert f"Saved 1 records to {path}" in capsys.readouterr().out


@pytest.mark.db
def test_clean_main_block(monkeypatch):
    """Verify that the cleaning module's main block can execute.

    The cleaning, loading, and saving functions are replaced with no-op
    implementations so the module's ``__main__`` entry point can be
    executed without performing real file or LLM operations.

    :param monkeypatch: Pytest fixture used to replace cleaning operations.
    """
    monkeypatch.setattr(clean, "load_data", lambda path: [])
    monkeypatch.setattr(clean, "clean_data", lambda data: [])
    monkeypatch.setattr(
        clean,
        "save_cleaned_data",
        lambda data, path: None,
    )

    path = "src/clean.py"

    with open(path, encoding="utf-8") as file:
        source = file.read()

    exec(compile(source, path, "exec"), {"__name__": "__main__"})


@pytest.mark.db
def test_load_data_helpers_cover_invalid_values():
    """Verify invalid-value handling and complete record transformation.

    Invalid numeric values, dates, and result IDs must be converted to
    ``None``. A valid applicant record must have its string fields trimmed,
    numeric fields converted, date parsed, and LLM-generated field names
    converted to the database naming convention.
    """
    assert load_data._clean_float("not-a-number") is None
    assert load_data._parse_date("not-a-date") is None
    assert load_data._get_p_id("not-a-number") is None

    record = load_data._transform_record({
        "url": "https://www.thegradcafe.com/result/54321/",
        "program_name": "  Computer Science  ",
        "university": "  Johns Hopkins University  ",
        "comments": "  Test comment  ",
        "date_added": "09/23/2026",
        "applicant_status": "  Accepted  ",
        "start_term": "  Fall 2026  ",
        "nationality": "  US  ",
        "gpa": "3.85",
        "gre_score": "320",
        "gre_v_score": "160",
        "gre_aw": "4.5",
        "degree_type": "  PhD  ",
        "llm-generated-program": "  Computer Science  ",
        "llm-generated-university": "  Johns Hopkins University  ",
    })

    assert record["p_id"] == 54321
    assert record["program"] == "Computer Science"
    assert record["university"] == "Johns Hopkins University"
    assert record["comments"] == "Test comment"
    assert str(record["date_added"]) == "2026-09-23"
    assert record["status"] == "Accepted"
    assert record["term"] == "Fall 2026"
    assert record["us_or_international"] == "US"
    assert record["gpa"] == 3.85
    assert record["gre"] == 320.0
    assert record["gre_v"] == 160.0
    assert record["gre_aw"] == 4.5
    assert record["degree"] == "PhD"
    assert record["llm_generated_program"] == "Computer Science"
    assert record["llm_generated_university"] == "Johns Hopkins University"


@pytest.mark.db
def test_load_data_main(monkeypatch, tmp_path, capsys):
    """Verify the main database loading workflow.

    The test supplies one valid and one invalid applicant record, replaces
    the database connection with a fake connection, and verifies that the
    loader creates the table, inserts only the valid record, commits the
    transaction, and reports the expected processing statistics.

    :param monkeypatch: Pytest fixture used to replace the input path and
        PostgreSQL connection.
    :param tmp_path: Temporary directory used for the input JSON file.
    :param capsys: Pytest fixture used to capture loader output.
    """
    data_file = tmp_path / "applicants.json"

    applicants = [
        {
            "url": "https://www.thegradcafe.com/result/12345/",
            "program_name": "Computer Science",
            "university": "Johns Hopkins University",
            "comments": "Test applicant",
            "date_added": "09/23/2026",
            "applicant_status": "Accepted",
            "start_term": "Fall 2026",
            "nationality": "US",
            "gpa": "3.8",
            "gre_score": "320",
            "gre_v_score": "160",
            "gre_aw": "4.5",
            "degree_type": "PhD",
        },
        {
            "url": "invalid-url",
            "program_name": "Invalid record",
        },
    ]

    data_file.write_text(
        json.dumps(applicants),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        load_data,
        "DATA_FILE",
        str(data_file),
    )

    monkeypatch.setattr(
        load_data,
        "DATABASE_URL",
        "test-database-url",
    )

    executed = []
    committed = False

    class FakeCursor:
        def __init__(self):
            self.fetchone_calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, sql, record=None):
            executed.append((sql, record))

        def fetchone(self):
            self.fetchone_calls += 1
            return None

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            nonlocal committed
            committed = True

        def rollback(self):
            pass

    def fake_connect(connection_string):
        assert connection_string == "test-database-url"
        return FakeConnection()

    monkeypatch.setattr(
        load_data.psycopg,
        "connect",
        fake_connect,
    )

    load_data.main()

    assert committed is True
    assert executed[0][0] == load_data.CREATE_TABLE_SQL

    insert_calls = [
        call
        for call in executed
        if call[0] == load_data.INSERT_SQL
    ]

    assert len(insert_calls) == 1
    assert insert_calls[0][1]["p_id"] == 12345

    output = capsys.readouterr().out

    assert "Loading data from" in output
    assert "Changes committed to the database." in output
    assert "Processed: 2" in output
    assert "Inserted:  1" in output
    assert "Updated:   0" in output
    assert "Unchanged: 0" in output
    assert "Skipped:   1" in output
    assert "Database loading complete." in output


@pytest.mark.db
def test_load_data_transform_record_cleans_all_fields():
    """Verify that ``_transform_record`` normalizes all applicant fields.

    Leading and trailing whitespace is removed from string fields, numeric
    values are converted to floats, dates are converted to ``date`` objects,
    and hyphenated LLM-generated keys are mapped to database column names.
    """
    applicant = {
        "url": "https://www.thegradcafe.com/result/54321/",
        "program_name": "  Computer Science  ",
        "university": "  Johns Hopkins University  ",
        "comments": "  Test comment  ",
        "date_added": "09/23/2026",
        "applicant_status": "  Accepted  ",
        "start_term": "  Fall 2026  ",
        "nationality": "  US  ",
        "gpa": "3.85",
        "gre_score": "320",
        "gre_v_score": "160",
        "gre_aw": "4.5",
        "degree_type": "  PhD  ",
        "llm-generated-program": "  Computer Science  ",
        "llm-generated-university": "  Johns Hopkins University  ",
    }

    result = load_data._transform_record(applicant)

    assert result["p_id"] == 54321
    assert result["program"] == "Computer Science"
    assert result["university"] == "Johns Hopkins University"
    assert result["comments"] == "Test comment"
    assert result["date_added"] == date(2026, 9, 23)
    assert result["status"] == "Accepted"
    assert result["term"] == "Fall 2026"
    assert result["us_or_international"] == "US"
    assert result["gpa"] == 3.85
    assert result["gre"] == 320.0
    assert result["gre_v"] == 160.0
    assert result["gre_aw"] == 4.5
    assert result["degree"] == "PhD"
    assert result["llm_generated_program"] == "Computer Science"
    assert result["llm_generated_university"] == (
        "Johns Hopkins University"
    )


@pytest.mark.db
def test_load_data_clean_float_invalid_values():
    """Verify that ``_clean_float`` returns ``None`` for invalid inputs.

    The helper must reject both non-numeric strings and arbitrary objects
    that cannot be converted to a floating-point value.
    """
    assert _clean_float("not-a-number") is None
    assert _clean_float(object()) is None


@pytest.mark.db
def test_load_data_invalid_float_and_id():
    """Verify invalid numeric values and malformed result IDs return ``None``."""
    assert load_data._clean_float("invalid") is None
    assert load_data._get_p_id(
        "https://www.thegradcafe.com/result/abc"
    ) is None


@pytest.mark.db
def test_load_data_transform_record_invalid_numeric_values():
    """Verify that invalid applicant numeric fields become ``None``.

    A record with a valid result ID but invalid GPA and GRE values should
    still be transformed successfully, with each invalid numeric field
    represented as ``None``.
    """
    applicant = {
        "url": "https://www.thegradcafe.com/result/54321",
        "gpa": "not-a-number",
        "gre_score": "invalid",
        "gre_v_score": "bad",
        "gre_aw": "invalid",
    }

    record = load_data._transform_record(applicant)

    assert record["p_id"] == 54321
    assert record["gpa"] is None
    assert record["gre"] is None
    assert record["gre_v"] is None
    assert record["gre_aw"] is None