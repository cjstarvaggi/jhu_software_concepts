import json

from llm_hosting.app import _call_llm


def load_data(input_path):
    """Load records from a JSON file"""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "rows" in data:
        data = data["rows"]

    if not isinstance(data, list):
        raise ValueError("Input data must be a list of records.")

    print(f"Loaded {len(data):,} records.")
    return data


def _call_llm(unique_pairs):
    """Calls the LLM on all the unique pairs"""
    total = len(unique_pairs)

    for i, (program_name, university) in enumerate(unique_pairs, start=1):
        result = _call_llm(program_name=program_name, university=university)
        unique_pairs[(program_name, university)] = result

        if i % 100 == 0 or i == total:
            print(f"LLM processed {i:,}/{total:,}")

    return unique_pairs


def _get_cleaned_data(unique_pairs):
    """Appends the LLM data to the applicant data in the desired fields"""
    cleaned_data = []
    for row in data:
        cleaned_row = dict(row)

        program_name = str(row.get("program_name") or "").strip()
        university = str(row.get("university") or "").strip()

        result = unique_pairs[(program_name, university)]

        cleaned_row["llm-generated-program"] = result[
            "standardized_program"
        ]

        cleaned_row["llm-generated-university"] = result[
            "standardized_university"
        ]

        cleaned_data.append(cleaned_row)

    return cleaned_data


def clean_data(data):
    """Clean each unique program/university pair using the LLM"""
    unique_pairs = {}

    for row in data:
        program_name = str(row.get("program_name") or "").strip()
        university = str(row.get("university") or "").strip()

        key = (program_name, university)

        if key not in unique_pairs:
            unique_pairs[key] = None

    print(f"Total records: {len(data):,}")
    print(f"Unique pairs: {len(unique_pairs):,}")
    print(f"LLM calls required: {len(unique_pairs):,}")

    unique_pairs = _call_llm(unique_pairs)
    cleaned_data = _get_cleaned_data(unique_pairs)

    return cleaned_data


def save_cleaned_data(data, output_path):
    """Save cleaned records to a JSON file"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(data):,} records to {output_path}")


if __name__ == "__main__":
    input_path = "applicant_data.json"
    output_path = "llm_extended_applicant_data.json"

    data = load_data(input_path)
    cleaned_data = clean_data(data)
    save_cleaned_data(cleaned_data, output_path)