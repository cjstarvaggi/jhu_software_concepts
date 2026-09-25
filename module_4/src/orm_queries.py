from sqlalchemy import Numeric, and_, cast, func, or_, select

from models import Applicant, Session


def get_applicant(p_id):
    """
    Retrieve an applicant by primary key and return its fields as a dictionary.

    A SQLAlchemy session is created for the lookup and closed after the
    operation completes, including when an exception is raised.

    :param p_id: Primary key of the applicant to retrieve.
    :type p_id: int
    :returns: Applicant fields as a dictionary, or ``None`` if no applicant
        exists with the specified primary key.
    :rtype: dict or None
    """
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
    Count applicants who applied for Fall 2026.

    :param session: Active SQLAlchemy session used to execute the query.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted applicant count when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Calculate the percentage of classified applicants who are international.

    Only records with a non-NULL nationality classification are included in
    the denominator. Two international classifications are counted as
    international applicants.

    :param session: Active SQLAlchemy session used to execute the queries.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted percentage when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Calculate average GPA, GRE Quantitative, GRE Verbal, and GRE Analytical
    Writing scores across applicants who provide each metric.

    :param session: Active SQLAlchemy session used to execute the queries.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted results. If
        ``False``, return the results as a list of strings instead.
    :type print_string: bool
    :returns: A list of formatted average-score strings when ``print_string``
        is ``False``. Otherwise, returns ``None``.
    :rtype: list[str] or None
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
    Calculate the average GPA of American applicants who applied for Fall
    2026 and reported a GPA.

    :param session: Active SQLAlchemy session used to execute the query.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted average GPA when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Calculate the percentage of Fall 2025 entries that are acceptances.

    :param session: Active SQLAlchemy session used to execute the queries.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted acceptance percentage when ``print_string`` is
        ``False``. Otherwise, returns ``None``.
    :rtype: str or None
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
    Calculate the average GPA of accepted applicants who applied for Fall
    2026 and reported a GPA.

    :param session: Active SQLAlchemy session used to execute the query.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted average GPA when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Count applicants who applied to Johns Hopkins University for a master's
    degree in Computer Science.

    The university filter matches either ``Johns Hopkins University`` or
    ``JHU``.

    :param session: Active SQLAlchemy session used to execute the query.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted applicant count when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Count Fall 2026 acceptances for Computer Science PhD applicants at the
    specified universities.

    The university filter includes Georgetown University, Massachusetts
    Institute of Technology, MIT, Stanford University, and Carnegie Mellon
    University.

    :param session: Active SQLAlchemy session used to execute the query.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted acceptance count when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Compare Fall 2026 Computer Science PhD acceptance counts at the
    specified universities using original and LLM-adjusted fields.

    The original-field query uses ``university`` and ``program``, while the
    LLM-adjusted query uses ``llm_generated_university`` and
    ``llm_generated_program``.

    :param session: Active SQLAlchemy session used to execute the queries.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted results. If
        ``False``, return the results as a list of strings instead.
    :type print_string: bool
    :returns: A list containing the original count, LLM-adjusted count, and
        their difference when ``print_string`` is ``False``. Otherwise,
        returns ``None``.
    :rtype: list[str] or None
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
    Count applicants applying for a Physics PhD at West Virginia University.

    The university filter matches either ``West Virginia University`` or
    ``WVU``.

    :param session: Active SQLAlchemy session used to execute the query.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted applicant count when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Calculate the average GPA of accepted master's applicants to Johns
    Hopkins University who reported a GPA.

    The university filter matches either ``Johns Hopkins University`` or
    ``JHU``.

    :param session: Active SQLAlchemy session used to execute the query.
    :type session: sqlalchemy.orm.Session
    :param print_string: If ``True``, print the formatted result. If
        ``False``, return the formatted result instead.
    :type print_string: bool
    :returns: Formatted average GPA when ``print_string`` is ``False``.
        Otherwise, returns ``None``.
    :rtype: str or None
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
    Create a SQLAlchemy session and run the selected applicant queries.

    :returns: ``None``.
    :rtype: None
    """
    with Session() as session:
        _question_1(session)
        _question_4(session)
        _question_5(session)
        _question_8(session)
        _question_9(session)
        _question_11(session)


if __name__ == "__main__":  # pragma: no cover
    main()
