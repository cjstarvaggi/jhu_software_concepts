import json
import os
import time

from llm_hosting.app import (
    _call_llm,
    CANON_PROGS,
    CANON_UNIS,
)


data_file_name = "llm_extend_applicant_data.json"


def load_data(input_path, limit=None):
    """
    Load records from a JSON file
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
    Normalizes for comparison (does not change the actual stored value
    """
    value = str(value or "")
    value = " ".join(value.split())
    return value.lower()


def _build_canonical_lookup(values):
    """
    Compares a read value to the canon list
    """
    lookup = {}

    for value in values:
        lookup[_comparison_key(value)] = value

    return lookup


def _get_canonical_program(value):
    """
    Pulls the actual canonical program
    """
    CANON_PROG_LOOKUP = _build_canonical_lookup(CANON_PROGS)
    return CANON_PROG_LOOKUP.get(_comparison_key(value))


def _get_canonical_university(value):
    """
    Pulls the actual canonical university
    """
    CANON_UNI_LOOKUP = _build_canonical_lookup(CANON_UNIS)
    return CANON_UNI_LOOKUP.get(_comparison_key(value))


def _is_already_cleaned(row):
    """
    Checks whether a record has already been cleaned
    """
    return (
        row.get("llm-generated-program") not in (None, "")
        and row.get("llm-generated-university") not in (None, "")
    )


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
    Checks to see if a program and university matches
    canon values; if so, there's no need to run the LLM
    on this entry
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
    Prints the results of the cleaning operation
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
    Cleans records sequentially using one LLM instance;
    the records remain in their original input order.
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
    Safely saves the cleaned applicant data by writing to a temporary
    file first so a crash during writing doesn't destroy the previous data
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