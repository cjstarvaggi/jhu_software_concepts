import json
import os
import time

from llm_hosting.app import (
    _call_llm,
    CANON_PROGS,
    CANON_UNIS,
)

data_file_name = r"src\llm_extend_applicant_data.json"


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

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "rows" in data:
        data = data["rows"]

    if not isinstance(data, list):
        raise ValueError("Input data must be a list of records.")

    if limit is not None:
        data = data[:limit]

    print(f"Loaded {len(data):,} records.")
    return data


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

    value = str(value or "")
    value = " ".join(value.split())
    return value.lower()


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

    CANON_PROG_LOOKUP = _build_canonical_lookup(CANON_PROGS)
    return CANON_PROG_LOOKUP.get(_comparison_key(value))


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

    CANON_UNI_LOOKUP = _build_canonical_lookup(CANON_UNIS)
    return CANON_UNI_LOOKUP.get(_comparison_key(value))


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


def _canon_check(
    program_is_canonical,
    university_is_canonical,
    canonical_program,
    canonical_university,
    program_name,
    university,
    llm_calls,
    skipped_llm,
    program_matches,
    university_matches,
    both_matches,
):
    """
    Resolve canonical program and university values, using the LLM only
    for fields that do not already have canonical matches.

    When both fields match canonical values, no LLM call is made. When only
    one field matches, the canonical field is preserved while the LLM is
    asked to standardize only the other field.

    :param program_is_canonical: Whether the program already matches a
        canonical value.
    :type program_is_canonical: bool
    :param university_is_canonical: Whether the university already matches
        a canonical value.
    :type university_is_canonical: bool
    :param canonical_program: Canonical program value, if matched.
    :type canonical_program: str or None
    :param canonical_university: Canonical university value, if matched.
    :type canonical_university: str or None
    :param program_name: Original program name.
    :type program_name: str
    :param university: Original university name.
    :type university: str
    :param llm_calls: Current count of LLM calls.
    :type llm_calls: int
    :param skipped_llm: Current count of records for which the LLM was
        skipped.
    :type skipped_llm: int
    :param program_matches: Current count of canonical program matches.
    :type program_matches: int
    :param university_matches: Current count of canonical university
        matches.
    :type university_matches: int
    :param both_matches: Current count of records where both fields matched
        canonical values.
    :type both_matches: int
    :returns: Standardized program and university values followed by the
        updated processing counters.
    :rtype: tuple
    """

    if program_is_canonical and university_is_canonical:
        standardized_program = canonical_program
        standardized_university = canonical_university

        llm_calls += 0
        skipped_llm += 1
        program_matches += 1
        university_matches += 1
        both_matches += 1

    else:
        result = _call_llm(
            program_name=program_name,
            university=university,
            normalize_program=not program_is_canonical,
            normalize_university=not university_is_canonical,
        )

        if program_is_canonical:
            standardized_program = canonical_program
            program_matches += 1
        else:
            standardized_program = result["standardized_program"]

        if university_is_canonical:
            standardized_university = canonical_university
            university_matches += 1
        else:
            standardized_university = result["standardized_university"]

        llm_calls += 1

    return (
        standardized_program,
        standardized_university,
        llm_calls,
        skipped_llm,
        program_matches,
        university_matches,
        both_matches,
    )


def _final_cleaning_stats(
    start_time,
    total,
    program_matches,
    university_matches,
    both_matches,
    llm_calls,
    skipped_llm,
    already_cleaned,
):
    """
    Print summary statistics for a completed cleaning operation.

    The summary includes canonical match counts, LLM usage, the number of
    previously cleaned records, elapsed time, and average processing rate.

    :param start_time: Timestamp captured when cleaning began.
    :type start_time: float
    :param total: Total number of records processed.
    :type total: int
    :param program_matches: Number of records with canonical program
        matches.
    :type program_matches: int
    :param university_matches: Number of records with canonical university
        matches.
    :type university_matches: int
    :param both_matches: Number of records where both fields matched
        canonical values.
    :type both_matches: int
    :param llm_calls: Number of LLM calls performed.
    :type llm_calls: int
    :param skipped_llm: Number of records for which the LLM was skipped.
    :type skipped_llm: int
    :param already_cleaned: Number of records that already contained
        standardized program and university values.
    :type already_cleaned: int
    """

    print()
    print()

    elapsed = time.time() - start_time
    rate = total / elapsed if total > 0 else 0

    print("Cleaning summary")
    print("----------------")
    print(f"Total records:                {total:,}")
    print(f"Program canonical matches:    {program_matches:,}")
    print(f"University canonical matches: {university_matches:,}")
    print(f"Both canonical:                {both_matches:,}")
    print(f"LLM calls:                     {llm_calls:,}")
    print(f"Skipped LLM calls:             {skipped_llm:,}")
    print(f"Already cleaned:               {already_cleaned:,}")
    print(f"Elapsed time:                  {elapsed:.1f}s")
    print(f"Average rate:                  {rate:.2f} records/sec")


