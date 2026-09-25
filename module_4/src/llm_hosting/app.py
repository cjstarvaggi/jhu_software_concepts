"""Flask + tiny local LLM standardizer with incremental JSONL CLI output."""

from __future__ import annotations

import json
import os
import re
import sys
import difflib

from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, request
from huggingface_hub import hf_hub_download
from llama_cpp import Llama  # CPU-only by default if N_GPU_LAYERS=0

app = Flask(__name__)

# ---------------- Model config ----------------
MODEL_REPO = os.getenv(
    "MODEL_REPO",
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
)
MODEL_FILE = os.getenv(
    "MODEL_FILE",
    "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
)

N_THREADS = 2  # int(os.getenv("N_THREADS", str(os.cpu_count() or 2)))
N_CTX = 2048  # int(os.getenv("N_CTX", "2048"))
N_GPU_LAYERS = -1  # int(os.getenv("N_GPU_LAYERS", "0"))  # 0 → CPU-only

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CANON_UNIS_PATH = os.getenv(
    "CANON_UNIS_PATH", os.path.join(BASE_DIR, "canon_universities.txt")
)
CANON_PROGS_PATH = os.getenv(
    "CANON_PROGS_PATH", os.path.join(BASE_DIR, "canon_programs.txt")
)

# Precompiled, non-greedy JSON object matcher to tolerate chatter around JSON
JSON_OBJ_RE = re.compile(r"\{.*?\}", re.DOTALL)


