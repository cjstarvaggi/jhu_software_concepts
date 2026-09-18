# Mini LLM Standardizer — Flask (Replit-friendly)

Tiny Flask API that runs a small local LLM (TinyLlama 1.1B, GGUF) via `llama-cpp-python` to standardize
degree program + university names. It appends two new fields to each row:
- `llm-generated-program`
- `llm-generated-university`

## Quickstart (Replit)

1. Create a new **Python** Repl.
2. Upload these files (or import the zip).
3. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the API server:
   ```bash
   python app.py --serve
   ```
   The first run downloads a small GGUF model from Hugging Face (defaults to TinyLlama 1.1B Chat Q4_K_M).

5. Test locally (replace the URL with your Replit web URL when deployed):
   ```bash
   curl -s -X POST http://localhost:8000/standardize      -H "Content-Type: application/json"      -d @sample_data.json | jq .
   ```

## CLI mode (no server)

```bash
python app.py --file cleaned_applicant_data.json --stdout > full_out.jsonl
```

## Config (env vars)

- `MODEL_REPO` (default: `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF`)
- `MODEL_FILE` (default: `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`)
- `N_THREADS` (2)
- `N_CTX` (22048)
- `N_GPU_LAYERS` (-1 — GPU layers enabled)

If memory is tight on Replit, try:
```bash
export MODEL_FILE=tinyllama-1.1b-chat-v1.0.Q3_K_M.gguf
```

## Standardization changes

- Canonical matches are case/whitespace-insensitive and preserve the canonical spelling.
- Program and university fields are standardized independently.
- Common LLM spelling errors are corrected before fuzzy matching.
- Fuzzy matching uses stricter thresholds to avoid incorrect substitutions.
- Parenthetical text is removed before LLM processing.
- Values already found in the canonical lists are treated as verified and are not changed by the LLM.
- The LLM is instructed to preserve valid names and return Unknown only for clearly invalid values.
- If a field is not verified, only that field is allowed to be normalized.

## Notes
- Strict JSON prompting + post-processing keep the small model on task.
- The TinyLlama GGUF model runs locally through llama-cpp-python.
- The model uses a 2048-token context, 2 threads, and GPU layer offloading.
- The model is loaded once and reused after the first request.
- Extend the canonical lists and correction patterns in app.py for higher accuracy on your dataset.