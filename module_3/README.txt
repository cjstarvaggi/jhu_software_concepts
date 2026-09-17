Name: Carl Starvaggi
JHED ID: cstarva1

Module: 3
Assignment: Database Queries Assignment 
Due Date: 09/20/2026

# RUN INSTRUCTIONS

1. Extract the files
2. Install the required Python packages: pip install -r requirements.txt
3. Create a .env file containing the PostgreSQL database connection information.
4. Run load_data.py
5. Run python query_data.py

# APPROACH

load_data.py loads the cleaned applicant data from llm_extend_applicant_data.json, 
transforms each record into a format compatible with PostgreSQL, and then creates 
the applicants table if it doesn't already exist. Valid records are inserted 
into the database or updated when an existing applicant ID is found, while records 
with invalid or missing IDs are skipped.

query_data.py connects to the PostgreSQL database and contains a separate function 
for each assignment question. Each function submits a SQL query to calculate the 
requested count, percentage, or average; the results are then printed in the 
suggested formatting.

models.py defines the Applicant SQLAlchemy model used to represent the applicants 
table. It maps each table column to the appropriate SQLAlchemy data type and 
defines p_id as the primary key. The file also loads the database connection 
settings from the .env file and creates the SQLAlchemy engine, session, and 
declarative base used to interact with the database.

# LIMITATIONS

No known limitations.

# KNOWN BUGS

No known bugs.