# ---------------- Canonical lists + abbrev maps ----------------
def _read_lines(path: str) -> List[str]:
    """Read non-empty, stripped lines from a UTF-8 text file.

    Each non-empty line is returned as a separate list element with leading
    and trailing whitespace removed. If the file does not exist, an empty
    list is returned.

    :param path: Path to the text file to read.
    :returns: A list containing the non-empty, stripped lines from the file.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        return []


CANON_UNIS = _read_lines(CANON_UNIS_PATH)
CANON_PROGS = _read_lines(CANON_PROGS_PATH)

ABBREV_UNI: Dict[str, str] = {
    r"(?i)^mcg(\.|ill)?$": "McGill University",
    r"(?i)^(ubc|u\.?b\.?c\.?)$": "University of British Columbia",
    r"(?i)^uoft$": "University of Toronto",
}

COMMON_UNI_FIXES: Dict[str, str] = {
    "McGiill University": "McGill University",
    "Mcgill University": "McGill University",
    # Normalize 'Of' → 'of'
    "University Of British Columbia": "University of British Columbia",
    # Observed LLM spelling/capitalization errors
    "Friedrich-Schiller Universität Jenna": "Friedrich-Schiller Universität Jena",
    "Feerdowsi University of Mashhad": "Ferdowsi University of Mashhad",
    "University of Dhaaka": "University of Dhaka",
    "Islamic Azad University, Farsi Science & Research Branch": "Islamic Azad University, Fars Science & Research Branch",
    "Feederal University of Technology, Minna": "Federal University of Technology, Minna",
    "LaDoke Akintola University of Technology": "Ladoke Akintola University of Technology",
    "Beijiing Normal University": "Beijing Normal University",
    "University of Guilañ": "University of Guilan",
    "University of South Floridaa": "University of South Florida",
    "AbduS Salam International Centre for Theoretical Physics": "Abdus Salam International Centre for Theoretical Physics",
}

COMMON_PROG_FIXES: Dict[str, str] = {
    "Mathematic": "Mathematics",
    "Info Studies": "Information Studies",
    # Observed LLM spelling errors
    "Strategiic Management": "Strategic Management",
    "AeroNautiics & Astronautics": "Aeronautics & Astronautics",
    "AeroNautiics & AstroNautics": "Aeronautics & Astronautics",
    "Diné Culture and Languaage Sustainability": "Diné Culture and Language Sustainability",
    "Mathematicas in Data Science": "Mathematics in Data Science",
    "Mathematic in Data Science": "Mathematics in Data Science",
    "EUROP EANFORSY": "EUROPEAN FORESTRY",
}

# ---------------- Few-shot prompt ----------------

SYSTEM_PROMPT = (
    "You are a conservative data-cleaning assistant. "
    "Your job is to standardize degree program and university names "
    "without inventing, guessing, or changing valid names.\n\n"
    "Rules:\n"
    "1. The input contains two independent fields:\n"
    "   - `program_name`\n"
    "   - `university`\n\n"
    "2. Clean each field independently. Never use the university to "
    "guess or modify the program, and never use the program to guess "
    "or modify the university.\n\n"
    "3. Preserve the original wording whenever it appears to be a "
    "valid name. Do NOT rewrite a proper noun merely because it looks "
    "unusual or unfamiliar.\n\n"
    "4. NEVER invent spelling changes. In particular, do not add, "
    "remove, duplicate, or substitute letters in proper names.\n"
    "   Examples:\n"
    "   - `Jena` must NOT become `Jenna`.\n"
    "   - `Ferdowsi` must NOT become `Feerdowsi`.\n"
    "   - `Dhaka` must NOT become `Dhaaka`.\n"
    "   - `Fars` must NOT become `Farsi`.\n"
    "   - `Federal` must NOT become `Feederal`.\n"
    "   - `Beijing` must NOT become `Beijiing`.\n"
    "   - `Language` must NOT become `Languaage`.\n"
    "   - `Aeronautics` must NOT become `AeroNautiics`.\n\n"
    "5. Do NOT substitute one institution for another. "
    "For example, `IIT Delhi` must NOT become `IIIT Delhi`.\n\n"
    "6. Do not invent words, remove meaningful words, or add words "
    "unless the change is an obvious formatting correction.\n\n"
    "7. Correct only clear formatting issues such as:\n"
    "   - extra whitespace\n"
    "   - inconsistent capitalization\n"
    "   - obvious capitalization of a proper name\n"
    "   - obvious abbreviation expansion when unambiguous\n\n"
    "8. Parenthetical text has already been removed from the input. "
    "Do not recreate it.\n\n"
    "9. A valid university or program does NOT have to appear in a "
    "provided canonical list. Do not reject a name just because it is "
    "not in the canonical list.\n\n"
    "10. If a value is clearly invalid, meaningless, or cannot be "
    "identified as a specific program or university, return `Unknown` "
    "for that field (such as 'All school' or 'Hogwartz').\n\n"
    "11. When uncertain between changing the input and preserving it, "
    "ALWAYS preserve the original input.\n\n"
    "12. Return JSON ONLY with exactly these keys:\n"
    "   `standardized_program`, `standardized_university`\n"
)


FEW_SHOTS: List[Tuple[Dict[str, str], Dict[str, str]]] = [
    (
        {
            "program_name": "Information Studies",
            "university": "McGill University",
        },
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {
            "program_name": "Information",
            "university": "McG",
        },
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {
            "program_name": "Mathematics",
            "university": "University Of British Columbia",
        },
        {
            "standardized_program": "Mathematics",
            "standardized_university": "University of British Columbia",
        },
    ),
]

_LLM = None


def _load_llm() -> Llama:
    """Load and cache the configured GGUF language model.

    The model is downloaded from Hugging Face into the local ``models``
    directory the first time this function is called. Subsequent calls
    return the already-initialized global model instance.

    :returns: The initialized :class:`llama_cpp.Llama` model.
    """
    global _LLM
    if _LLM is not None:
        return _LLM

    model_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILE,
        local_dir="models",
    )

    _LLM = Llama(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False,
    )
    return _LLM


def _best_match(
    name: str,
    candidates: List[str],
    cutoff: float = 0.86,
) -> str | None:
    """Find the closest candidate using :mod:`difflib` fuzzy matching.

    Only the single highest-ranked match is considered, and it must meet
    the supplied similarity cutoff.

    :param name: Value to compare against the candidate list.
    :param candidates: Candidate strings to search.
    :param cutoff: Minimum similarity ratio required for a match.
    :returns: The closest matching candidate, or ``None`` if no match
        satisfies the cutoff or either input is empty.
    """
    if not name or not candidates:
        return None
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _comparison_key(value: str) -> str:
    """Create a normalized key for case- and whitespace-insensitive comparison.

    Leading and trailing whitespace is removed, internal whitespace is
    collapsed, and the resulting value is converted to lowercase.

    :param value: Value to normalize for comparison.
    :returns: A lowercase comparison key with normalized whitespace.
    """
    value = str(value or "")
    value = " ".join(value.split())
    return value.lower()


def _canonical_match(
    value: str,
    canonical_values: List[str],
) -> str | None:
    """Find a case- and whitespace-insensitive canonical value.

    The comparison uses :func:`_comparison_key`, but the original canonical
    spelling is returned when a match is found.

    :param value: Value to search for in the canonical list.
    :param canonical_values: Canonical values against which to compare.
    :returns: The matching canonical value, or ``None`` if no match exists.
    """
    key = _comparison_key(value)

    if not key:
        return None

    for canonical in canonical_values:
        if _comparison_key(canonical) == key:
            return canonical

    return None


def _remove_parenthetical(value: str) -> str:
    """Remove parenthetical text from a program or university name.

    Parenthetical sections, including their surrounding whitespace, are
    removed. Remaining whitespace is collapsed and leading/trailing
    whitespace is stripped.

    :param value: Program or university name to clean.
    :returns: The name with parenthetical text removed and whitespace
        normalized.
    """
    value = str(value or "")
    value = re.sub(r"\s*\([^)]*\)", "", value)
    return " ".join(value.split()).strip()


def _post_normalize_program(prog: str) -> str:
    """Apply deterministic normalization to a program name.

    Known spelling fixes are applied first, followed by an exact canonical
    lookup, a normalized canonical lookup, and finally fuzzy matching.
    If no canonical or fuzzy match is found, the cleaned input is preserved.

    :param prog: Program name to normalize.
    :returns: The normalized or best-matching program name.
    """
    p = (prog or "").strip()
    p = COMMON_PROG_FIXES.get(p, p)
    if p in CANON_PROGS:
        return p

    canonical_match = _canonical_match(p, CANON_PROGS)
    if canonical_match != None:
        return canonical_match
    match = _best_match(p, CANON_PROGS, cutoff=0.90)
    return match or p


def _post_normalize_university(uni: str) -> str:
    """Apply deterministic normalization to a university name.

    Abbreviations and known spelling corrections are applied before exact,
    normalized canonical, and fuzzy matching. If no match is found, the
    cleaned input is preserved, with ``Unknown`` returned for an empty value.

    :param uni: University name to normalize.
    :returns: The normalized or best-matching university name.
    """
    u = (uni or "").strip()

    # Abbreviations
    for pat, full in ABBREV_UNI.items():
        if re.fullmatch(pat, u):
            u = full
            break

    # Common spelling fixes
    u = COMMON_UNI_FIXES.get(u, u)

    # Canonical or fuzzy map
    if u in CANON_UNIS:
        return u

    canonical_match = _canonical_match(u, CANON_UNIS)
    if canonical_match != None:
        return canonical_match

    match = _best_match(u, CANON_UNIS, cutoff=0.92)
    return match or u or "Unknown"


def _call_llm(
    program_name: str,
    university: str,
    normalize_program: bool = True,
    normalize_university: bool = True,
) -> Dict[str, str]:
    """Standardize a program and university using the local LLM.

    Parenthetical text is removed before constructing the prompt. Each field
    can independently be marked as eligible or ineligible for normalization.
    The LLM response is parsed as JSON, with a fallback to the original input
    when parsing fails. Eligible values are then passed through deterministic
    post-normalization.

    :param program_name: Original program name.
    :param university: Original university name.
    :param normalize_program: Whether the program may be changed by the
        standardization process.
    :param normalize_university: Whether the university may be changed by the
        standardization process.
    :returns: A dictionary containing ``standardized_program`` and
        ``standardized_university``.
    """
    program_name = _remove_parenthetical(program_name)
    university = _remove_parenthetical(university)

    llm = _load_llm()

    program_status = (
        "MAY BE STANDARDIZED" if normalize_program else "VERIFIED - DO NOT CHANGE"
    )
    university_status = (
        "MAY BE STANDARDIZED" if normalize_university else "VERIFIED - DO NOT CHANGE"
    )

    system_prompt = SYSTEM_PROMPT + (
        f"\n\nCurrent field permissions:\n"
        f"- program_name: {program_status}\n"
        f"- university: {university_status}\n"
    )

    messages = [{"role": "system", "content": system_prompt}]

    for x_in, x_out in FEW_SHOTS:
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    x_in,
                    ensure_ascii=False,
                ),
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    x_out,
                    ensure_ascii=False,
                ),
            }
        )

    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {
                    "program_name": program_name,
                    "university": university,
                    "program_permission": program_status,
                    "university_permission": university_status,
                },
                ensure_ascii=False,
            ),
        }
    )

    out = llm.create_chat_completion(
        messages=messages,
        temperature=0.0,
        max_tokens=128,
        top_p=1.0,
    )

    text = (out["choices"][0]["message"]["content"] or "").strip()

    try:
        match = JSON_OBJ_RE.search(text)

        obj = json.loads(match.group(0) if match else text)
        std_prog = str(obj.get("standardized_program", "")).strip()
        std_uni = str(obj.get("standardized_university", "")).strip()

    except Exception:
        std_prog = program_name.strip() if program_name else "Unknown"
        std_uni = university.strip() if university else "Unknown"

    if not normalize_program:
        std_prog = program_name.strip() if program_name else "Unknown"
    else:
        std_prog = _post_normalize_program(std_prog)

    if not normalize_university:
        std_uni = university.strip() if university else "Unknown"
    else:
        std_uni = _post_normalize_university(std_uni)

    return {
        "standardized_program": std_prog,
        "standardized_university": std_uni,
    }


def _normalize_input(payload: Any) -> List[Dict[str, Any]]:
    """Normalize supported request payload shapes into a row list.

    A payload may either be a list of row dictionaries or a dictionary
    containing a list under the ``rows`` key. Any other payload shape
    produces an empty list.

    :param payload: Parsed JSON payload to normalize.
    :returns: A list of input rows, or an empty list for unsupported input.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return []


