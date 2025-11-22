import os
import json
import pandas as pd
from pydantic import BaseModel, Field
import logging
from typing import Optional
from datetime import datetime, UTC
from dotenv import load_dotenv
import time
import random
from google import genai
from schema import GrantData # Import the updated Pydantic model
from typing import Optional, List, Dict, Any # Added missing import

## ---1. CONFIGURATION
# LOAD ENVIRONMENT VARIABLES
load_dotenv()

# The API key is now correctly loaded from the environment by the user's setup.
API_KEY = os.getenv("GEMINI_API_KEY") 
if not API_KEY:
    logging.error("No GEMINI API KEY found in .env file! Ensure it is set for successful execution.")


# directory setup
CONFIG_PATH = "config/sources_list.json"
DATA_DIR = "data/processed"
LOG = 'data/log'
RAW_OUTPUT_DIR = os.path.join(DATA_DIR, "raw_output.jsonl")

# Using UTC time for robust timestamping (addresses DeprecationWarning)
now_utc = datetime.now(UTC).strftime('%Y-%m-%d_%H-%M-%S')
VALIDATED_CSV = os.path.join(DATA_DIR, f"validated_grants_{now_utc}.csv")
LOG_FILE = os.path.join(LOG, f"pipeline-run_{now_utc}.log")


os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG, exist_ok=True)


# configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
# Stream to console too
logging.getLogger().addHandler(logging.StreamHandler())

logging.info("=== GRANT EXTRACTION PIPELINE INITIALIZED ===")


#load sources
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        SOURCES = json.load(f).get("sources", [])
        logging.info(f"Loaded {len(SOURCES)} sources from {CONFIG_PATH}")
except FileNotFoundError:
    logging.error(f"Sources file not found at {CONFIG_PATH}. Please ensure '{CONFIG_PATH}' exists.")
    SOURCES = []

if not SOURCES:
    logging.warning("No sources found. Exiting early may occur if nothing to process.")


# Initialize Gemini Client
client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-2.5-flash" 
TEMPERATURE = 0.3              
MAX_TOKENS = 4096 


def build_prompt(url: str) -> str:
    # We explicitly embed the expected JSON structure in the prompt now.
    schema_definition = """
[
    {
        "grant_id": "Unique identifier for the grant (e.g., GOV_AB_2025_001).",
        "title": "The full, official title of the grant program.",
        "description": "Crucial: The full, detailed description including purpose, eligibility, and funding details.",
        "funder": "The name of the organization offering the grant.",
        "funder_type": "The type of funder (e.g., 'Federal Grant', 'Foundation Grant').",
        "funding_type": "Nature of the funding (e.g., 'Grant', 'Loan').",
        "amount_min": 100000,
        "amount_max": 5000000,
        "currency": "The three-letter currency code (e.g., 'CAD', 'USD').",
        "deadline": "The application deadline, formatted as 'YYYY-MM-DD' or 'Ongoing'.",
        "application_complexity": "Estimated complexity (e.g., 'Low', 'Medium', 'High').",
        "eligible_provinces": ["List of eligible regions/states. Use ['National'] if nationwide."],
        "geography_details": "Any specific local or regional restrictions.",
        "eligible_applicant_type": ["List of organization types (e.g., 'Small Business', 'Non-profit')."],
        "eligible_industries": ["List of specific industries or sectors."],
        "target_beneficiaries": ["List of groups supported (e.g., 'Youth', 'Women-owned businesses')."],
        "supported_project_types": ["List of projects funded (e.g., 'R&D', 'Equipment Purchase')."],
        "sdg_alignment": ["List of UN SDGs the grant aligns with."],
        "application_url": "Direct URL to the primary application page or program details.",
        "is_recurring": true,
        "notes": "Any essential caveats or additional information.",
        "application_questions_link": "Direct URL to the FAQ/contact page (or null).",
        "application_package_link": "Direct URL to downloadable application forms (or null)."
    }
]
    """
    
    return f"""
    You are an expert grant data extraction assistant.

    **Action:** Visit the webpage at: {url}
    **Task:** Extract ALL grant programs listed on the page.

    **Formatting Rules:**
    1.  Return **ONLY THE VALID JSON ARRAY/OBJECT** — do not include any markdown, commentary, or text outside the JSON structure.
    2.  The JSON structure MUST strictly adhere to the following schema definition. Use **EXACTLY** these field names:

    SCHEMA REFERENCE (Use exactly these field names, filling required data):
    {schema_definition}

    **Content Rules:**
    -   If the page lists multiple grants, return an array of JSON objects.
    -   The 'description' must be highly detailed, including full context, purpose, eligibility, and funding details.
    
    ***
    **MONEY VALUE RULE:**
    For the fields `amount_min` and `amount_max`:
    1.  You **MUST** report the monetary amount in the **major currency unit** (e.g., Dollars, Euros).
    2.  The final value in the JSON MUST be a pure integer (no decimals). If the source includes cents, round down to the nearest whole unit.
    3.  **Example:** If the grant amount is $10,000.00, `amount_max` should be 10000.
    ***
    
    -   For list fields (e.g., eligible_provinces), always return a JSON array ([]), even if empty or only containing one item.
    """


