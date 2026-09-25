import json
import os
import re
import subprocess
import time

from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

batch_size = 20
data_file_name = os.path.join("src", "llm_extend_applicant_data.json")
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
chrome_profile = r"C:\temp\selenium-chrome"
chrome_port = 9222
base_url = "https://www.thegradcafe.com"
survey_url = urljoin(base_url, "/survey")


def _new_applicant_item():
    """
    Create a new applicant record with all supported fields initialized
    to ``None``.

    :returns: A dictionary containing the fields used to represent a
        scraped applicant record.
    :rtype: dict
    """

    return {
        "program_name": None,
        "university": None,
        "comments": None,
        "date_added": None,
        "url": None,
        "applicant_status": None,
        "acceptance_date": None,
        "rejected_date": None,
        "wait_list_date": None,
        "interview_date": None,
        "start_term": None,
        "nationality": None,
        "gre_score": None,
        "gre_v_score": None,
        "degree_type": None,
        "gpa": None,
        "gre_aw": None,
    }


def _load_data():
    """
    Load previously scraped applicant records from the configured
    JSON data file.

    If the data file does not exist, an empty list is returned. The
    loaded JSON value must be a list of records.

    :returns: Previously stored applicant records, or an empty list if
        the data file does not exist.
    :rtype: list
    :raises ValueError: If the loaded JSON value is not a list.
    """

    if not os.path.exists(data_file_name):
        return []

    with open(data_file_name, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Applicant data must be a list of records.")

    return data


def save_data(data):
    """
    Safely persist applicant data to the configured JSON file.

    The data is first written to a temporary file and then moved into
    place with ``os.replace`` so that a failure during the write is less
    likely to destroy the previous checkpoint.

    :param data: Applicant records to serialize to JSON.
    :type data: list
    """

    temp_file = data_file_name + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    os.replace(temp_file, data_file_name)


def _get_result_id(url):
    """
    Extract the numeric Grad Cafe result ID from a result URL.

    URLs are expected to end with ``/result/<id>``. Invalid, missing, or
    non-matching URLs return ``None``.

    :param url: Grad Cafe result URL to inspect.
    :type url: str or None
    :returns: The numeric result ID, or ``None`` if it cannot be extracted.
    :rtype: int or None
    """

    if not url:
        return None

    match = re.search(r"/result/(\d+)$", url)

    if not match:
        return None

    return int(match.group(1))


def _get_highest_result_id(data):
    """
    Find the highest Grad Cafe result ID already stored in the applicant
    data.

    :param data: Previously scraped applicant records.
    :type data: list
    :returns: The highest result ID found, or ``0`` if no valid result IDs
        are present.
    :rtype: int
    """

    highest_result_id = 0

    for item in data:
        result_id = _get_result_id(item.get("url"))

        if result_id is not None and result_id > highest_result_id:
            highest_result_id = result_id

    return highest_result_id


def _initialize_chrome(url, port=chrome_port):
    """
    Launch a Chrome instance configured for Selenium remote debugging.

    The browser uses the configured user profile so the user can complete
    Cloudflare verification manually. Selenium can subsequently attach to
    the running browser through the specified debugging port.

    Several Chrome background services are disabled to reduce unnecessary
    browser activity during scraping.

    :param url: URL to open when Chrome starts.
    :type url: str
    :param port: Remote debugging port used by Selenium.
    :type port: int
    :returns: The subprocess representing the launched Chrome instance.
    :rtype: subprocess.Popen
    """

    process = subprocess.Popen(
        [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={chrome_profile}",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            url,
        ]
    )

    return process


def _commandeer_chrome(port=chrome_port):
    """
    Create a Selenium WebDriver attached to an already running Chrome
    instance through its remote debugging port.

    The page load strategy is set to ``eager`` so Selenium can continue
    once the initial HTML document has been loaded without waiting for
    every page resource to finish.

    :param port: Remote debugging port exposed by the running Chrome
        instance.
    :type port: int
    :returns: A Selenium Chrome WebDriver attached to the existing browser.
    :rtype: selenium.webdriver.Chrome
    """

    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")

    options.page_load_strategy = "eager"

    return webdriver.Chrome(options=options)


def _scrape_survey_page(driver, url):
    """
    Scrape a Grad Cafe survey page for result metadata and result URLs.

    The page is loaded through the supplied Selenium driver. Applicant
    metadata such as the date added, GPA, and start term is extracted from
    the survey table, while result links and the pagination link are
    collected separately.

    :param driver: Selenium WebDriver used to load the survey page.
    :type driver: selenium.webdriver.Chrome
    :param url: Survey page URL to scrape.
    :type url: str
    :returns: A tuple containing survey table metadata, result URLs, and
        the URL of the next survey page. The tuple has the form
        ``(table_info, results, next_link)``.
    :rtype: tuple
    """

    driver.get(url)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    table_info = []

    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)

        if len(cells) != 5:
            continue

        date_added = cells[2].get_text(strip=True)
        sibling = row.find_next_sibling("tr")

        if not sibling:
            continue

        text = sibling.get_text(" ", strip=True)
        gpa_match = re.search(r"GPA\s+([\d.]+)", text)
        term_match = re.search(r"(Spring|Summer|Fall|Winter)\s+\d{4}", text)

        table_info.append(
            {
                "date_added": date_added,
                "gpa": (gpa_match.group(1) if gpa_match else None),
                "term": (term_match.group(0) if term_match else None),
            }
        )

    result_links = soup.find_all("a", href=re.compile(r"^/result/\d+$"))
    results = [urljoin(url, link["href"]) for link in result_links]

    next_link = None

    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        if text.lower() == "next":
            next_link = urljoin(url, link["href"])
            break

    return (table_info, results, next_link)


