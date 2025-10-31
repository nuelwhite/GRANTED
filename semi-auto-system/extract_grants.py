"""
    This script extracts structured grant data from grant sources using Gemini AI
    and saves it to data/raw as a timestamped CSV.
"""

import os
import json
import time
import pandas as pd
from datetime import datetime
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