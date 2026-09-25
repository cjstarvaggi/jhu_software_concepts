import re
import pytest

from src.app import create_app
from src import orm_queries


@pytest.mark.analysis
def test_analysis_page_contains_answer_labels():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/analysis")

    assert response.status_code == 200
    assert b"Answer:" in response.data


@pytest.mark.analysis
def test_percentages_have_two_decimal_places():
    app = create_app({"TESTING": True})

    with app.test_client() as client:
        response = client.get("/analysis")

    assert response.status_code == 200

    html = response.data.decode("utf-8")
    percentages = re.findall(r"\b\d+(?:\.\d+)?%", html)

    assert percentages
    assert all(re.fullmatch(r"\d+\.\d{2}%", value) for value in percentages)


@pytest.mark.parametrize(
    "question, expected",
    [
        (orm_queries._question_1, "1. Fall 2026 applicant count:"),
        (orm_queries._question_2, "2. Percent international:"),
        (orm_queries._question_3, "3. Average GPA:"),
        (orm_queries._question_4, "4. Average Fall 2026 American applicant GPA:"),
        (orm_queries._question_5, "5. Fall 2025 acceptance percentage:"),
        (orm_queries._question_6, "6. Average Fall 2026 accepted applicant GPA:"),
        (orm_queries._question_7, "7. JHU Computer Science masters applicants:"),
        (orm_queries._question_8, "8. Fall 2026 various university Computer Science PhD acceptances:"),
        (orm_queries._question_9, "9. Original-field count:"),
        (orm_queries._question_10, "10. West Virginia University Physics PhD applicants:"),
        (orm_queries._question_11, "11. JHU Masters acceptances average GPA:"),
    ],
)

@pytest.mark.analysis
def test_orm_questions_print_branches(question, expected, capsys):
    class FakeResult:
        def scalar_one(self):
            return 1

        def scalar_one_or_none(self):
            return 3.50

    class FakeSession:
        def execute(self, statement):
            return FakeResult()

    question(FakeSession())
    output = capsys.readouterr().out

    assert expected in output

@pytest.mark.analysis
def test_orm_queries_main(monkeypatch):
    calls = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(orm_queries, "Session", lambda: FakeSession())

    for name in [
        "_question_1",
        "_question_4",
        "_question_5",
        "_question_8",
        "_question_9",
        "_question_11",
    ]:
        monkeypatch.setattr(orm_queries, name, lambda session, name=name: calls.append(name))

    orm_queries.main()

    assert calls == [
        "_question_1",
        "_question_4",
        "_question_5",
        "_question_8",
        "_question_9",
        "_question_11",
    ]