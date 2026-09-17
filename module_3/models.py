import os

from dotenv import load_dotenv
from sqlalchemy import Column, Date, Integer, Numeric, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()


DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

DATABASE_URL = (
    f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Applicant(Base):
    """
    SQLAlchemy model for the existing applicants table.
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