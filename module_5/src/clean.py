"""Clean and standardize applicant program and university data."""

import json
import os
import time
from dataclasses import dataclass

from llm_hosting.app import (
    _call_llm,
    CANON_PROGS,
    CANON_UNIS,
)

data_file_name = os.path.join("src", "llm_extend_applicant_data.json")


@dataclass
class CleaningStats:
    """
    Track statistics collected during the cleaning process.

    :ivar llm_calls: Number of LLM calls made during cleaning.
    :ivar skipped_llm: Number of records for which the LLM call was skipped.
    :ivar program_matches: Number of records with matched program names.
    :ivar university_matches: Number of records with matched university names.
    :ivar both_matches: Number of records with both program and university matches.
    :ivar already_cleaned: Number of records that were already cleaned.
    """

    llm_calls: int = 0
    skipped_llm: int = 0
    program_matches: int = 0
    university_matches: int = 0
    both_matches: int = 0
    already_cleaned: int = 0


def load_data(input_path, limit=None):
    """
    Load applicant records from a JSON file.

    The input may either be a list of records or a dictionary containing
    the records under a ``"rows"`` key. An optional limit can restrict
    processing to the first specified number of records.

    :param input_path: Path to the JSON input file.
    :type input_path: str
    :param limit: Maximum number of records to load, or ``None`` to load
        all records.
    :type limit: int or None
    :returns: Loaded applicant records.
    :rtype: list
    :raises ValueError: If the loaded JSON value is neither a list nor a
        dictionary containing a ``"rows"`` list.
    """

    with open(input_path, "r", encoding="utf-8") as file_handle:
        loaded_data = json.load(file_handle)

    if isinstance(loaded_data, dict) and "rows" in loaded_data:
        loaded_data = loaded_data["rows"]

    if not isinstance(loaded_data, list):
        raise ValueError("Input data must be a list of records.")

    if limit is not None:
        loaded_data = loaded_data[:limit]

    print(f"Loaded {len(loaded_data):,} records.")
    return loaded_data


def _comparison_key(value):
    """
    Normalize a value for canonical comparison without changing the
    original stored value.

    Whitespace is collapsed and the resulting value is converted to
    lowercase so comparisons are insensitive to capitalization and
    repeated whitespace.

    :param value: Value to normalize for comparison.
    :type value: object
    :returns: Normalized comparison key.
    :rtype: str
    """

    normalized_value = str(value or "")
    normalized_value = " ".join(normalized_value.split())

    return normalized_value.lower()


def _build_canonical_lookup(values):
    """
    Build a normalized lookup dictionary for canonical values.

    Each canonical value is indexed by its normalized comparison key while
    the original canonical spelling is retained as the dictionary value.

    :param values: Canonical values to index.
    :type values: iterable
    :returns: Mapping from normalized comparison keys to their original
        canonical values.
    :rtype: dict
    """

    lookup = {}

    for value in values:
        lookup[_comparison_key(value)] = value

    return lookup


def _get_canonical_program(value):
    """
    Find the canonical program corresponding to an input value.

    The comparison is case-insensitive and ignores differences in repeated
    or surrounding whitespace.

    :param value: Program name to compare against the canonical program list.
    :type value: object
    :returns: The canonical program name, or ``None`` if no match exists.
    :rtype: str or None
    """

    canonical_program_lookup = _build_canonical_lookup(CANON_PROGS)

    return canonical_program_lookup.get(_comparison_key(value))


def _get_canonical_university(value):
    """
    Find the canonical university corresponding to an input value.

    The comparison is case-insensitive and ignores differences in repeated
    or surrounding whitespace.

    :param value: University name to compare against the canonical
        university list.
    :type value: object
    :returns: The canonical university name, or ``None`` if no match exists.
    :rtype: str or None
    """

    canonical_university_lookup = _build_canonical_lookup(CANON_UNIS)

    return canonical_university_lookup.get(_comparison_key(value))


def _is_already_cleaned(row):
    """
    Determine whether a record already contains both LLM-generated
    standardized fields.

    A record is considered already cleaned only when both
    ``llm-generated-program`` and ``llm-generated-university`` contain
    non-empty values.

    :param row: Applicant record to inspect.
    :type row: dict
    :returns: ``True`` when both standardized fields are populated;
        otherwise ``False``.
    :rtype: bool
    """

    return row.get("llm-generated-program") not in (None, "") and row.get(
        "llm-generated-university"
    ) not in (None, "")


