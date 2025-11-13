import os
import json
import pandas as pd
from pydantic import BaseModel, Field
import logging
from datetime import datetime
from dotenv import load_dotenv
import time
import random
from google import genai
from schema import GrantData


## ---1. CONFIGURATION
# LOAD ENVIRONMENT VARIABLES
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("No GEMINI API KEY found in .env file!")


# directory setup
CONFIG_PATH = "config/sources_list.json"
DATA_DIR = "data"
RAW_OUTPUT_DIR = os.path.join(DATA_DIR, "raw_output.jsonl")
VALIDATED_CSV = os.path.join(DATA_DIR, "validated_grants.csv")
LOG_FILE = os.path.join(DATA_DIR, f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.log")


os.makedirs(DATA_DIR, exist_ok=True)


# configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
# Stream to console too
logging.getLogger().addHandler(logging.StreamHandler())

logging.info("=== GRANT EXTRACTION PIPELINE INITIALIZED ===")
logging.info(f"Log file: {LOG_FILE}")
logging.info(f"Config path: {CONFIG_PATH}")
logging.info(f"Data directory: {DATA_DIR}")


#load sources
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        SOURCES = json.load(f).get("sources", [])
        logging.info(f"Loaded {len(SOURCES)} sources from {CONFIG_PATH}")
except FileNotFoundError:
    logging.error(f"Sources file not found at {CONFIG_PATH}")
    SOURCES = []

if not SOURCES:
    logging.warning("No sources found. Exiting early may occur if nothing to process.")


# Initialize Gemini Client
client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-2.0-flash"       
TEMPERATURE = 0.3          
MAX_TOKENS = 4096  


def build_prompt(url: str) -> str:
    return f"""
You are a grant data extraction assistant for an AI-powered funding platform.

Go to the webpage: {url}

If the page lists **multiple grants or programs**, extract ALL of them as an array of JSON objects.
If it describes **a single grant**, return one JSON object.

Each grant must follow this structure exactly:
{{
  "grant_id": "",
  "title": "",
  "description": "",
  "funder": "",
  "funder_type": "",
  "funding_type": "",
  "amount_min": null,
  "amount_max": null,
  "currency": "",
  "deadline": "",
  "application_complexity": "",
  "eligible_provinces": [],
  "geography_details": "",
  "eligible_applicant_type": [],
  "eligible_industries": [],
  "target_beneficiaries": [],
  "supported_project_types": [],
  "sdg_alignment": [],
  "application_url": "",
  "is_recurring": false,
  "notes": ""
}}

Guidelines:
- When processing a portal page, extract **all grant programs listed**, not just the first.
- The 'description' must include full context, purpose, eligibility, and funding details — as detailed as possible.
- Use factual, well-structured text. Never invent information.
- Return *only valid JSON* — no markdown or text outside JSON.
"""



def extract_from_gemini(url, retries = 3, backoff = 2.0):
    """
    Handles the API call with retry/backoff.
    Returns parsed JSON text or None on failure.
    """
    prompt = build_prompt(url)
    for attempt in range(1, retries + 1):
        try:
            logging.info(f"Extracting from {url} (attempt {attempt}/{retries})")
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_TOKENS,
                    response_mime_type="application/json",
                ),
            )
            return response.text  # raw JSON string from Gemini
        except Exception as e:
            wait = backoff * (2 ** (attempt - 1)) + random.uniform(0, 1)
            logging.warning(f"Gemini request failed: {e}. Retrying in {wait:.1f}s...")
            time.sleep(wait)
    logging.error(f"All attempts failed for: {url}")
    return None


def parse_and_validate(raw_json: str, source_url: str):
    """
    Parse Gemini's JSON response and validate each record using GrantSchema.
    Returns (valid_records, invalid_records)
    """
    valid_records, invalid_records = [], []

    if not raw_json:
        logging.warning(f"No content returned for {source_url}")
        return valid_records, invalid_records

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error for {source_url}: {e}")
        return valid_records, invalid_records

    # Handle both single objects and arrays
    if isinstance(parsed, dict):
        parsed = [parsed]
    elif not isinstance(parsed, list):
        logging.warning(f"Unexpected JSON structure for {source_url}")
        return valid_records, invalid_records

    for item in parsed:
        item["source_url"] = source_url

        # Auto-generate grant_id if missing or empty
        if not item.get("grant_id"):
            funder_base = (item.get("funder") or "UNKNOWN").replace(" ", "_").upper()[:10]
            item["grant_id"] = f"{funder_base}_{int(time.time())}_{random.randint(100,999)}"

        try:
            validated = GrantData(**item)
            valid_records.append(validated.model_dump())
        except Exception as e:
            logging.warning(f"Validation failed for {source_url}: {e}")
            invalid_records.append({"source_url": source_url, "error": str(e)})

    return valid_records, invalid_records