def extract_from_gemini(url: str, retries: int = 3, backoff: float = 2.0) -> Optional[str]:
    """
    Handles the API call with retry/backoff, and CRITICALLY, enables Google Search Grounding.
    The response_mime_type and response_schema are REMOVED to avoid the 400 error.
    Returns raw JSON text or None on failure.
    """
    prompt = build_prompt(url)
    
    # We no longer pass the schema in config, but rely on the prompt text instruction
    # to guide the model's output structure.
    
    for attempt in range(1, retries + 1):
        try:
            logging.info(f"Extracting from {url} (attempt {attempt}/{retries})")
            
            # The prompt now contains the full schema definition
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_TOKENS,
                    # This tool enables web access (Grounding)
                    tools=[{"google_search": {}}], 
                ),
            )
            
            # Since we removed the JSON mime type, the model might wrap the JSON in ```json...```
            # We must strip any markdown formatting before returning the raw JSON string.
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text.strip("```json").strip("```").strip()
            
            # CRITICAL FIX: Clean up illegal control characters/non-standard whitespace
            # This fixes "Invalid control character" errors caused by LLM-generated whitespace
            # like non-breaking spaces (\u00a0).
            raw_text = raw_text.replace('\u00a0', ' ')
            raw_text = raw_text.replace('\u200b', '') # Zero-width space
            
            return raw_text
        
        except Exception as e:
            wait = backoff * (2 ** (attempt - 1)) + random.uniform(0, 1)
            logging.warning(f"Gemini request failed: {e}. Retrying in {wait:.1f}s...")
            time.sleep(wait)
            
    logging.error(f"All attempts failed for: {url}")
    return None


def parse_and_validate(raw_json: str, source_url: str) -> tuple[list, list]:
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
        # Increased error logging to help debug malformed JSON from the LLM
        logging.error(f"JSON parsing error for {source_url}: {e} (Raw: {raw_json[:500]}...)")
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
            # Pydantic validation
            validated = GrantData(**item)
            valid_records.append(validated.model_dump())
        except Exception as e:
            logging.warning(f"Validation failed for {source_url} (ID: {item.get('grant_id', 'N/A')}): {e}")
            invalid_records.append({"source_url": source_url, "error": str(e), "data_preview": item})

    return valid_records, invalid_records


def quality_check(grant: dict) -> bool:
    """
    Returns True if grant passes quality checks,
    False if it needs manual review. (Logic remains the same)
    """
    # Condition 1 — missing max amount
    if not grant.get("amount_max"):
        return False

    # Condition 2 — empty critical fields
    critical_fields = ["title", "description", "funder", "application_url"]
    empty_count = sum(1 for f in critical_fields if not grant.get(f))
    if empty_count > 1:  # more than one critical field empty
        return False

    # Condition 3 — description too short or generic
    desc = grant.get("description", "").strip().lower()
    if len(desc) < 80 or "click here" in desc or "learn more" in desc:
        return False

    return True