def _standardize_record(row, stats):
    """
    Standardize the program and university fields for one record.

    Canonical values are used directly whenever available. The LLM is
    called only for fields that do not already match a canonical value.

    :param row: Applicant record to standardize.
    :type row: dict
    :param stats: Mutable cleaning statistics.
    :type stats: CleaningStats
    :returns: A cleaned copy of the applicant record.
    :rtype: dict
    """

    program_name = row.get("program_name") or ""
    university = row.get("university") or ""

    canonical_program = _get_canonical_program(program_name)
    canonical_university = _get_canonical_university(university)

    program_is_canonical = canonical_program is not None
    university_is_canonical = canonical_university is not None

    if program_is_canonical and university_is_canonical:
        standardized_program = canonical_program
        standardized_university = canonical_university

        stats.skipped_llm += 1
        stats.program_matches += 1
        stats.university_matches += 1
        stats.both_matches += 1
    else:
        result = _call_llm(
            program_name=program_name,
            university=university,
            normalize_program=not program_is_canonical,
            normalize_university=not university_is_canonical,
        )

        if program_is_canonical:
            standardized_program = canonical_program
            stats.program_matches += 1
        else:
            standardized_program = result["standardized_program"]

        if university_is_canonical:
            standardized_university = canonical_university
            stats.university_matches += 1
        else:
            standardized_university = result["standardized_university"]

        stats.llm_calls += 1

    cleaned_row = dict(row)

    cleaned_row["llm-generated-program"] = standardized_program
    cleaned_row["llm-generated-university"] = standardized_university

    return cleaned_row


def _print_progress(completed, total, start_time, stats):
    """
    Print the current cleaning progress on a single terminal line.

    :param completed: Number of records processed so far.
    :type completed: int
    :param total: Total number of records.
    :type total: int
    :param start_time: Timestamp captured when cleaning began.
    :type start_time: float
    :param stats: Current cleaning statistics.
    :type stats: CleaningStats
    """

    elapsed = time.time() - start_time
    rate = completed / elapsed if elapsed > 0 else 0
    remaining = total - completed

    print(
        f"\rProcessed {completed:,}/{total:,} "
        f"({completed / total:.1%}) | "
        f"LLM: {stats.llm_calls:,} | "
        f"Skipped: {stats.skipped_llm:,} | "
        f"Rate: {rate:.2f} rec/s | "
        f"Remaining: {remaining:,}",
        end="",
        flush=True,
    )


def _final_cleaning_stats(start_time, total, stats):
    """
    Print summary statistics for a completed cleaning operation.

    The summary includes canonical match counts, LLM usage, the number of
    previously cleaned records, elapsed time, and average processing rate.

    :param start_time: Timestamp captured when cleaning began.
    :type start_time: float
    :param total: Total number of records processed.
    :type total: int
    :param stats: Final cleaning statistics.
    :type stats: CleaningStats
    """

    print()
    print()

    elapsed = time.time() - start_time
    rate = total / elapsed if total > 0 else 0

    print("Cleaning summary")
    print("----------------")
    print(f"Total records:                {total:,}")
    print(f"Program canonical matches:    {stats.program_matches:,}")
    print(f"University canonical matches: {stats.university_matches:,}")
    print(f"Both canonical:                {stats.both_matches:,}")
    print(f"LLM calls:                     {stats.llm_calls:,}")
    print(f"Skipped LLM calls:             {stats.skipped_llm:,}")
    print(f"Already cleaned:               {stats.already_cleaned:,}")
    print(f"Elapsed time:                  {elapsed:.1f}s")
    print(f"Average rate:                  {rate:.2f} records/sec")


def clean_data(records):
    """
    Clean applicant records sequentially while preserving input order.

    Records that already contain standardized program and university
    values are retained without further processing. For other records,
    canonical program and university lookups are performed first, and
    the LLM is called only for fields that do not have canonical matches.

    Processing progress and LLM usage statistics are printed while the
    records are being cleaned. A final summary is printed after all
    records have been processed.

    :param records: Applicant records to clean.
    :type records: list
    :returns: Cleaned applicant records in their original input order.
    :rtype: list
    """

    total = len(records)

    if total == 0:
        return []

    print("Starting cleaning process...")
    print()

    start_time = time.time()
    stats = CleaningStats()
    cleaned_records = []

    for index, row in enumerate(records):
        if _is_already_cleaned(row):
            cleaned_records.append(row)
            stats.already_cleaned += 1
        else:
            cleaned_records.append(_standardize_record(row, stats))

        completed = index + 1
        _print_progress(completed, total, start_time, stats)

    _final_cleaning_stats(start_time, total, stats)

    return cleaned_records


def save_cleaned_data(records, destination_path):
    """
    Safely save cleaned applicant data to a JSON file.

    The records are first written to a temporary file and then moved into
    place with ``os.replace``. This reduces the risk of losing the previous
    output file if the process fails while writing the new data.

    :param records: Cleaned applicant records to save.
    :type records: list
    :param destination_path: Destination path for the cleaned JSON data.
    :type destination_path: str
    """

    temp_file = destination_path + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file_handle:
        json.dump(records, file_handle, ensure_ascii=False, indent=2)

    os.replace(temp_file, destination_path)

    print(f"Saved {len(records):,} records to {destination_path}")


def main():
    """
    Load, clean, and save applicant data.

    :returns: None
    :rtype: None
    """

    source_path = data_file_name
    destination_path = data_file_name

    applicant_records = load_data(source_path)
    cleaned_records = clean_data(applicant_records)
    save_cleaned_data(cleaned_records, destination_path)


if __name__ == "__main__":
    main()
