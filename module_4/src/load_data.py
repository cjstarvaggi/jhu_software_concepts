import os
import json
import psycopg

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = os.getenv("DATA_FILE")
DATABASE_URL = os.getenv("DATABASE_URL")


CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS applicants (
        p_id INTEGER PRIMARY KEY,
        program TEXT,
        university TEXT,
        comments TEXT,
        date_added DATE,
        url TEXT UNIQUE,
        status TEXT,
        term TEXT,
        us_or_international TEXT,
        gpa REAL,
        gre REAL,
        gre_v REAL,
        gre_aw REAL,
        degree TEXT,
        llm_generated_program TEXT,
        llm_generated_university TEXT
    );
"""

INSERT_SQL = """
    INSERT INTO applicants (
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
    )
    VALUES (
        %(p_id)s,
        %(program)s,
        %(university)s,
        %(comments)s,
        %(date_added)s,
        %(url)s,
        %(status)s,
        %(term)s,
        %(us_or_international)s,
        %(gpa)s,
        %(gre)s,
        %(gre_v)s,
        %(gre_aw)s,
        %(degree)s,
        %(llm_generated_program)s,
        %(llm_generated_university)s
    )
    ON CONFLICT (p_id) DO UPDATE SET
        program = COALESCE(EXCLUDED.program, applicants.program),
        university = COALESCE(EXCLUDED.university, applicants.university),
        comments = COALESCE(EXCLUDED.comments, applicants.comments),
        date_added = COALESCE(EXCLUDED.date_added, applicants.date_added),
        url = COALESCE(EXCLUDED.url, applicants.url),
        status = COALESCE(EXCLUDED.status, applicants.status),
        term = COALESCE(EXCLUDED.term, applicants.term),
        us_or_international = COALESCE(
            EXCLUDED.us_or_international,
            applicants.us_or_international
        ),
        gpa = COALESCE(EXCLUDED.gpa, applicants.gpa),
        gre = COALESCE(EXCLUDED.gre, applicants.gre),
        gre_v = COALESCE(EXCLUDED.gre_v, applicants.gre_v),
        gre_aw = COALESCE(EXCLUDED.gre_aw, applicants.gre_aw),
        degree = COALESCE(EXCLUDED.degree, applicants.degree),
        llm_generated_program = COALESCE(
            EXCLUDED.llm_generated_program,
            applicants.llm_generated_program
        ),
        llm_generated_university = COALESCE(
            EXCLUDED.llm_generated_university,
            applicants.llm_generated_university
        )
    WHERE ROW(
        applicants.program,
        applicants.university,
        applicants.comments,
        applicants.date_added,
        applicants.url,
        applicants.status,
        applicants.term,
        applicants.us_or_international,
        applicants.gpa,
        applicants.gre,
        applicants.gre_v,
        applicants.gre_aw,
        applicants.degree,
        applicants.llm_generated_program,
        applicants.llm_generated_university
    ) IS DISTINCT FROM ROW(
        COALESCE(EXCLUDED.program, applicants.program),
        COALESCE(EXCLUDED.university, applicants.university),
        COALESCE(EXCLUDED.comments, applicants.comments),
        COALESCE(EXCLUDED.date_added, applicants.date_added),
        COALESCE(EXCLUDED.url, applicants.url),
        COALESCE(EXCLUDED.status, applicants.status),
        COALESCE(EXCLUDED.term, applicants.term),
        COALESCE(EXCLUDED.us_or_international, applicants.us_or_international),
        COALESCE(EXCLUDED.gpa, applicants.gpa),
        COALESCE(EXCLUDED.gre, applicants.gre),
        COALESCE(EXCLUDED.gre_v, applicants.gre_v),
        COALESCE(EXCLUDED.gre_aw, applicants.gre_aw),
        COALESCE(EXCLUDED.degree, applicants.degree),
        COALESCE(EXCLUDED.llm_generated_program, applicants.llm_generated_program),
        COALESCE(EXCLUDED.llm_generated_university, applicants.llm_generated_university)
    )
    RETURNING p_id;
