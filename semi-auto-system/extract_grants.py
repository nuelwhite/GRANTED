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