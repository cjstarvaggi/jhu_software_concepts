Name: Carl Starvaggi
JHED ID: cstarva1

Module: 2
Assignment: Web Scraping
Due Date: 09/13/2026

# APPROACH

`robots_check.py` uses `urllib.robotparser` to check whether the site's 
landing page ("/") and survey page ("/survey/") are permitted by robots.txt;
`screenshot.jpg` documents the results.

`scraper.py` uses a Selenium + Chrome + BeautifulSoup workflow; Chrome is
launched and manually verified through Cloudflare, after which Selenium 
attaches to the browser through its remote debugging port. Result pages 
are fetched using JavaScript `fetch()` within the verified browser session 
and parsed with BeautifulSoup. `urllib.parse.urljoin` is only used for 
constructing URLs.

Applicant data is stored as dictionaries in `applicant_data.json`. Results are
processed in batches of 20 (skipping duplicate URLs to retain efficiency); 
scraping continues until 50,000 records are collected. `scrape_progress.json` 
allows the scraper to resume from the last completed survey page. Data and 
progress are saved using temporary files and checkpoints to reduce the 
risk of losing progress.

# KNOWN BUGS

The scraper depends on The Grad Cafe's current HTML structure; as such, changes 
to the site's page layout, field ordering, or pagination could cause incorrect 
or missing data. The result parser also relies on fixed `<dd>` element positions;
a more robust version would identify fields by their labels.

The scraper requires Google Chrome and a Windows-specific Chrome executable
path; Cloudflare verification requires manual interaction.
