""" Final version 1 of the extraction script
    This script extracts grant data from the URLs avaliable
    And saves the extracted data in csv format in 'data/raw' directory
    with extraction logs in 'data/logs'
"""

import json 
import os
import random
import time
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from typing import List, Optional
from utils.email_notifier import send_notification

# --- 1. Define Grant Schema for data collection using Pydantic"

class GrantData(BaseModel):
    """Structured data extracted from a grant page."""
    grant_id: str = Field(description="Unique identifier for the grant, e.g., 'VentureLAB_AAI_2024'.")
    title: str = Field(description="Full, descriptive title of the grant.")
    description: str = Field(description="A concise summary of the grant's purpose, scope, and who it helps.")
    funder: str = Field(description="The full name of the organization providing the funding.")
    funder_type: str = Field(description="Type of funder (e.g., 'Government', 'Non-profit', 'Private Foundation').")
    funding_type: str = Field(description="Nature of the funding (e.g., 'Grant', 'Loan', 'Tax Credit').")
    amount_min: Optional[int] = Field(None, description="Minimum funding amount (in CENTS or smallest currency unit). Use None if not specified.")
    amount_max: Optional[int] = Field(None, description="Maximum funding amount (in CENTS or smallest currency unit). Use None if not specified.")
    currency: str = Field(description="The three-letter currency code (e.g., 'CAD', 'USD').")
    deadline: str = Field(description="The application deadline, formatted as 'YYYY-MM-DD' or a descriptive phrase if a date isn't available (e.g., 'Ongoing').")
    application_complexity: str = Field(description="Estimated complexity (e.g., 'Low', 'Medium', 'High').")
    eligible_provinces: List[str] = Field(description="List of eligible provinces/states/regions. Use ['National'] if nationwide.")
    geography_details: str = Field(description="Any specific local or regional restrictions not covered by provinces.")
    eligible_applicant_type: List[str] = Field(description="List of organization types that can apply (e.g., 'Small Business', 'Non-profit', 'Individual').")
    eligible_industries: List[str] = Field(description="List of specific industries or sectors targeted.")
    target_beneficiaries: List[str] = Field(description="List of groups the grant is intended to support (e.g., 'Youth', 'Women-owned businesses').")
    supported_project_types: List[str] = Field(description="List of projects the grant can fund (e.g., 'R&D', 'Equipment Purchase', 'Training').")
    sdg_alignment: List[str] = Field(description="List of UN Sustainable Development Goals the grant aligns with.")
    application_url: str = Field(description="Direct URL to the application page or program details.")
    is_recurring: bool = Field(description="True if the grant is offered on a regular cycle (e.g., annually), False otherwise.")
    notes: str = Field(description="Any essential caveats or additional information.")
    application_docs_raw: str = Field(description="Raw text snippet listing required application documents.")
    application_questions_text: str = Field(description="Raw text snippet of the main questions or sections in the application.")

# --- 2. SETUP AND CONFIGURATION ---

# load environment variables
load_dotenv()

# load api key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("No GEMINI AI API key found in the .env file")

# configure gemini
client = genai.Client(api_key=api_key)


# Directories
os.makedirs("semi-auto-system/data/raw", exist_ok=True)
os.makedirs("semi-auto-system/data/logs", exist_ok=True)

timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
log_file = f"semi-auto-system/data/logs/extraction_{timestamp}.log"


## Configure logging
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.getLogger().addHandler(logging.StreamHandler())

# --- 3. BEGIN EXTRACTION ---

logging.info("...STARTING EXTRACTION PIPELINE...")

# load config file containing URLs
SOURCES_FILE = r"semi-auto-system/config/sources_list.json"
try:
    with open(SOURCES_FILE, 'r') as f:
        sources = json.load(f).get('sources', [])
        logging.info(f"Loaded {len(sources)} sources from {SOURCES_FILE}")
except FileNotFoundError:
    logging.error(f"Error: Could not find sources file at {SOURCES_FILE}")
    sources = []

# --- Main Extraction Point---
def extract_grant(url, retries = 3, backoff = 2.0):
    attempt = 0
    while attempt < retries:
        attempt += 1

        try:
            logging.info(f"Extracting from: {url}. \nAttempting {attempt}/{retries}")

            # prompt for data collection
            prompt = f"""
                    You are a data extraction assistant for a grant management platform.
                    Extract all required grant-related information from the following page:
                    {url}
                    
                    Ensure amounts are converted to the smallest currency unit (e.g., CENTS if currency is USD/CAD).
                    Populate all fields with the best available data. If data is unavailable, use default/empty values like None for Optionals, or empty lists for List fields.
                    """

            
            # make the request to gemini with the Structured Output configuration
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json", 
                    response_schema=GrantData,          
                    ),
                )

            # parse response
            parsed_grant = response.parsed
            grant_dict = parsed_grant.model_dump()
            grant_dict["source_url"] = url 
            logging.info(f"SUCCESS: {parsed_grant.title[:70]}")
            return grant_dict

        except Exception as e:
            wait_time = backoff * (2 ** (attempt - 1)) + random.uniform(0, 1)
            logging.warning(f"ERROR: {e}. Retrying in {wait_time:1f}s...")
            time.sleep(wait_time)

    # if all attempts fail
    logging.error(f"Extraction failed after {retries} attempts: {url}")

    return {"source_url": url, "error": "Extraction failed after retries"}



# Execution loop

def run_batch_extraction():
    results, failures = [], []
    total = len(sources)

    for i, url in enumerate(sources, start=1):
        logging.info(f"\n---- [{i}/{total}] Processing {url} ----")
        result = extract_grant(url)
        if "error" in result:
            failures.append(result)
        results.append(result)
        time.sleep(2)

    # Save all results
    df = pd.DataFrame(results)
    out_file = f"semi-auto-system/data/raw/grants_raw_{timestamp}.csv"
    df.to_csv(out_file, index=False, encoding="utf-8")
    logging.info(f"Saved all records to {out_file}")

    # Save failed URLs separately
    if failures:
        failed_df = pd.DataFrame(failures)
        failed_path = f"semi-auto-system/data/raw/failed_{timestamp}.csv"
        failed_df.to_csv(failed_path, index=False)
        logging.warning(f"{len(failures)} failures saved to {failed_path}")
    else:
        logging.info("All sources processed successfully.")

    
    logging.info("Extraction job complete.")
    logging.info(f"Total sources: {total}")
    logging.info(f"Successful: {total - len(failures)}")
    logging.info(f"Failed: {len(failures)}")
    
    # Return metrics and output path for downstream notification
    return (total - len(failures), len(failures), out_file)

if __name__ == "__main__":
    success_count, fail_count, out_file = run_batch_extraction()
    send_notification(
        success_count=success_count,
        fail_count=fail_count,
        csv_path=out_file,
        log_path=log_file,
        )