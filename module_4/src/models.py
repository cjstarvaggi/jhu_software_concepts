import os

from dotenv import load_dotenv
from sqlalchemy import Column, Date, Integer, Numeric, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")


engine = create_engine(DATABASE_URL.replace("postgresql", "postgresql+psycopg"))
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Applicant(Base):
    """
    SQLAlchemy ORM model for the existing ``applicants`` database table.

    The model maps applicant records to their corresponding PostgreSQL
    columns and uses ``p_id`` as the primary key.

    :ivar p_id: Unique identifier for the applicant record.
    :type p_id: sqlalchemy.Column
    :ivar program: Applicant's program name.
    :type program: sqlalchemy.Column
    :ivar university: Applicant's university.
    :type university: sqlalchemy.Column
    :ivar comments: Applicant's comments or additional information.
    :type comments: sqlalchemy.Column
    :ivar date_added: Date the applicant record was added.
    :type date_added: sqlalchemy.Column
    :ivar url: URL of the applicant's source record.
    :type url: sqlalchemy.Column
    :ivar status: Applicant's application status.
    :type status: sqlalchemy.Column
    :ivar term: Application start term.
    :type term: sqlalchemy.Column
    :ivar us_or_international: Applicant nationality or international status.
    :type us_or_international: sqlalchemy.Column
    :ivar gpa: Applicant's GPA.
    :type gpa: sqlalchemy.Column
    :ivar gre: Applicant's overall GRE score.
    :type gre: sqlalchemy.Column
    :ivar gre_v: Applicant's GRE verbal score.
    :type gre_v: sqlalchemy.Column
    :ivar gre_aw: Applicant's GRE analytical writing score.
    :type gre_aw: sqlalchemy.Column
    :ivar degree: Applicant's degree type.
    :type degree: sqlalchemy.Column
    :ivar llm_generated_program: LLM-generated standardized program name.
    :type llm_generated_program: sqlalchemy.Column
    :ivar llm_generated_university: LLM-generated standardized university
        name.
    :type llm_generated_university: sqlalchemy.Column
    """

    __tablename__ = "applicants"

    p_id = Column(Integer, primary_key=True)
    program = Column(Text)
    university = Column(Text)
    comments = Column(Text)
    date_added = Column(Date)
    url = Column(Text)
    status = Column(Text)
    term = Column(Text)
    us_or_international = Column(Text)
    gpa = Column(Numeric)
    gre = Column(Numeric)
    gre_v = Column(Numeric)
    gre_aw = Column(Numeric)
    degree = Column(Text)
    llm_generated_program = Column(Text)
    llm_generated_university = Column(Text)
