from sqlalchemy import Numeric, and_, cast, func, or_, select

from models import Applicant, Session

def get_applicant(p_id):
    session = Session()

    try:
        applicant = session.get(Applicant, p_id)

        if applicant is None:
            return None

        return {
            "p_id": applicant.p_id,
            "program": applicant.program,
            "university": applicant.university,
            "comments": applicant.comments,
            "date_added": applicant.date_added,
            "url": applicant.url,
            "status": applicant.status,
            "term": applicant.term,
            "us_or_international": applicant.us_or_international,
            "gpa": applicant.gpa,
            "gre": applicant.gre,
            "gre_v": applicant.gre_v,
            "gre_aw": applicant.gre_aw,
            "degree": applicant.degree,
            "llm_generated_program": applicant.llm_generated_program,
            "llm_generated_university": applicant.llm_generated_university,
        }
    finally:
        session.close()


def _question_1(session, print_string=True):
    """
    Question 1:
    How many entries in the database are from applicants
    who applied for Fall 2026?
    """
    statement = select(func.count(Applicant.p_id)).where(
        Applicant.term.ilike("Fall 2026")
    )

    result = session.execute(statement).scalar_one()
    result_string = f"Fall 2026 applicant count: {result:,}"

    if print_string:
        print(f"1. {result_string}")
    else:
        return result_string


def _question_2(session, print_string=True):
    """
    Question 2: Among entries that provide a nationality
    classification, what percentage are international students?
    """

    total_statement = select(func.count(Applicant.p_id)).where(
        Applicant.us_or_international.is_not(None)
    )

    international_statement = select(func.count(Applicant.p_id)).where(
        or_(
            Applicant.us_or_international.ilike(
                "International (my highest degree is from outside USA)"
            ),
            Applicant.us_or_international.ilike(
                "International (my highest degree is from USA)"
            ),
        )
    )

    total = session.execute(total_statement).scalar_one()
    international = session.execute(international_statement).scalar_one()

    if total == 0:
        result_string = "Percent international: N/A (no nationality classifications)"
    else:
        percentage = (international / total) * 100
        result_string = f"Percent international: {percentage:.2f}%"

    if print_string:
        print(f"2. {result_string}")
    else:
        return result_string


def _question_3(session, print_string=True):
    """
    Question 3: What is the average GPA, GRE Quantitative, GRE
    Verbal, and GRE Analytical Writing scores of applicants
    who provide each metric?
    """
    gpa_statement = select(func.round(cast(func.avg(Applicant.gpa), Numeric), 2))
    gre_statement = select(func.round(cast(func.avg(Applicant.gre), Numeric), 2))
    gre_v_statement = select(func.round(cast(func.avg(Applicant.gre_v), Numeric), 2))
    gre_aw_statement = select(func.round(cast(func.avg(Applicant.gre_aw), Numeric), 2))

    gpa = session.execute(gpa_statement).scalar_one_or_none()
    gre = session.execute(gre_statement).scalar_one_or_none()
    gre_v = session.execute(gre_v_statement).scalar_one_or_none()
    gre_aw = session.execute(gre_aw_statement).scalar_one_or_none()

    result_string_1 = f"Average GPA: {gpa:.2f}"
    result_string_2 = f"Average GRE Quantitative: {gre:.2f}"
    result_string_3 = f"Average GRE Verbal: {gre_v:.2f}"
    result_string_4 = f"Average GRE Analytical Writing: {gre_aw:.2f}"

    if print_string:
        print(f"3. {result_string_1}")
        print(f"3. {result_string_2}")
        print(f"3. {result_string_3}")
        print(f"3. {result_string_4}")
    else:
        return [
            result_string_1,
            result_string_2,
            result_string_3,
            result_string_4,
        ]


def _question_4(session, print_string=True):
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
    result_string = f"Average Fall 2026 American applicant GPA: {result:.2f}"
    if print_string:
        print(f"4. {result_string}")
    else:
        return result_string


def _question_5(session, print_string=True):
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
    if total == 0:
        result_string = "Fall 2025 acceptance percentage: N/A (no Fall 2025 entries)"
    else:
        percentage = (accepted / total) * 100
        result_string = f"Fall 2025 acceptance percentage: {percentage:.2f}%"
    
    if print_string:
        print(f"5. {result_string}")
    else:
        return result_string