"""


def _clean_text(value):
    """
    Normalize a text value for database storage.

    Missing values and strings containing only whitespace are converted to
    ``None``. Non-string values are returned unchanged.

    :param value: Value to normalize.
    :type value: object
    :returns: The stripped value, ``None`` for missing or blank strings, or
        the original non-string value.
    :rtype: object
    """

    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    return value


def _clean_float(value):
    """
    Convert a value to a floating-point number for database storage.

    Missing, blank, and invalid numeric values are converted to ``None``.

    :param value: Value to convert to a float.
    :type value: object
    :returns: The converted floating-point value, or ``None`` when the
        value is missing or invalid.
    :rtype: float or None
    """

    value = _clean_text(value)

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value):
    """
    Convert an ``MM/DD/YYYY`` date string into a Python ``date`` object.

    Missing, blank, or incorrectly formatted values are converted to
    ``None``.

    :param value: Date value to parse.
    :type value: object
    :returns: Parsed date, or ``None`` when the value is missing or invalid.
    :rtype: datetime.date or None
    """

    value = _clean_text(value)

    if value is None:
        return None

    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        return None


def _get_p_id(url):
    """
    Extract the Grad Cafe result ID from a result URL.

    The final path component of the URL is interpreted as an integer and
    used as the applicant's database primary key.

    :param url: Grad Cafe result URL.
    :type url: str or None
    :returns: The numeric result ID, or ``None`` if it cannot be extracted.
    :rtype: int or None
    """

    url = _clean_text(url)

    if not url:
        return None

    try:
        return int(url.rstrip("/").split("/")[-1])
    except (ValueError, TypeError):
        return None


def _transform_record(applicant):
    """
    Transform a JSON applicant record into the structure expected by the
    PostgreSQL ``applicants`` table.

    Text fields are cleaned, numeric fields are converted to floats, dates
    are converted to Python ``date`` objects, and the Grad Cafe result ID
    is extracted from the record URL.

    Records without a valid result ID are skipped by returning ``None``.

    :param applicant: Applicant record loaded from the JSON data file.
    :type applicant: dict
    :returns: Database-ready applicant record, or ``None`` when the record
        does not contain a valid result ID.
    :rtype: dict or None
    """

    url = _clean_text(applicant.get("url"))
    p_id = _get_p_id(url)

    if p_id is None:
        return None

    return {
        "p_id": p_id,
        "program": _clean_text(applicant.get("program_name")),
        "university": _clean_text(applicant.get("university")),
        "comments": _clean_text(applicant.get("comments")),
        "date_added": _parse_date(applicant.get("date_added")),
        "url": url,
        "status": _clean_text(applicant.get("applicant_status")),
        "term": _clean_text(applicant.get("start_term")),
        "us_or_international": _clean_text(applicant.get("nationality")),
        "gpa": _clean_float(applicant.get("gpa")),
        "gre": _clean_float(applicant.get("gre_score")),
        "gre_v": _clean_float(applicant.get("gre_v_score")),
        "gre_aw": _clean_float(applicant.get("gre_aw")),
        "degree": _clean_text(applicant.get("degree_type")),
        "llm_generated_program": _clean_text(applicant.get("llm-generated-program")),
        "llm_generated_university": _clean_text(
            applicant.get("llm-generated-university")
        ),
    }


def main(rollback=False, data_file=None):
    """
    Load applicant data from JSON and synchronize it with PostgreSQL.

    The ``applicants`` table is created if it does not already exist.
    Existing database values are preserved when the corresponding incoming
    value is ``None``. Non-NULL incoming values can replace existing values
    when they differ.

    Database changes are committed unless ``rollback`` is ``True``. Any
    exception during processing causes the current transaction to be
    rolled back before the exception is re-raised.

    :param rollback: If ``True``, roll back the transaction instead of
        committing changes.
    :type rollback: bool
    :raises Exception: Re-raises any exception encountered while loading
        or writing applicant data.
    """

    print(f"Loading data from {DATA_FILE}...")

    data_file = data_file or DATA_FILE

    with open(data_file, "r", encoding="utf-8") as file:
        applicants = json.load(file)

    connection_string = DATABASE_URL

    inserted = 0
    updated = 0
    unchanged = 0
    skipped = 0

    with psycopg.connect(connection_string) as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)

                for applicant in applicants:
                    record = _transform_record(applicant)

                    if record is None:
                        skipped += 1
                        continue

                    # Check whether the record already exists.
                    cursor.execute(
                        "SELECT 1 FROM applicants WHERE p_id = %(p_id)s",
                        {"p_id": record["p_id"]},
                    )
                    existed = cursor.fetchone() is not None

                    cursor.execute(INSERT_SQL, record)

                    if not existed:
                        inserted += 1
                    elif cursor.fetchone() is not None:
                        updated += 1
                    else:
                        unchanged += 1

            if rollback:
                conn.rollback()
                print("Transaction rolled back.")
            else:
                conn.commit()
                print("Changes committed to the database.")

        except Exception:
            conn.rollback()
            raise

    print(f"Processed: {len(applicants)}")
    print(f"Inserted:  {inserted}")
    print(f"Updated:   {updated}")
    print(f"Unchanged: {unchanged}")
    print(f"Skipped:   {skipped}")
    print("Database loading complete.")


if __name__ == "__main__":  # pragma: no cover
    main()
