Operational Notes
=================

Troubleshooting
~~~~~~~~~~~~~~~~~~~~~~

When running the full test suite locally, some tests may take a few seconds to complete. The full suite should 
be complete in under a minute.

When running the full suite via the GitHub Actions pipeline, the full suite may take a few minutes to complete.
This is primarily due to the fact that dependencies like cp-llama must be installed in the linux environment
prior to actually executing the script.