def _fetch_pages_in_browser(driver, urls):
    """
    Fetch multiple result pages concurrently from within an existing
    Cloudflare-verified Chrome session.

    JavaScript ``fetch`` requests are executed inside the browser so the
    browser's cookies and authenticated session can be reused. Each result
    contains the requested URL, HTTP status, response HTML when available,
    and an error message when the browser-side request fails.

    :param driver: Selenium WebDriver attached to the active Chrome session.
    :type driver: selenium.webdriver.Chrome
    :param urls: Result page URLs to fetch.
    :type urls: list[str]
    :returns: Browser fetch results for each requested URL.
    :rtype: list
    """

    if not urls:
        return []

    script = """
    const urls = arguments[0];
    const callback = arguments[arguments.length - 1];

    Promise.all(urls.map(async (url) => {
            try {
                const response = await fetch(
                    url,
                    {
                        credentials: "include"
                    }
                );

                if (!response.ok) {

                    return {
                        url: url,
                        status: response.status,
                        html: null
                    };

                }

                return {
                    url: url,
                    status: response.status,
                    html: await response.text()
                };

            } catch (error) {

                return {
                    url: url,
                    status: 0,
                    html: null,
                    error: String(error)
                };

            }

        })
    ).then(callback);
    """

    return driver.execute_async_script(script, urls)


