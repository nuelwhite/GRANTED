import os
import json
import pandas as pd
import pydantic
import logging
from datetime import datetime
from dotenv import load_dotenv
import time
import random
from google import genai


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


def build_prompt(url):
    """
    Creates a detailed extraction prompt for Gemini.
    Emphasizes completeness and detail for description and notes fields.
    """
    return f"""
You are a grant data extraction assistant for an AI-powered funding-match platform.

Extract all detailed information about grants from this webpage: {url}

If the page lists multiple grants, extract *all* of them as an array of JSON objects.
If it contains a single grant, return a single JSON object.

Use this JSON structure exactly (fill empty or unknown values with null, [] or ""):

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
- Make `description` long and rich in detail — include purpose, scope, eligibility, and funding highlights.
- Add any extra clarifications, exceptions, or context in `notes`.
- Use ISO format for dates (YYYY-MM-DD) when possible.
- Do not invent information. Keep factual accuracy.
- Return *only* valid JSON — no text outside the JSON structure.
"""