def clean_data(data):
    """
    Clean applicant records sequentially while preserving input order.

    Records that already contain standardized program and university
    values are retained without further processing. For other records,
    canonical program and university lookups are performed first, and
    the LLM is called only for fields that do not have canonical matches.

    Processing progress and LLM usage statistics are printed while the
    records are being cleaned. A final summary is printed after all
    records have been processed.

    :param data: Applicant records to clean.
    :type data: list
    :returns: Cleaned applicant records in their original input order.
    :rtype: list
    """

    total = len(data)

    if total == 0:
        return []

    print("Starting cleaning process...")
    print()

    start_time = time.time()

    llm_calls = 0
    skipped_llm = 0
    program_matches = 0
    university_matches = 0
    both_matches = 0
    already_cleaned = 0

    cleaned_data = []

    for index, row in enumerate(data):
        if _is_already_cleaned(row):
            cleaned_data.append(row)
            already_cleaned += 1

            completed = index + 1

            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            remaining = total - completed

            print(
                f"\rProcessed {completed:,}/{total:,} "
                f"({completed / total:.1%}) | "
                f"LLM: {llm_calls:,} | "
                f"Skipped: {skipped_llm:,} | "
                f"Rate: {rate:.2f} rec/s | "
                f"Remaining: {remaining:,}",
                end="",
                flush=True,
            )

            continue

        program_name = row.get("program_name") or ""
        university = row.get("university") or ""

        canonical_program = _get_canonical_program(program_name)
        canonical_university = _get_canonical_university(university)

        program_is_canonical = canonical_program is not None
        university_is_canonical = canonical_university is not None

        [
            standardized_program,
            standardized_university,
            llm_calls,
            skipped_llm,
            program_matches,
            university_matches,
            both_matches,
        ] = _canon_check(
            program_is_canonical,
            university_is_canonical,
            canonical_program,
            canonical_university,
            program_name,
            university,
            llm_calls,
            skipped_llm,
            program_matches,
            university_matches,
            both_matches,
        )

        cleaned_row = dict(row)

        cleaned_row["llm-generated-program"] = standardized_program
        cleaned_row["llm-generated-university"] = standardized_university

        cleaned_data.append(cleaned_row)

        completed = index + 1

        elapsed = time.time() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        remaining = total - completed

        print(
            f"\rProcessed {completed:,}/{total:,} "
            f"({completed / total:.1%}) | "
            f"LLM: {llm_calls:,} | "
            f"Skipped: {skipped_llm:,} | "
            f"Rate: {rate:.2f} rec/s | "
            f"Remaining: {remaining:,}",
            end="",
            flush=True,
        )

    _final_cleaning_stats(
        start_time,
        total,
        program_matches,
        university_matches,
        both_matches,
        llm_calls,
        skipped_llm,
        already_cleaned,
    )

    return cleaned_data


def save_cleaned_data(data, output_path):
    """
    Safely save cleaned applicant data to a JSON file.

    The records are first written to a temporary file and then moved into
    place with ``os.replace``. This reduces the risk of losing the previous
    output file if the process fails while writing the new data.

    :param data: Cleaned applicant records to save.
    :type data: list
    :param output_path: Destination path for the cleaned JSON data.
    :type output_path: str
    """

    temp_file = output_path + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.replace(temp_file, output_path)

    print(f"Saved {len(data):,} records to {output_path}")


if __name__ == "__main__":
    input_path = data_file_name
    output_path = data_file_name

    data = load_data(input_path)
    cleaned_data = clean_data(data)
    save_cleaned_data(cleaned_data, output_path)
