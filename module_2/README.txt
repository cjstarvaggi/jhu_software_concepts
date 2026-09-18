Name: Carl Starvaggi
JHED ID: cstarva1

Module: 2
Assignment: Web Scraping
Due Date: 09/13/2026

# RUN INSTRUCTIONS

1. Download and extract the files
2. pip install -r requirements.txt
3. Run robots_check.py, 
4. Run scrape.py
5. Run clean.py

# APPROACH

robots_check.py uses urllib.robotparser to check whether the site's
landing page ("/") and survey page ("/survey/") are permitted by robots.txt;
screenshot.jpg documents the results.

scraper.py uses a Selenium + Chrome + BeautifulSoup workflow; Chrome is
launched and manually verified through Cloudflare, after which Selenium
attaches to the browser through its remote debugging port. Result pages
are fetched using JavaScript fetch() within the verified browser session
and parsed with BeautifulSoup. urllib.parse.urljoin is only used for
constructing URLs.

Applicant data is stored as dictionaries in applicant_data.json. Results are
processed in batches of 20 (skipping duplicate URLs to retain efficiency);
scraping continues until 50,000 records are collected. scrape_progress.json
allows the scraper to resume from the last completed survey page. Data and
progress are saved using temporary files and checkpoints to reduce the
risk of losing progress.

clean.py loads the scraped applicant data and checks each program and
university against the canonical lists before using the LLM. Values that match
the canonical lists are used directly, avoiding an unnecessary LLM call.
Non-canonical fields are sent to the LLM for standardization, while canonical
fields are preserved. The script processes records sequentially, maintains
their original order, and reports canonical matches, skipped LLM calls, LLM
calls, processing rate, and elapsed time. The cleaned records are saved to 
llm_extended_applicant_data.json.

# LLM STANDARDIZER UPDATES

The original standardizer was updated to make normalization more reliable and
prevent unnecessary LLM changes. Canonical university and program lists are
now loaded relative to the script directory, and case/whitespace-insensitive
canonical matching was added so existing valid entries are preserved.

Post-processing was expanded with additional corrections for common LLM
spelling errors, tighter fuzzy-match thresholds, and parenthetical text
removal. Program and university values are now normalized independently rather
than being treated as one combined field.

The LLM prompt was rewritten to be more conservative, instructing the model
to preserve valid names and avoid inventing spelling changes. Canonical matches
are now marked as verified and protected from LLM modification; only fields
that do not match the canonical lists are allowed to be standardized.

The LLM hosting configuration was also changed from CPU-only execution to GPU
acceleration with N_GPU_LAYERS = -1. The model now uses a fixed 2 threads and
2048-token context, while the existing Hugging Face GGUF download and
in-memory model caching remain in place.

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

In some instances, running the scraper for extended periods of time would lead 
the current chrome webpage to crash; the scraper was written to allow a manual
reload within five seconds of this happening.