def _scrape_result_page_html(
    html,
    url,
    date_added=None,
    gpa=None,
    start_term=None,
):
    """
    Parse a single Grad Cafe applicant result page into a standardized
    applicant record.

    Applicant fields are extracted from the page's ``dd`` elements.
    Status-specific dates are identified from the status field, while
    optional survey metadata such as the date added, GPA, and start term
    is supplied separately.

    The result page is expected to contain at least ten ``dd`` elements.

    :param html: HTML source for the applicant result page.
    :type html: str
    :param url: URL of the applicant result page.
    :type url: str
    :param date_added: Date the result was added to the survey, if known.
    :type date_added: str or None
    :param gpa: GPA extracted from the survey page, if available.
    :type gpa: str or None
    :param start_term: Starting academic term extracted from the survey
        page, if available.
    :type start_term: str or None
    :returns: A standardized applicant record with missing values represented
        by ``None``.
    :rtype: dict
    :raises ValueError: If the result page does not contain the expected
        minimum number of fields.
    """

    item = _new_applicant_item()
    soup = BeautifulSoup(html, "html.parser")
    column_fields_html = soup.find_all("dd")

    if len(column_fields_html) < 10:
        raise ValueError("Unexpected result page structure")

    item["university"] = column_fields_html[0].get_text(" ", strip=True)
    item["program_name"] = column_fields_html[1].get_text(" ", strip=True)
    item["degree_type"] = column_fields_html[2].get_text(" ", strip=True)
    item["nationality"] = column_fields_html[3].get_text(" ", strip=True)
    item["applicant_status"] = column_fields_html[4].get_text(" ", strip=True)

    status_text = column_fields_html[5].get_text(" ", strip=True)
    date_match = re.search(r"\d{2}/\d{2}/\d{4}", status_text)

    if date_match:
        date_value = date_match.group()
        if item["applicant_status"] == "Accepted":
            item["acceptance_date"] = date_value
        elif item["applicant_status"] == "Rejected":
            item["rejected_date"] = date_value
        elif item["applicant_status"] == "Wait listed":
            item["wait_list_date"] = date_value
        elif item["applicant_status"] == "Interview":
            item["interview_date"] = date_value

    item["gre_score"] = column_fields_html[7].get_text(" ", strip=True)
    item["gre_v_score"] = column_fields_html[8].get_text(" ", strip=True)
    item["gre_aw"] = column_fields_html[9].get_text(" ", strip=True)

    item["gpa"] = gpa
    item["start_term"] = start_term
    item["url"] = url

    if date_added:
        try:
            item["date_added"] = datetime.strptime(date_added, "%b %d, %Y").strftime(
                "%m/%d/%Y"
            )

        except ValueError:
            item["date_added"] = date_added

    if "Notes" in html and len(column_fields_html) > 10:
        item["comments"] = column_fields_html[10].get_text(" ", strip=True)

    return {
        key: (None if value == "Not provided" else value) for key, value in item.items()
    }


def _process_batch(driver, batch, existing_urls):
    """
    Fetch and parse one batch of applicant result pages.

    Result pages are fetched through the active browser session, parsed into
    applicant records, and filtered against URLs that have already been
    stored. Successfully processed URLs are added to ``existing_urls`` to
    prevent duplicate records during the current scraping run.

    :param driver: Selenium WebDriver attached to the active Chrome session.
    :type driver: selenium.webdriver.Chrome
    :param batch: Applicant result metadata for the pages to process.
    :type batch: list[dict]
    :param existing_urls: Set of result URLs already stored or processed.
    :type existing_urls: set
    :returns: Newly parsed applicant records from the batch.
    :rtype: list
    """

    urls = [item["url"] for item in batch]

    metadata = {item["url"]: item for item in batch}

    print(f"Fetching {len(urls)} result pages...")

    start_time = time.perf_counter()
    fetched = _fetch_pages_in_browser(driver, urls)

    records = []

    for result in fetched:
        result_url = result["url"]
        html = result["html"]

        if not html:
            print(f"FAILED: {result_url} " f"(HTTP {result.get('status')})")
            continue

        if result_url in existing_urls:
            continue

        info = metadata.get(result_url, {})

        try:
            item = _scrape_result_page_html(
                html,
                result_url,
                info.get("date_added"),
                info.get("gpa"),
                info.get("term"),
            )
        except Exception as e:
            print(f"PARSE ERROR: {result_url}: {e}")
            continue

        records.append(item)
        existing_urls.add(result_url)

    elapsed = time.perf_counter() - start_time

    print(f"Added {len(records)} records " f"in {elapsed:.2f}s")

    return records


