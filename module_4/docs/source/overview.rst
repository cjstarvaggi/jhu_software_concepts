Overview & Setup
================

This project is a Flask-based applicant data application that collects,
cleans, stores, and analyzes graduate applicant data. It includes a web
application, an ETL pipeline, a PostgreSQL database, and automated tests.

Setup
~~~~~~~~~~~~~~~~~~~~~~

Before running the application, install the project's required Python
dependencies and configure the required environment variables. The 
Python dependencies can be found in :file:`requirements.txt` in the project's
root folder

Environment Variables
~~~~~~~~~~~~~~~~~~~~~~

The application requires several environmental variables in order to run properly
execute. The two most important are ``DATABASE_URL`` (which contains the connection 
string for the PostgreSQL database) and ``DATA_FILE`` (which contains the location
of the applicants JSON file).

For example:

.. code-block:: text

   DATABASE_URL=postgresql://[POSTGRES_USER]:[POSTGRES_PASSWORD]@[POSTGRES_HOST]:[POSTGRES_PORT]/[POSTGRES_DB]
   DATA_FILE=src/llm_extend_applicant_data.json


Additional environment variables ``POSTGRES_HOST``, ``POSTGRES_PORT``,
``POSTGRES_DB``, ``POSTGRES_USER``, and ``POSTGRES_PASSWORD``, are required
to run tests; all environmental variables should be defined in the 
project's ``.env`` file.

Running the Application
~~~~~~~~~~~~~~~~~~~~~~~

From the project root, cd to the :file:`src` folder; then start Flask with:

.. code-block:: powershell

   python -m app

The application can then be accessed through the local address reported by
Flask.
