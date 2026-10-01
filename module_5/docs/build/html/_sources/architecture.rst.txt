Architecture
===============

The application is organized into three primary layers: the web layer,
the ETL layer, and the database layer.

Web Layer
--------------

The web layer is implemented using Flask and is responsible for providing
the application's HTTP interface.

The primary responsibilities of this layer include:

* Creating and configuring the Flask application.
* Registering application routes.
* Receiving requests from the user.
* Returning HTML pages and API responses.
* Initiating data-processing operations through the application's
  underlying modules.

The primary web application functionality is located in
:mod:`src.app`.

ETL Layer
--------------

The ETL layer is responsible for extracting applicant information,
transforming and cleaning the collected data, and preparing records for
storage.

The primary responsibilities include:

* Scraping applicant information from source pages.
* Loading collected data.
* Cleaning and standardizing applicant records.
* Normalizing program and university information.
* Preparing records for database insertion.

The primary ETL functionality is distributed across
:mod:`src.scrape`, :mod:`src.load_data`, and :mod:`src.clean`.

Database Layer
--------------

The database layer provides the persistent storage and database-access
functionality for applicant records.

The primary responsibilities include:

* Defining the database schema through SQLAlchemy ORM models.
* Representing applicant records with the ``Applicant`` model.
* Creating and managing database sessions.
* Inserting and querying applicant records.
* Retrieving applicant information for use by the application.

The ORM model is defined in :mod:`src.models`, while database queries and
related operations are implemented in :mod:`src.orm_queries`.

Layer Interaction
-----------------

The three layers work together as follows:

.. code-block:: text

   Web Layer
   src.app
       |
       v
   ETL Layer
   src.scrape -> src.load_data -> src.clean
       |
       v
   Database Layer
   src.models / src.orm_queries
       |
       v
   PostgreSQL Database

The web layer provides the user-facing interface, the ETL layer processes
applicant data, and the database layer provides persistent storage and
retrieval.