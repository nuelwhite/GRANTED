import os
import json
import pandas as pd
import pydantic
import logging
from datetime import datetime
from dotenv import load_dotenv


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