Testing Guide
===============

Test Markers
-------------

All tests are marked with the following Pytest markers:

* :file:`@pytest.mark.web` — page load / HTML structure.
* :file:`@pytest.mark.buttons` — button endpoints & busy-state behavior.
* :file:`@pytest.mark.analysis` — labels and percentage formatting.
* :file:`@pytest.mark.db` — database schema/inserts/selects.
* :file:`@pytest.mark.integration` — end-to-end flows.

Several fixtures are included as well; they are distinguished in the Reference
below by not being preceeded by ``test_``.

Running Tests
-------------

The automated test suite is run with ``pytest``; running the command
below from the project root will test the entire stack:

.. code-block:: powershell

   pytest -m "web or buttons or analysis or db or integration"

To run the tests with coverage:

.. code-block:: powershell

   pytest -m "web or buttons or analysis or db or integration" --cov=src


Test Reference
--------------

.. toctree::
   :maxdepth: 2
   
   tests/test_flask_page
   tests/test_buttons
   tests/test_analysis_format
   tests/test_db_insert
   tests/test_integration_end_to_end