def enrich_grant_text(description: str, notes: str) -> tuple[str, list]:
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


def format_list_fields(record: dict) -> dict:
    """
    Converts list-based fields into semi-column separated strings for CSV export.
    """
    list_fields = [
        "eligible_provinces", 
        "eligible_applicant_type", 
        "eligible_industries", 
        "target_beneficiaries", 
        "supported_project_types", 
        "sdg_alignment"
    ]
    
    for field in list_fields:
        if isinstance(record.get(field), list):
            # Join the list elements with a semi-colon and space
            record[field] = "; ".join(str(item) for item in record[field])
        elif record.get(field) is None:
             # Ensure empty list fields are represented as empty strings in CSV
            record[field] = ""
            
    return record


def save_to_csv(valid_records: list, invalid_records: list):
    """
    Appends validated grant data to the validated_grants.csv
    and logs invalid ones separately if needed.
    """
    if not valid_records:
        logging.warning("No valid records to save.")
        return

    # Apply CSV formatting transformation
    transformed_records = [format_list_fields(record) for record in valid_records]
    df = pd.DataFrame(transformed_records)

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
    # Use a static name for the CSV here so we can check past runs
    static_csv_name = os.path.join(DATA_DIR, "validated_grants.csv")
    if not os.path.exists(static_csv_name):
        return set()

    try:
        df = pd.read_csv(static_csv_name, usecols=["source_url"], dtype={'source_url': str})
        return set(df["source_url"].dropna().tolist())
    except Exception as e:
        logging.error(f"Error loading processed URLs: {e}")
        return set()


def run_pipeline():
    """
    Full end-to-end process:
    1. Loop through URLs
    2. Extract via Gemini (now with grounding)
    3. Parse + Validate
    4. Enrich (summary + keywords)
    5. Save valid + invalid data (now with CSV list formatting)
    """
    global client # Ensure client is globally accessible
    if not API_KEY:
        logging.error("Pipeline cannot run without API Key.")
        return

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

        # 1. Extract raw JSON from Gemini
        raw = extract_from_gemini(url)
        if not raw:
            all_invalid.append({"source_url": url, "error": "Gemini extraction failed"})
            continue

        # 2. Parse + validate
        valid, invalid = parse_and_validate(raw, url)

        # 3. Enrich each valid grant
        for grant in valid:
            # We use a separate LLM call for enrichment, which CAN use structured output 
            # because it does NOT use the Google Search tool.
            summary, keywords = enrich_grant_text(grant["description"], grant["notes"]) 

            # Construct enriched notes
            enriched_note = f"{grant['notes'].strip()}\n\n---\nSummary: {summary}\nKeywords: {', '.join(keywords)}"
            grant["notes"] = enriched_note


        # 4. Aggregate results
        all_valid.extend(valid)
        all_invalid.extend(invalid)

        time.sleep(2)  # slight delay to avoid rate limit

    # 5. Split between high-quality and manual-review grants
    high_quality, manual_review = [], []

    for grant in all_valid:
        if quality_check(grant):
            high_quality.append(grant)
        else:
            manual_review.append(grant)

    # Save them separately
    save_to_csv(high_quality, all_invalid)

    if manual_review:
        review_path = os.path.join(DATA_DIR, "manual_review.csv")
        # Apply formatting for the review file too
        df_review = pd.DataFrame([format_list_fields(r) for r in manual_review])
        append_review = os.path.exists(review_path)
        df_review.to_csv(review_path, mode="a", header=not append_review, index=False, encoding="utf-8")
        logging.warning(f"{len(manual_review)} records moved to manual review at {review_path}")


    logging.info("=== Extraction Complete ===")
    logging.info(f"Total URLs processed: {total}")
    logging.info(f"Valid grants: {len(all_valid)}")
    logging.info(f"Invalid grants: {len(all_invalid)}")
    logging.info(f"Output file: {VALIDATED_CSV}")


if __name__ == "__main__":
    run_pipeline()