@app.get("/")
def health() -> Any:
    """Return a simple health-check response.

    :returns: A JSON response containing ``{"ok": True}``.
    """
    return jsonify({"ok": True})


@app.post("/standardize")
def standardize() -> Any:
    """Standardize applicant rows submitted through the HTTP API.

    The request JSON may contain either a list of rows or a dictionary with
    a ``rows`` list. Each row's program and university are checked against
    the canonical lists before being passed to the LLM. The standardized
    values are added to the row as ``llm-generated-program`` and
    ``llm-generated-university``.

    :returns: A JSON response containing the processed rows under ``rows``.
    """
    payload = request.get_json(force=True, silent=True)
    rows = _normalize_input(payload)

    out: List[Dict[str, Any]] = []
    for row in rows:
        program_name = (row or {}).get("program_name") or ""
        university = (row or {}).get("university") or ""

        canonical_program = _canonical_match(program_name, CANON_PROGS)
        canonical_university = _canonical_match(university, CANON_UNIS)

        result = _call_llm(
            program_name=program_name,
            university=university,
            normalize_program=canonical_program is None,
            normalize_university=canonical_university is None,
        )

        row["llm-generated-program"] = result["standardized_program"]
        row["llm-generated-university"] = result["standardized_university"]
        out.append(row)

    return jsonify({"rows": out})


