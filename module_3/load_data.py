import os
import json
import psycopg

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = os.getenv(
    "APPLICANT_DATA_FILE",
    "llm_extended_applicant_data.json",
)

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")


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
        program = EXCLUDED.program,
        university = EXCLUDED.university,
        comments = EXCLUDED.comments,
        date_added = EXCLUDED.date_added,
        url = EXCLUDED.url,
        status = EXCLUDED.status,
        term = EXCLUDED.term,
        us_or_international = EXCLUDED.us_or_international,
        gpa = EXCLUDED.gpa,
        gre = EXCLUDED.gre,
        gre_v = EXCLUDED.gre_v,
        gre_aw = EXCLUDED.gre_aw,
        degree = EXCLUDED.degree,
        llm_generated_program = EXCLUDED.llm_generated_program,
        llm_generated_university = EXCLUDED.llm_generated_university;
"""


def _clean_text(value):
    """
    Converts missing and blank values to None.
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
    Converts numeric values to floats, or None when
    they are missing or invalid.
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
    Converts MM/DD/YYYY strings into Python date
    objects.
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
    Creates a unique id from the Grad Cafe result url
    by stripping the page id and converting it to an
    integer.
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
    Transforms a dictionary from the JSON
    file into one compatible with the database
    schema.
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


def main():
    """
    Creates a table in the database if it does
    not already exist, and then loads the
    applicant data from the JSON file, makes
    it database compatible, and then writes it
    to the database.
    """
    print(f"Loading data from {DATA_FILE}...")

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        applicants = json.load(file)

    print(f"Found {len(applicants)} applicant records.")

    connection_string = (
        f"host={DB_HOST} "
        f"port={DB_PORT} "
        f"dbname={DB_NAME} "
        f"user={DB_USER} "
        f"password={DB_PASSWORD}"
    )

    inserted = 0
    skipped = 0

    with psycopg.connect(connection_string) as conn:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            for applicant in applicants:
                record = _transform_record(applicant)

                if record is None:
                    skipped += 1
                    continue

                cursor.execute(INSERT_SQL, record)
                inserted += 1

        conn.commit()

    print(f"Processed: {len(applicants)}")
    print(f"Loaded:    {inserted}")
    print(f"Skipped:   {skipped}")
    print("Database loading complete.")


if __name__ == "__main__":
    main()
