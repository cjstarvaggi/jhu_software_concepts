from sqlalchemy import Numeric, and_, cast, func, or_, select

from models import Applicant, Session


def _question_1(session):
    """
    Question 1:
    How many entries in the database are from applicants
    who applied for Fall 2026?
    """
    statement = select(func.count(Applicant.p_id)).where(
        Applicant.term.ilike("Fall 2026")
    )

    result = session.execute(statement).scalar_one()

    print(f"1. Fall 2026 applicant count: {result:,}")


def _question_4(session):
    """
    Question 4:
    What is the average GPA of American applicants
    who applied for Fall 2026?
    """
    statement = select(func.round(cast(func.avg(Applicant.gpa), Numeric), 2)).where(
        and_(
            Applicant.term.ilike("Fall 2026"),
            Applicant.us_or_international.ilike("American"),
            Applicant.gpa.is_not(None),
        )
    )

    result = session.execute(statement).scalar_one_or_none()

    print(f"4. Average Fall 2026 American applicant GPA: {result:.2f}")


def _question_5(session):
    """
    Question 5:
    What percentage of Fall 2025 entries are acceptances?
    """
    total_statement = select(func.count(Applicant.p_id)).where(
        Applicant.term.ilike("Fall 2025")
    )

    accepted_statement = select(func.count(Applicant.p_id)).where(
        and_(
            Applicant.term.ilike("Fall 2025"),
            Applicant.status.ilike("Accepted"),
        )
    )

    total = session.execute(total_statement).scalar_one()
    accepted = session.execute(accepted_statement).scalar_one()
    percentage = (accepted / total) * 100

    print(f"5. Fall 2025 acceptance percentage: {percentage:.2f}%")


def _question_8(session):
    """
    Question 8:
    How many Fall 2026 entries are acceptances from applicants
    applying for a PhD in Computer Science at one of the
    following universities?
    """

    universities = [
        "Georgetown University",
        "Massachusetts Institute of Technology",
        "MIT",
        "Stanford University",
        "Carnegie Mellon University",
    ]

    university_conditions = [
        Applicant.university.ilike(f"%{university}%") for university in universities
    ]

    statement = select(func.count(Applicant.p_id)).where(
        and_(
            or_(*university_conditions),
            Applicant.degree.ilike("PhD"),
            Applicant.program.ilike("Computer Science"),
            Applicant.status.ilike("Accepted"),
            Applicant.term.ilike("Fall 2026"),
        )
    )

    result = session.execute(statement).scalar_one()

    print(
        f"8. Fall 2026 various university Computer Science PhD acceptances: {result:,}"
    )


def _question_9(session):
    """
    Question 9:
    How many Fall 2026 entries are acceptances from applicants
    applying for a PhD in Computer Science at one of the
    following universities, comparing the original fields
    with the LLM-adjusted fields?
    """
    universities = [
        "Georgetown University",
        "Massachusetts Institute of Technology",
        "MIT",
        "Stanford University",
        "Carnegie Mellon University",
    ]

    original_university_conditions = [
        Applicant.university.ilike(f"%{university}%") for university in universities
    ]

    llm_university_conditions = [
        Applicant.llm_generated_university.ilike(f"%{university}%")
        for university in universities
    ]

    original_statement = select(func.count(Applicant.p_id)).where(
        and_(
            or_(*original_university_conditions),
            Applicant.degree.ilike("PhD"),
            Applicant.program.ilike("Computer Science"),
            Applicant.status.ilike("Accepted"),
            Applicant.term.ilike("Fall 2026"),
        )
    )

    llm_statement = select(func.count(Applicant.p_id)).where(
        and_(
            or_(*llm_university_conditions),
            Applicant.degree.ilike("PhD"),
            Applicant.llm_generated_program.ilike("Computer Science"),
            Applicant.status.ilike("Accepted"),
            Applicant.term.ilike("Fall 2026"),
        )
    )

    original_result = session.execute(original_statement).scalar_one()
    llm_result = session.execute(llm_statement).scalar_one()

    print(f"9. Original-field count: {original_result:,}")
    print(f"9. LLM-field count: {llm_result:,}")
    print(f"9. Difference: {original_result - llm_result:,}")


def _question_11(session):
    """
    Question 11:
    What is the average GPA of applicants accepted to
    Johns Hopkins University for a master's degree who
    reported their GPA?
    """
    university_conditions = [
        Applicant.university.ilike("%Johns Hopkins University%"),
        Applicant.university.ilike("%JHU%"),
    ]

    statement = select(func.round(cast(func.avg(Applicant.gpa), Numeric), 2)).where(
        and_(
            or_(*university_conditions),
            Applicant.status.ilike("Accepted"),
            Applicant.gpa.is_not(None),
            Applicant.degree.ilike("Masters"),
        )
    )

    result = session.execute(statement).scalar_one_or_none()

    print(f"11. JHU Masters acceptances average GPA: {result:.2f}")


def main():
    """
    Creates a SQLAlchemy session and runs the
    ORM queries.
    """
    with Session() as session:
        _question_1(session)
        _question_4(session)
        _question_5(session)
        _question_8(session)
        _question_9(session)
        _question_11(session)


if __name__ == "__main__":
    main()
