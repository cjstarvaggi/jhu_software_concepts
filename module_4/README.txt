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
6. Run python models.py and orm_queries.py
7. Run app.py

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

orm_queries.py repeats selected analyses from query_data.py without writing raw SQL 
queries. It creates a SQLAlchemy session and connects to the model in models.py to 
query the applicants table. The script answers Questions 1, 4, 5, 8, 9, and 11; 
GPA averages are similarly cast to Numeric before rounding to two decimal places 
to ensure compatibility with PostgreSQL's data types.

clean.py cleans and standardizes the scraped applicant data before it is loaded into 
PostgreSQL. It reads the applicant records from llm_extend_applicant_data.json, 
checks for records that have already been cleaned, and uses canonical mappings/LLM-
generated fields to standardize program and university names. The cleaned records 
are then saved back to the JSON file so that the resulting data can be used by 
load_data.py.

scrape.py collects applicant data from the Grad Café survey and result pages using 
Selenium and BeautifulSoup. It attaches to a Chrome browser so that Cloudflare 
verification can be completed manually ahead of scraping. The script checks the 
result IDs against the existing applicant data and only retrieves newer records, 
saving the results incrementally to llm_extend_applicant_data.json so that previously 
collected records do not need to be scraped again.

app.py provides the Flask web application used to display the analysis results. The 
script runs ORM queries from orm_queries.py and passes their results to the webpage 
for display. The application also provides controls for pulling new applicant data 
and updating the analysis; the data pull runs through the scraping, cleaning, 
and database-loading process while the analysis update re-queries the current 
PostgreSQL data without starting another scrape.

# PART 7 COMPARISON ANALYSIS:

Question 4 asks the following: what is the average GPA of American applicants who 
applied for Fall 2026? The raw SQL query used to answer this question in query_data.py 
was as follows:

"""
    SELECT ROUND(AVG(gpa)::numeric, 2)
    FROM applicants
    WHERE term = 'Fall 2026'
    AND us_or_international = 'American'
    AND gpa IS NOT NULL;
"""

Meanwhile, the corresponding SQLAlchemy querry was:

select(func.round(cast(func.avg(Applicant.gpa), Numeric), 2)).where(
        and_(
            Applicant.term.ilike("Fall 2026"),
            Applicant.us_or_international.ilike("American"),
            Applicant.gpa.is_not(None),
        )
    )

When examining the two queries, it appears there are advantages and disadvantages
to both approaches. The raw SQL query reads more simply, but may be more difficult
to debug if one doesn't have a good understanding of the object that's being called.
The ORM query by contrast seems more complex but comes with the benefit of accessing
a model whose attributes are neatly stored and easy to access. In my opinion, ORM is
more scalable and enables the user to not have to write specific queries each time
the database must be accessed, whilst the raw queries seem to grant the most 
flexibility as to the types of queries that can be made. 

# LIMITATIONS

The scraper requires Google Chrome and a Windows-specific Chrome executable
path; Cloudflare verification requires a single initial manual interaction.

# KNOWN BUGS

The scraper depends on The Grad Cafe's current HTML structure; as such, changes
to the site's page layout, field ordering, or pagination could cause incorrect
or missing data. The result parser also relies on fixed <dd> element positions;
a more robust version would identify fields by their labels.

The GPU acceleration settings utilized to offload additional threads may not
be compatible with other machines; this can be resolved be changing 
N_GPU_LAYERS back to 0 for CPU-only processing, though it will significantly
slow down the process.

Whilst some fine-tuning of the model was able to fix some of the original 
LLM standardization issues, some may undoubtedly persist leading to minor
spelling errors in some llm generated json fields.