def enrich_grant_text(description: str, notes: str):
    """
    Uses Gemini to generate a concise summary and list of keywords for faster AI matching.
    """
    try:
        prompt = f"""
        You will be given a grant description and notes.
        Create two short outputs:
        1. summary: 2–3 sentences summarizing the purpose, eligibility, and impact.
        2. keywords: a list of 5–10 relevant thematic keywords (lowercase).

        Return strictly as JSON with fields:
        {{
            "summary": "",
            "keywords": []
        }}

        Description:
        {description}

        Notes:
        {notes}
        """

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=512,
                response_mime_type="application/json"
            ),
        )

        enriched = json.loads(response.text)
        return enriched.get("summary", ""), enriched.get("keywords", [])
    except Exception as e:
        logging.warning(f"Keyword enrichment failed: {e}")
        return "", []



def save_to_csv(valid_records: list, invalid_records: list):
    """
    Appends validated grant data to validated_grants.csv
    and logs invalid ones separately if needed.
    """
    if not valid_records:
        logging.warning("No valid records to save.")
        return

    df = pd.DataFrame(valid_records)

    # Append to existing CSV if it exists, else create new
    write_header = not os.path.exists(VALIDATED_CSV)
    df.to_csv(VALIDATED_CSV, mode="a", header=write_header, index=False, encoding="utf-8")
    logging.info(f"Saved {len(valid_records)} validated records to {VALIDATED_CSV}")

    # Optionally, store invalids to a separate file
    if invalid_records:
        invalid_path = os.path.join(DATA_DIR, "invalid_records.csv")
        df_invalid = pd.DataFrame(invalid_records)
        append_invalid = os.path.exists(invalid_path)
        df_invalid.to_csv(invalid_path, mode="a", header=not append_invalid, index=False)
        logging.warning(f"{len(invalid_records)} invalid records logged in {invalid_path}")



def load_processed_urls():
    """
    Load URLs that have already been successfully processed to avoid duplication.
    """
    if not os.path.exists(VALIDATED_CSV):
        return set()

    try:
        df = pd.read_csv(VALIDATED_CSV, usecols=["source_url"])
        return set(df["source_url"].dropna().tolist())
    except Exception:
        return set()


def run_pipeline():
    """
    Full end-to-end process:
    1. Loop through URLs
    2. Extract via Gemini
    3. Parse + Validate
    4. Enrich (summary + keywords)
    5. Save valid + invalid data
    """
    all_valid, all_invalid = [], []
    total = len(SOURCES)
    processed = load_processed_urls()

    logging.info(f"Starting batch extraction for {total} sources.")
    logging.info(f"Skipping {len(processed)} URLs already processed.")

    for i, url in enumerate(SOURCES, start=1):
        if url in processed:
            logging.info(f"---- Skipping already processed: {url}")
            continue

        logging.info(f"\n---- [{i}/{total}] Processing {url} ----")

        # 1️⃣ Extract raw JSON from Gemini
        raw = extract_from_gemini(url)
        if not raw:
            all_invalid.append({"source_url": url, "error": "Gemini extraction failed"})
            continue

        # 2️⃣ Parse + validate
        valid, invalid = parse_and_validate(raw, url)

        # 3️⃣ Enrich each valid grant
        for grant in valid:
            summary, keywords = enrich_grant_text(grant["description"], grant["notes"])
            grant["summary"] = summary
            grant["keywords"] = keywords

        # 4️⃣ Aggregate results
        all_valid.extend(valid)
        all_invalid.extend(invalid)

        time.sleep(2)  # slight delay to avoid rate limit

    # 5️⃣ Save all results to CSVs
    save_to_csv(all_valid, all_invalid)

    logging.info("=== Extraction Complete ===")
    logging.info(f"Total URLs processed: {total}")
    logging.info(f"Valid grants: {len(all_valid)}")
    logging.info(f"Invalid grants: {len(all_invalid)}")
    logging.info(f"Output file: {VALIDATED_CSV}")



if __name__ == "__main__":
    run_pipeline()
