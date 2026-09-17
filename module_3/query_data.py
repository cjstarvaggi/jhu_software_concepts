import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")


def _get_connection():
    """
    Creates and returns the PostgreSQL database
    connection.
    """
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def _submit_query(conn, sql):
    """
    Submits a query to the applicants table in the
    PostgreSQL database through the existing
    connection.
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchone()[0]


def _question_1(conn):
    """
    Question 1:
    How many entries in the database are from applicants
    who applied for Fall 2026?
    """

    sql = """
        SELECT COUNT (*) from applicants
            WHERE term = 'Fall 2026';
    """

    result = _submit_query(conn, sql)
    print(f"1. Fall 2026 applicant count: {result:,}")


def _question_2(conn):
    """
    Question 2:
    Among entries that provide a nationality classification,
    what percentage are international students?
    """

    sql = """
        SELECT ROUND(
            100.0 * COUNT(*) /
            (
                SELECT COUNT(*)
                FROM applicants
                WHERE us_or_international IS NOT NULL
            ),
            2
        )
        FROM applicants
        WHERE us_or_international = 'International (my highest degree is from outside USA)'
        AND us_or_international IS NOT NULL;
    """

    result = _submit_query(conn, sql)
    print(f"2. Percent international: {result}%")


def _question_3(conn):
    """
    Question 3:
    What is the average GPA, GRE Quantitative,
    GRE Verbal, and GRE Analytical Writing scores
    of applicants who provide each metric?
    """

    sql1 = """
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants;
    """

    sql2 = """
        SELECT ROUND(AVG(gre)::numeric, 2)
        FROM applicants;
    """

    sql3 = """
        SELECT ROUND(AVG(gre_v)::numeric, 2)
        FROM applicants;
    """

    sql4 = """
        SELECT ROUND(AVG(gre_aw)::numeric, 2)
        FROM applicants;
    """

    result1 = _submit_query(conn, sql1)
    result2 = _submit_query(conn, sql2)
    result3 = _submit_query(conn, sql3)
    result4 = _submit_query(conn, sql4)

    print(f"3. Average GPA: {result1:.2f}")
    print(f"3. Average GRE Quantitative: {result2:.2f}")
    print(f"3. Average GRE Verbal: {result3:.2f}")
    print(f"3. Average GRE Analytical Writing: {result4:.2f}")


def _question_4(conn):
    """
    Question 4:
    What is the average GPA of American applicants
    who applied for Fall 2026?
    """

    sql = """
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term = 'Fall 2026'
        AND us_or_international = 'American'
        AND gpa IS NOT NULL;
    """

    result = _submit_query(conn, sql)
    print(f"4. Average Fall 2026 American applicant GPA: {result}")


def _question_5(conn):
    """
    Question 5:
    What percentage of Fall 2025 entries are acceptances?
    """

    sql = """
        SELECT ROUND(
            100.0 * COUNT(*) /
            (
                SELECT COUNT(*)
                FROM applicants
                WHERE term = 'Fall 2025'
            ),
            2
        )
        FROM applicants
        WHERE term = 'Fall 2025'
        AND status = 'Accepted';
    """

    result = _submit_query(conn, sql)
    print(f"5. Fall 2025 acceptance percentage: {result}%")


def _question_6(conn):
    """
    Question 6:
    What is the average GPA of accepted applicants
    who applied for Fall 2026?
    """

    sql = """
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term = 'Fall 2026'
        AND status = 'Accepted'
        AND gpa IS NOT NULL;
    """

    result = _submit_query(conn, sql)
    print(f"6. Average Fall 2026 accepted applicant GPA: {result}")


def _question_7(conn):
    """
    Question 7:
    How many entries are from applicants who applied to Johns Hopkins
    University for a master's degree in Computer Science?
    """

    sql = """
        SELECT COUNT (*) from applicants
            WHERE university LIKE ANY (ARRAY['%Johns Hopkins University%', '%JHU%'])
            AND degree = 'Masters'
            AND program = 'Computer Science';
    """

    result = _submit_query(conn, sql)
    print(f"7. JHU Computer Science masters applicants: {result}")


def _question_8(conn):
    """
    Question 8:
    How many Fall 2026 entries are acceptances from applicants
    applying for a PhD in Computer Science at one of the
    following universities?
    """

    sql = """
        SELECT COUNT (*) from applicants
            WHERE university LIKE ANY (ARRAY['%Georgetown University%', '%Massachusetts Institute of Technology%', '%MIT%', '%Stanford University%', '%Carnegie Mellon University%'])
            AND degree = 'PhD'
            AND program = 'Computer Science'
            AND status = 'Accepted'
            AND term = 'Fall 2026';
    """

    result = _submit_query(conn, sql)
    print(f"8. Fall 2026 various university Computer Science PhD acceptances: {result}")


def _question_9(conn):
    """
    Question 9:
    How many Fall 2026 entries are acceptances from applicants
    applying for a PhD in Computer Science at one of the
    following universities (using llm adjusted values)?
    """

    sql1 = """
        SELECT COUNT (*) from applicants
            WHERE university LIKE ANY (ARRAY['%Georgetown University%', '%Massachusetts Institute of Technology%', '%MIT%', '%Stanford University%', '%Carnegie Mellon University%'])
            AND degree = 'PhD'
            AND program = 'Computer Science'
            AND status = 'Accepted'
            AND term = 'Fall 2026';
    """

    sql2 = """
        SELECT COUNT (*) from applicants
            WHERE llm_generated_university LIKE ANY (ARRAY['%Georgetown University%', '%Massachusetts Institute of Technology%', '%MIT%', '%Stanford University%', '%Carnegie Mellon University%'])
            AND degree = 'PhD'
            AND llm_generated_program = 'Computer Science'
            AND status = 'Accepted'
            AND term = 'Fall 2026';
    """

    result1 = _submit_query(conn, sql1)
    result2 = _submit_query(conn, sql2)
    print(f"9. Original-field count: {result1}")
    print(f"9. LLM-field count: {result2}")
    print(f"9. Difference: {result1-result2}")


def _question_10(conn):
    """
    Question 10:
    How many entries are applicants
    applying for a Physics PhD
    at West Virginia University?
    """

    sql = """
        SELECT COUNT (*) from applicants
            WHERE university LIKE ANY (ARRAY['%West Virginia University%', '%WVU%'])
            AND program = 'Physics'
            AND degree = 'PhD'
    """

    result = _submit_query(conn, sql)
    print(f"10. West Virginia University Physics PhD applicants: {result}")


def _question_11(conn):
    """
    Question 11:
    What is the average GPA of applicants accepted to
    Johns Hopkins University for a master's degree who
    reported their gpa?
    """

    sql = """
        SELECT ROUND(AVG(gpa)::numeric, 2)
            FROM applicants
            WHERE university LIKE ANY (ARRAY['%Johns Hopkins University%', '%JHU%'])
            AND status = 'Accepted'
            AND gpa IS NOT NULL
            AND degree = 'Masters';
    """

    result = _submit_query(conn, sql)
    print(f"11. JHU Masters acceptances average GPA: {result}")


def main():
    """
    Initializes a connection to the PostgreSQL database
    and then runs all the query questions.
    """
    with _get_connection() as conn:
        _question_1(conn)
        _question_2(conn)
        _question_3(conn)
        _question_4(conn)
        _question_5(conn)
        _question_6(conn)
        _question_7(conn)
        _question_8(conn)
        _question_9(conn)
        _question_10(conn)
        _question_11(conn)


if __name__ == "__main__":
    main()
