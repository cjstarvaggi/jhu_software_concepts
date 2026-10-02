Name: Carl Starvaggi
JHED ID: cstarva1

Module: 4
Assignment: Testing and Documentation
Due Date: 09/27/2026

# RUN INSTRUCTIONS

1. Extract the files
2. Follow the steps in the Fresh Install section below as they pertain to your
particular operating system.
3. From the project root, cd to the src folder; create a .env file containing 
the PostgreSQL database connection information modeled by .env.example.
5. From the project root, cd to the src folder; then run python -m app
6. Run the full test suite from the project root using the command:
pytest -m "web or buttons or analysis or db or integration" --cov=src

# Fresh Install

1. Create and activate a virtual environment:
    • If using pip, use the bash command $python -m venv .venv
    • If using uv, use the bash command $uv venv

2. Activate the virtual environment:
    • Windows: $.venv\Scripts\activate
    • macOS/Linux: $source .venv/bin/activate

3. Install the dependencies:
    • If using just pip:
        • Run the bash command: $pip install -e .
        • Run the bash command: $pip install -r requirements.txt
    • If using pip and uv:
        • Run the bash command: $uv pip install -e .
        • Run the bash command: $uv pip sync requirements.txt

# APPROACH

load_data.py loads the cleaned applicant data from llm_extend_applicant_data.json, 
transforms each record into a format compatible with PostgreSQL, and then creates 
the applicants table if it doesn't already exist. Valid records are inserted 
into the database or updated when an existing applicant ID is found, while records 
with invalid or missing IDs are skipped.

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

The tests folder contains a number of tests that can be utilized to verify the flow 
of the application from start to end. Every aspect of the code is checked utilizing
the command pytest -m "web or buttons or analysis or db or integration" or after
commit to the github repository via an automated GitHub Actions workflow. Sphinx-enabled
documentation is also provided for every major class and function in the program.

Every script in the src folder has been linted with the pylint library to ensure
security compliance, with additional checks completed by snyk cli and snyk code.
Addressed vulnerabilities are documented in the SECURITY section below.

# SECURITY

During a run of Snyk CLI, a vulnerability was found within the installed llama-ccp-python
library, tied to a diskcache import within the package; the vulnerability persisted even 
though the program doesn't touch the affected part of the package. A pull request on the 
official repo page documenting the issue, but due to it not being resolved as of project
submission, the package was manually patched to remove the vulnerable package. The patched
package is included in the vendor folder and has been added to the requirements text file.

Running Snyk Code revealed seven minor issues, all related to unsanitized inputs directly 
inside file-handling functions like open() and json.dump() in the llm_hosting and patched
llama_ccp folders. Due to their low risk nature, it wasn't necessary to overhaul those
sections of the script.

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