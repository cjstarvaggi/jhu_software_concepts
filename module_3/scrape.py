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
data_file_name = "llm_extend_applicant_data.json"
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
chrome_profile = r"C:\temp\selenium-chrome"
chrome_port = 9222
base_url = "https://www.thegradcafe.com"
survey_url = urljoin(base_url, "/survey")


def _new_applicant_item():
    """
    Returns a dataframe of all the desired categories with default
    None values for each
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
    Loads the previously scraped applicant data
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
    Safely saves the applicant data by writing to a temporary file
    first so a crash during writing doesn't destroy the previous checkpoint
    """

    temp_file = data_file_name + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    os.replace(temp_file, data_file_name)


def _get_result_id(url):
    """
    Extracts the Grad Cafe result ID from a result URL
    """

    if not url:
        return None

    match = re.search(r"/result/(\d+)$", url)

    if not match:
        return None

    return int(match.group(1))


def _get_highest_result_id(data):
    """
    Finds the highest Grad Cafe result ID already
    stored in the applicant data
    """

    highest_result_id = 0

    for item in data:
        result_id = _get_result_id(item.get("url"))

        if result_id is not None and result_id > highest_result_id:
            highest_result_id = result_id

    return highest_result_id


def _initialize_chrome(url, port=chrome_port):
    """
    Launches an instance of Chrome so the user can complete
    Cloudflare's normal verification manually; the remote
    debugging port is specified so that Selenium can later
    attach to the browser, and unnecessary chrome background
    activity isn't started to speed up Selenium
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
    Initializes a Selenium instance and attaches to
    the currently running instance of Chrome through
    the debug port
    """

    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")

    options.page_load_strategy = "eager"

    return webdriver.Chrome(options=options)


def _scrape_survey_page(driver, url):
    """
    Scrapes the current surey page for prospective
    applicants to add to the database
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
    Fetches multiple result pages concurrently from inside
    the already Cloudflare-verified Chrome session; Chrome
    performs the requests using fetch(), which preserves
    the browser's cookies/session
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


def _scrape_result_page_html(html, url, date_added=None, gpa=None, start_term=None):
    """
    Parses a single applicant result page
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
            item["date_added"] = datetime.strptime(
                date_added,
                "%b %d, %Y"
            ).strftime("%m/%d/%Y")

        except ValueError:
            item["date_added"] = date_added

    if "Notes" in html and len(column_fields_html) > 10:
        item["comments"] = column_fields_html[10].get_text(
            " ",
            strip=True
        )

    return {
        key: (None if value == "Not provided" else value)
        for key, value in item.items()
    }


def _process_batch(driver, batch, existing_urls):
    """
    Fetches and parses one batch of result pages
    """

    urls = [item["url"] for item in batch]

    metadata = {
        item["url"]: item
        for item in batch
    }

    print(f"Fetching {len(urls)} result pages...")

    start_time = time.perf_counter()
    fetched = _fetch_pages_in_browser(driver, urls)

    records = []

    for result in fetched:
        result_url = result["url"]
        html = result["html"]

        if not html:
            print(
                f"FAILED: {result_url} "
                f"(HTTP {result.get('status')})"
            )
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
            print(
                f"PARSE ERROR: {result_url}: {e}"
            )
            continue

        records.append(item)
        existing_urls.add(result_url)

    elapsed = time.perf_counter() - start_time

    print(
        f"Added {len(records)} records "
        f"in {elapsed:.2f}s"
    )

    return records


def scrape_data(survey_url, authentication_event=None):
    """
    Loads previously scraped applicant data and then
    scrapes only records newer than the newest result
    already stored in the data file
    """

    data = _load_data()

    existing_urls = {
        item["url"]
        for item in data
        if item.get("url")
    }

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
                ) = _scrape_survey_page(
                    driver,
                    current_url
                )

            except Exception as e:
                print()
                print(
                    f"ERROR loading survey page "
                    f"{page_number}:"
                )
                print(e)
                save_data(data)
                print("Data checkpoint saved")
                print("Retrying in 5 seconds...")

                time.sleep(5)
                continue

            print(
                f"Found {len(result_urls)} result URLs"
            )
            print(
                f"Next page: {next_url or 'NONE'}"
            )

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

            print(
                f"New results: "
                f"{len(new_results)}"
            )

            for start in range(
                0,
                len(new_results),
                batch_size
            ):
                batch = new_results[
                    start : start + batch_size
                ]

                records = _process_batch(
                    driver,
                    batch,
                    existing_urls,
                )

                data = records + data
                new_records += len(records)

                print(
                    f"TOTAL: {len(data):,}"
                )

                save_data(data)

                print("Data checkpoint saved")

            if reached_existing_data:
                print()
                print(
                    "Reached existing data."
                )
                print(
                    "Scraping stopped safely."
                )
                break

            if not next_url:
                print()
                print(
                    f"WARNING: No Next link found "
                    f"on page {page_number}"
                )
                print(
                    "Scraping stopped safely"
                )
                save_data(data)

                break

            if next_url == current_url:
                print()
                print(
                    "WARNING: Next URL is the same "
                    "as the current URL"
                )
                print(
                    "Stopping to prevent an infinite loop"
                )
                save_data(data)

                break

            current_url = next_url
            page_number += 1

            print()
            print(
                f"Moving to page {page_number}"
            )

            time.sleep(0.2)

    finally:
        save_data(data)
        print()
        print(f"New records: {new_records:,}")
        print(f"Total records: {len(data):,}")

        driver.quit()

    return data


if __name__ == "__main__":
    scrape_data(survey_url)

    print()
    print("Done!")