def _question_6(session, print_string=True):
    """
    Question 6: What is the average GPA of accepted applicants
    who applied for Fall 2026?
    """
    statement = select(func.round(cast(func.avg(Applicant.gpa), Numeric), 2)).where(
        and_(
            Applicant.term.ilike("Fall 2026"),
            Applicant.status.ilike("Accepted"),
            Applicant.gpa.is_not(None),
        )
    )

    result = session.execute(statement).scalar_one_or_none()
    result_string = f"Average Fall 2026 accepted applicant GPA: {result:.2f}"
    if print_string:
        print(f"6. {result_string}")
    else:
        return result_string


def _question_7(session, print_string=True):
    """
    Question 7: How many entries are from applicants who applied
    to Johns Hopkins University for a master's degree in Computer
    Science?
    """
    university_conditions = [
        Applicant.university.ilike("%Johns Hopkins University%"),
        Applicant.university.ilike("%JHU%"),
    ]
    statement = select(func.count(Applicant.p_id)).where(
        and_(
            or_(*university_conditions),
            Applicant.degree.ilike("Masters"),
            Applicant.program.ilike("Computer Science"),
        )
    )
    result = session.execute(statement).scalar_one()
    result_string = f"JHU Computer Science masters applicants: {result:,}"

    if print_string:
        print(f"7. {result_string}")
    else:
        return result_string


def _question_8(session, print_string=True):
    """
    Question 8:
    How many Fall 2026 entries are acceptances from applicants
    applying for a PhD in Computer Science at one of the
    following universities?
    """

    university_conditions = [
        Applicant.university.ilike("%Georgetown University%"),
        Applicant.university.ilike("%Massachusetts Institute of Technology%"),
        Applicant.university.ilike("MIT"),
        Applicant.university.ilike("%Stanford University%"),
        Applicant.university.ilike("%Carnegie Mellon University%"),
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

    result_string = (
        f"Fall 2026 various university Computer Science PhD acceptances: {result:,}"
    )
    if print_string:
        print(f"8. {result_string}")
    else:
        return result_string


def _question_9(session, print_string=True):
    """
    Question 9:
    How many Fall 2026 entries are acceptances from applicants
    applying for a PhD in Computer Science at one of the
    following universities, comparing the original fields
    with the LLM-adjusted fields?
    """
    original_university_conditions = [
        Applicant.university.ilike("%Georgetown University%"),
        Applicant.university.ilike("%Massachusetts Institute of Technology%"),
        Applicant.university.ilike("MIT"),
        Applicant.university.ilike("%Stanford University%"),
        Applicant.university.ilike("%Carnegie Mellon University%"),
    ]

    llm_university_conditions = [
        Applicant.llm_generated_university.ilike("%Georgetown University%"),
        Applicant.llm_generated_university.ilike("%Massachusetts Institute of Technology%"),
        Applicant.llm_generated_university.ilike("MIT"),
        Applicant.llm_generated_university.ilike("%Stanford University%"),
        Applicant.llm_generated_university.ilike("%Carnegie Mellon University%"),
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

    result_string_1 = f"Original-field count: {original_result:,}"
    result_string_2 = f"LLM-field count: {llm_result:,}"
    result_string_3 = f"Difference: {original_result - llm_result:,}"

    if print_string:
        print(f"9. {result_string_1}")
        print(f"9. {result_string_2}")
        print(f"9. {result_string_3}")
    else:
        return [result_string_1, result_string_2, result_string_3]


def _question_10(session, print_string=True):
    """
    Question 10: How many entries are applicants applying
    for a Physics PhD at West Virginia University?
    """
    university_conditions = [
        Applicant.university.ilike("%West Virginia University%"),
        Applicant.university.ilike("%WVU%"),
    ]
    statement = select(func.count(Applicant.p_id)).where(
        and_(
            or_(*university_conditions),
            Applicant.program.ilike("Physics"),
            Applicant.degree.ilike("PhD"),
        )
    )

    result = session.execute(statement).scalar_one()
    result_string = f"West Virginia University Physics PhD applicants: {result:,}"

    if print_string:
        print(f"10. {result_string}")
    else:
        return result_string


def _question_11(session, print_string=True):
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

    result_string = f"JHU Masters acceptances average GPA: {result:.2f}"
    if print_string:
        print(f"11. {result_string}")
    else:
        return result_string


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


if __name__ == "__main__": # pragma: no cover
    main()