def scrape_data(survey_url, authentication_event=None):
    """
    Incrementally scrape Grad Cafe applicant data and persist checkpoints.

    Previously stored applicant records are loaded first. The highest
    existing result ID is used to determine where previously scraped data
    ends, allowing the scraper to process only newer results. Result pages
    are fetched in batches through a Chrome session that can be manually
    authenticated through Cloudflare.

    Progress is checkpointed to the configured JSON data file after each
    batch and during recoverable errors. Scraping stops when an existing
    result is reached, pagination ends, or a pagination loop is detected.

    :param survey_url: URL of the Grad Cafe survey page from which scraping
        should begin.
    :type survey_url: str
    :param authentication_event: Optional synchronization event that, when
        provided, is waited on after Chrome is initialized and before
        Selenium attaches to the browser.
    :type authentication_event: threading.Event or None
    :returns: The complete applicant dataset after the scraping run.
    :rtype: list
    """

    data = _load_data()

    existing_urls = {item["url"] for item in data if item.get("url")}

    highest_result_id = _get_highest_result_id(data)

    print(f"Existing records:    {len(data):,}")
    print(f"Highest result ID:   {highest_result_id:,}")

    if highest_result_id == 0:
        print("No existing result IDs found.")

    print()
    print("Starting from the beginning...")

    current_url = survey_url
    page_number = 1
    new_records = 0

    _initialize_chrome(survey_url)

    if authentication_event is not None:
        authentication_event.wait()

    driver = _commandeer_chrome()

    try:
        while True:
            print()
            print(f"SURVEY PAGE {page_number}")

            try:
                (
                    table_info,
                    result_urls,
                    next_url,
                ) = _scrape_survey_page(driver, current_url)

            except Exception as e:
                print()
                print(f"ERROR loading survey page " f"{page_number}:")
                print(e)
                save_data(data)
                print("Data checkpoint saved")
                print("Retrying in 5 seconds...")

                time.sleep(5)
                continue

            print(f"Found {len(result_urls)} result URLs")
            print(f"Next page: {next_url or 'NONE'}")

            new_results = []
            reached_existing_data = False

            for i, result_url in enumerate(result_urls):
                result_id = _get_result_id(result_url)

                if result_id is None:
                    continue

                if result_id <= highest_result_id:
                    reached_existing_data = True
                    continue

                if result_url in existing_urls:
                    continue

                if i < len(table_info):
                    info = table_info[i]

                else:
                    info = {
                        "date_added": None,
                        "gpa": None,
                        "term": None,
                    }

                new_results.append(
                    {
                        "url": result_url,
                        "date_added": info["date_added"],
                        "gpa": info["gpa"],
                        "term": info["term"],
                    }
                )

            print(f"New results: " f"{len(new_results)}")

            for start in range(0, len(new_results), batch_size):
                batch = new_results[start : start + batch_size]

                records = _process_batch(
                    driver,
                    batch,
                    existing_urls,
                )

                data = records + data
                new_records += len(records)

                print(f"TOTAL: {len(data):,}")

                save_data(data)

                print("Data checkpoint saved")

            if reached_existing_data:
                print()
                print("Reached existing data.")
                print("Scraping stopped safely.")
                break

            if not next_url:
                print()
                print(f"WARNING: No Next link found " f"on page {page_number}")
                print("Scraping stopped safely")
                save_data(data)

                break

            if next_url == current_url:
                print()
                print("WARNING: Next URL is the same " "as the current URL")
                print("Stopping to prevent an infinite loop")
                save_data(data)

                break

            current_url = next_url
            page_number += 1

            print()
            print(f"Moving to page {page_number}")

            time.sleep(0.2)

    finally:
        save_data(data)
        print()
        print(f"New records: {new_records:,}")
        print(f"Total records: {len(data):,}")

        driver.quit()

    return data


if __name__ == "__main__":  # pragma: no cover
    scrape_data(survey_url)

    print()
    print("Done!")