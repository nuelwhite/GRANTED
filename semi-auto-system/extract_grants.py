"""
    This script extracts structured grant data from grant sources using Gemini AI
    and saves it to data/raw as a timestamped CSV.
"""

import os
import json
import time
import pandas as pd
from datetime import datetime, timezone
from google import genai
from dotenv import load_dotenv
import logging


# load environment variables
load_dotenv()


# configure gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# Configure file paths
SOURCES_FILE = "config/sources_list.json"
OUTPUT_DIR = "data/raw"


# create a directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)


# function to extract from source:: uses gemini to extract structured data
def extract_from_source(url):

    prompt = f"""
    You are a data extraction assistant for a grant management platform.
    Extract structured information from the following page:
    {url}

    Return a JSON object with these fields:
    grant_id, title, description, funder, funder_type, funding_type,
    amount_min, amount_max, currency, deadline, application_complexity,
    eligible_provinces, geography_details, eligible_applicant_type,
    eligible_industries, target_beneficiaries, supported_project_types,
    sdg_alignment, application_url, is_recurring, notes,
    application_docs_raw, application_questions_text
    """

    try:
        response = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt)
        result_text = response.text.strip()
        data = json.loads(result_text)
        data["source_url"] = url
        return data
    except Exception as e:
        print(f"Error extracting from {url}: {e}")
        return {"source_url": url, "error": str(e)}

    

# function to run main extraction
def run_extraction():
    with open(SOURCES_FILE, 'r') as f:
        sources = json.load(f).get("sources", [])

    
    all_data = []
    for url in sources:
        print(f"Extracting data from {url} ...")

        grant_data = extract_from_source(url)
        all_data.append(grant_data)

        time.sleep(5)   # sleep for 5 secs to avoid rate limits

        # convert extracted data to pandas Dataframe
        df = pd.DataFrame(all_data)


        # save dataframe as csv with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(OUTPUT_DIR, f"grants_raw_{timestamp}.csv")

        df.to_csv(output_file, index=False)

        print(f"Extraction Complete. Saved to {output_file}")
        print(f"Total grants extraccted: {len(df)}")

    
if "__name__" == "__main__":
    run_extraction()