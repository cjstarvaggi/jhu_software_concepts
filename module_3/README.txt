Name: Carl Starvaggi
JHED ID: cstarva1

Module: 3
Assignment: Database Queries Assignment 
Due Date: 09/20/2026

# RUN INSTRUCTIONS

1. Extract the files
2. pip install -r requirements.txt
3. run load_data.py, 

# APPROACH

load_data.py loads the cleaned applicant data from llm_extend_applicant_data.json, 
transforms each record into a format compatible with PostgreSQL, and then creates 
the applicants table if it doesn't already exist. Valid records are inserted 
into the database or updated when an existing applicant ID is found, while records 
with invalid or missing IDs are skipped.

# LIMITATIONS

No known limitations.

# KNOWN BUGS

No known bugs.