def _cli_process_file(
    in_path: str,
    out_path: str | None,
    append: bool,
    to_stdout: bool,
) -> None:
    """Process a JSON input file and incrementally write JSON Lines output.

    Input may contain either a list of rows or a dictionary containing a
    ``rows`` list. Each row is standardized independently and written as a
    JSON object followed by a newline. Output is flushed after each row so
    that processing results are available incrementally.

    When ``to_stdout`` is false, output is written to ``out_path`` or, when
    no output path is supplied, to ``<input>.jsonl``. Existing output is
    either overwritten or appended to according to ``append``.

    :param in_path: Path to the JSON input file.
    :param out_path: Destination path for JSONL output, or ``None`` to use
        the input path with ``.jsonl`` appended.
    :param append: Whether to append to an existing output file.
    :param to_stdout: Whether to write JSONL output to standard output.
    """
    with open(in_path, "r", encoding="utf-8") as f:
        rows = _normalize_input(json.load(f))

    sink = sys.stdout if to_stdout else None
    if not to_stdout:
        out_path = out_path or (in_path + ".jsonl")
        mode = "a" if append else "w"
        sink = open(out_path, mode, encoding="utf-8")

    assert sink is not None  # for type-checkers

    try:
        for row in rows:
            program_name = (row or {}).get("program_name") or ""
            university = (row or {}).get("university") or ""

            canonical_program = _canonical_match(program_name, CANON_PROGS)
            canonical_university = _canonical_match(university, CANON_UNIS)

            result = _call_llm(
                program_name=program_name,
                university=university,
                normalize_program=canonical_program is None,
                normalize_university=canonical_university is None,
            )

            row["llm-generated-program"] = result["standardized_program"]
            row["llm-generated-university"] = result["standardized_university"]

            json.dump(row, sink, ensure_ascii=False)
            sink.write("\n")
            sink.flush()
    finally:
        if sink is not sys.stdout:
            sink.close()


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="Standardize program/university with a tiny local LLM.",
    )
    parser.add_argument(
        "--file",
        help="Path to JSON input (list of rows or {'rows': [...]})",
        default=None,
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the HTTP server instead of CLI.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for JSON Lines (ndjson). "
        "Defaults to <input>.jsonl when --file is set.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the output file instead of overwriting.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write JSON Lines to stdout instead of a file.",
    )
    args = parser.parse_args()

    if args.serve or args.file is None:
        port = int(os.getenv("PORT", "8000"))
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        _cli_process_file(
            in_path=args.file,
            out_path=args.out,
            append=bool(args.append),
            to_stdout=bool(args.stdout),
        )