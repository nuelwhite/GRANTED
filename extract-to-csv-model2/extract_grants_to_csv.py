import os
import json
import re
import pandas as pd
from pydantic import BaseModel, Field
import logging
from typing import Optional, List
from datetime import datetime, UTC
from dotenv import load_dotenv
import time
import random
from google import genai

## ---1. CONFIGURATION
# LOAD ENVIRONMENT VARIABLES
load_dotenv()

# Load API key.
API_KEY = os.getenv("GEMINI_API_KEY") 
if not API_KEY:
    logging.error("No GEMINI API KEY found in .env file! Ensure it is set for successful execution.")


# directory setup
CONFIG_PATH = "config/sources_list.json"
DATA_DIR = "data/processed"
LOG = 'data/log'
RAW_OUTPUT_DIR = os.path.join(DATA_DIR, "raw_output.jsonl")

# Using UTC time for robust timestamping
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

logging.info("=== GRANT EXTRACTION PIPELINE V2 INITIALIZED ===")


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
MAX_TOKENS = 8096


# ENUM MAPPINGS FOR VALIDATION
VALID_FUNDER_TYPES = [
    "FEDERAL_GRANT",
    "PROVINCIAL_TERRITORIAL_GRANT",
    "MUNICIPAL_GRANT",
    "FOUNDATION_GRANT",
    "CORPORATE_GRANT",
    "COMMUNITY_ASSOCIATION_GRANT",
    "UNIVERSITY_COLLEGE_GRANT",
    "ACCELERATOR_INCUBATOR_GRANT",
    "OTHER"
]

VALID_FUNDING_TYPES = [
    "GRANT",
    "LOAN",
    "EQUITY",
    "TAX_CREDIT",
    "PRIZE",
    "IN_KIND"
]

VALID_SECTORS = [
    "AGRICULTURE",
    "HEALTH",
    "EDUCATION",
    "ENERGY",
    "TECHNOLOGY",
    "MANUFACTURING",
    "ENVIRONMENT",
    "CREATIVE",
    "SOCIAL_SERVICES",
    "FINANCE",
    "LEGAL",
    "PROFESSIONAL_SERVICES",
    "TRANSPORTATION",
    "CONSTRUCTION",
    "HOSPITALITY",
    "RETAIL",
    "OPEN_TO_ALL",
    "N_A"
]

VALID_APPLICANT_TYPES = [
    "INDIVIDUAL",
    "NON_PROFIT",
    "FOR_PROFIT",
    "RESEARCH_INSTITUTION",
    "PUBLIC_ENTITY",
    "OPEN_TO_ALL",
    "N_A"
]

VALID_BUSINESS_STAGES = [
    "IDEA",
    "EARLY_STAGE",
    "GROWTH",
    "ESTABLISHED"
]

VALID_REVENUE_RANGES = [
    "NONE",
    "UNDER_50K",
    "BETWEEN_50K_250K",
    "BETWEEN_250K_1M",
    "BETWEEN_1M_5M",
    "ABOVE_5M"
]

VALID_EMPLOYEE_RANGES = [
    "SOLO",
    "BETWEEN_1_5",
    "BETWEEN_6_20",
    "BETWEEN_21_50",
    "ABOVE_50"
]

VALID_EQUITY_FOCUS = [
    "RURAL", "URBAN", "REMOTE",
    "INDIGENOUS", "WOMEN_LED", "BIPOC_LED", "MINORITY_LED",
    "YOUTH", "SENIOR", "LGBTQ_PLUS", "VETERAN", "DISABLED",
    "IMMIGRANT", "REFUGEE", "LOW_INCOME", "UNDERSERVED"
]

VALID_GRANT_PURPOSE = [
    "RESEARCH", "PRODUCT_DEVELOPMENT", "CAPACITY_BUILDING",
    "INFRASTRUCTURE", "PROGRAM_EXPANSION", "OPERATIONAL",
    "CAPITAL", "EQUIPMENT", "TRAINING", "COMMUNITY_ENGAGEMENT",
    "MARKETING", "TECHNOLOGY", "HIRING"
]


def build_prompt(url: str) -> str:
    schema_definition = """
[
    {
        "grantID": "Unique identifier (e.g., GRANT-2024-001)",
        "programName": "Official title of the grant program",
        "programDescription": "Full detailed description including purpose, eligibility, and funding details",
        "funderName": "Organization offering the grant",
        "funderType": "One of: FEDERAL_GRANT, PROVINCIAL_TERRITORIAL_GRANT, MUNICIPAL_GRANT, FOUNDATION_GRANT, CORPORATE_GRANT, COMMUNITY_ASSOCIATION_GRANT, UNIVERSITY_COLLEGE_GRANT, ACCELERATOR_INCUBATOR_GRANT, OTHER",
        "programURL": "URL to official grant program page",
        "sourceType": "MANUAL_ENTRY",
        "programStatus": "One of: ACTIVE, CLOSED, UPCOMING, SUSPENDED",
        "currency": "ISO 4217 code (CAD, USD, etc.)",
        
        "eligibility": {
            "eligibleSectors": ["Array of sectors"],
            "eligibleGeographies": ["Array of ISO-2 country codes"],
            "businessStage": "One of: IDEA, EARLY_STAGE, GROWTH, ESTABLISHED (or null)",
            "organizationType": ["Array from: INDIVIDUAL, NON_PROFIT, FOR_PROFIT, RESEARCH_INSTITUTION, PUBLIC_ENTITY, OPEN_TO_ALL, N_A"],
            "revenueRange": "One of: NONE, UNDER_50K, BETWEEN_50K_250K, BETWEEN_250K_1M, BETWEEN_1M_5M, ABOVE_5M (or null)",
            "employeeRange": "One of: SOLO, BETWEEN_1_5, BETWEEN_6_20, BETWEEN_21_50, ABOVE_50 (or null)",
            "eligibleActivities": ["Array of eligible activities"],
            "ineligibleActivities": ["Array of ineligible activities"],
            "equityFocus": ["Array from equity focus options"],
            "grantPurpose": ["Array from grant purpose options"],
            "eligibilityNotes": "Additional eligibility notes",
            "additionalEligibilityCriteria": "Additional criteria"
        },
        
        "fundingStructure": {
            "fundingType": "One of: GRANT, LOAN, EQUITY, TAX_CREDIT, PRIZE, IN_KIND",
            "amountMin": 5000.00,
            "amountMax": 100000.00,
            "fixedAmount": null,
            "ratePercentage": null,
            "matchRequired": false,
            "matchPercentage": null,
            "nonRepayable": true,
            "repaymentTerms": null,
            "advancePayment": false,
            "reimbursementFrequency": "Quarterly, Monthly, etc. (or null)",
            "eligibleExpenseCategories": ["Array of eligible expense types"]
        },
        
        "deadlines": {
            "applicationOpenDate": "2024-01-01T00:00:00Z",
            "applicationCloseDate": "2024-12-31T23:59:59Z (or null for rolling)",
            "rollingDeadlineFlag": false,
            "loidDeadline": null,
            "decisionDate": null,
            "awardStartDate": null,
            "awardEndDate": null,
            "renewalDeadline": null,
            "reportingFrequency": "Quarterly, Annually, etc. (or null)",
            "keyMilestones": "Description of key milestones"
        },
        
        "documentation": {
            "businessPlanRequired": false,
            "financialStatementsRequired": false,
            "taxReturnsRequired": false,
            "incorporationDocumentsRequired": false,
            "lettersOfSupportRequired": false,
            "researchProposalRequired": false,
            "impactAssessmentRequired": false,
            "additionalDocuments": ["Array of additional document types"]
        },
        
        "compliance": {
            "reportingRequirements": "Description",
            "auditRequirement": "Description",
            "siteVisitRequirement": "Description",
            "dataCollectionRequirement": "Description",
            "ipRightsClauses": "Description",
            "publicityRequirement": "Description",
            "complianceScoring": "Description"
        },
        
        "contact": {
            "primaryContactName": "Contact person name",
            "primaryContactEmail": "email@example.com",
            "primaryContactPhone": "+1-123-456-7890",
            "programManagerName": "Manager name",
            "applicationPortalURL": "https://portal.example.com"
        },
        
        "programCategory": {
            "sector": "Primary sector",
            "theme": "Grant theme",
            "pillar": "Strategic pillar",
            "stage": "Business stage focus",
            "ediPriority": false
        }
    }
]
    """
    
    return f"""
You are an expert grant data extraction assistant. Extract grant information from: {url}

**ABSOLUTE REQUIREMENTS:**
1. Output ONLY the JSON array - nothing else
2. NO markdown code blocks (no ```)
3. NO explanatory text before or after the JSON
4. NO citation tags like [cite:...] anywhere
5. NO comments or notes
6. All text must be on single lines - no line breaks inside string values
7. Properly escape all quotes and special characters

Your response must start with [ and end with ]

SCHEMA:
{schema_definition}

**IMPORTANT FORMATTING RULES:**
- Keep ALL text on single continuous lines
- Replace any newlines in text with spaces
- Ensure all commas are present between properties
- Use exact enum values from schema
- For arrays, use [] if empty
- For null values, use null not empty string

Extract ALL grants found at the URL and return as a JSON array.
    """


def clean_json_string(text: str) -> str:
    """
    Clean JSON string by removing/escaping problematic characters
    """
    # First, try to extract just the JSON array/object if there's extra text
    # Look for the outermost [ or { and matching ] or }
    json_match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    
    # Remove common unicode characters that cause issues
    text = text.replace('\u00a0', ' ')  # Non-breaking space
    text = text.replace('\u200b', '')   # Zero-width space
    text = text.replace('\u2028', ' ')  # Line separator
    text = text.replace('\u2029', ' ')  # Paragraph separator
    text = text.replace('\r\n', ' ')    # Windows line endings
    text = text.replace('\r', ' ')      # Mac line endings
    text = text.replace('\t', ' ')      # Tabs
    
    # Remove control characters (except newlines that are valid in JSON structure)
    # This regex keeps structural newlines but removes embedded control chars
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
    
    # Now handle newlines more carefully - only keep those in JSON structure (between elements)
    # Replace newlines that are likely inside string values
    lines = text.split('\n')
    cleaned_lines = []
    in_string = False
    
    for line in lines:
        # Count unescaped quotes to track if we're inside a string
        quote_count = len(re.findall(r'(?<!\\)"', line))
        
        if in_string:
            # We're inside a string value - join with space
            if cleaned_lines:
                cleaned_lines[-1] = cleaned_lines[-1].rstrip() + ' ' + line.lstrip()
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
        
        # Toggle in_string if odd number of quotes
        if quote_count % 2 == 1:
            in_string = not in_string
    
    text = '\n'.join(cleaned_lines)
    
    # Final safety: collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    
    return text


def extract_from_gemini(url: str, retries: int = 3, backoff: float = 2.0) -> Optional[str]:
    """
    Handles the API call with retry/backoff.
    Returns raw JSON text or None on failure.
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
                    # Removed tools - let Gemini read the URL directly for cleaner JSON output
                ),
            )
            
            # Check if response has text
            if not response.text:
                logging.warning(f"Empty response from Gemini for {url}")
                continue
                
            raw_text = response.text.strip()
            
            # Remove citation tags that break JSON
            raw_text = re.sub(r'\[cite:\[.*?\]\]', '', raw_text, flags=re.DOTALL)
            raw_text = re.sub(r'\[cite:.*?\]', '', raw_text)
            
            # Remove any markdown code blocks (more aggressive)
            raw_text = re.sub(r'```json\s*', '', raw_text)
            raw_text = re.sub(r'```\s*', '', raw_text)
            
            # Remove any text before the first [ or {
            match = re.search(r'^[^\[\{]*?([\[\{])', raw_text, re.DOTALL)
            if match:
                raw_text = raw_text[match.start(1):]
            
            # Remove any text after the last ] or }
            last_bracket = max(raw_text.rfind(']'), raw_text.rfind('}'))
            if last_bracket != -1:
                raw_text = raw_text[:last_bracket + 1]
            
            # Clean the JSON string
            raw_text = clean_json_string(raw_text)
            
            # Final validation: check if it looks like valid JSON
            if not raw_text.startswith(('[', '{')):
                logging.warning(f"Response doesn't start with [ or {{, attempting to extract JSON...")
                # Try one more time to find JSON
                match = re.search(r'([\[\{].*[\]\}])', raw_text, re.DOTALL)
                if match:
                    raw_text = match.group(1)
            
            # Create a clean, readable filename from the URL
            # Extract domain and path parts
            url_parts = url.replace('https://', '').replace('http://', '').split('/')
            domain = url_parts[0].replace('www.', '')
            path_parts = [p for p in url_parts[1:] if p and p not in ['funding', 'grants', 'programs', 'application']]
            
            # Take last 2-3 meaningful parts of the path
            meaningful_parts = path_parts[-3:] if len(path_parts) >= 3 else path_parts
            
            # Create clean filename
            if meaningful_parts:
                safe_name = '-'.join(meaningful_parts)
            else:
                safe_name = domain.split('.')[0]  # Use first part of domain if no path
            
            # Clean the name
            safe_name = re.sub(r'[^\w\-]', '-', safe_name)
            safe_name = re.sub(r'-+', '-', safe_name)  # Replace multiple dashes with single
            safe_name = safe_name.strip('-')[:80]  # Limit length and remove trailing dashes
            
            # Add date
            date_str = datetime.now(UTC).strftime('%Y-%m-%d')
            debug_file = os.path.join(DATA_DIR, f"{safe_name}_{date_str}.json")
            
            # If file exists, add a counter
            counter = 1
            while os.path.exists(debug_file):
                debug_file = os.path.join(DATA_DIR, f"{safe_name}_{date_str}_{counter}.json")
                counter += 1
            
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(raw_text)
            logging.info(f"Raw response saved to {debug_file}")
            
            return raw_text
        
        except Exception as e:
            wait = backoff * (2 ** (attempt - 1)) + random.uniform(0, 1)
            logging.warning(f"Gemini request failed: {e}. Retrying in {wait:.1f}s...")
            time.sleep(wait)
            
    logging.error(f"All attempts failed for: {url}")
    return None


def validate_enum(value: str, valid_values: List[str], field_name: str) -> str:
    """Validate single enum value"""
    if not value:
        return None
    if value.upper() in valid_values:
        return value.upper()
    logging.warning(f"Invalid {field_name}: {value}. Setting to None/default.")
    return None


def validate_enum_array(values: List[str], valid_values: List[str], field_name: str) -> List[str]:
    """Validate array of enum values with smart mapping"""
    if not values:
        return []
    
    # Mapping dictionaries for common variations
    sector_mappings = {
        # Health/Medical/Life Sciences
        "HEALTHCARE": "HEALTH",
        "HEALTHCARE TECHNOLOGY": "HEALTH",
        "DIGITAL HEALTH": "HEALTH",
        "MEDICAL DEVICES": "HEALTH",
        "DIAGNOSTICS": "HEALTH",
        "THERAPEUTICS": "HEALTH",
        "HEALTH TECHNOLOGY": "HEALTH",
        "BIOMARKERS": "HEALTH",
        "MEDICAL TECHNOLOGY": "HEALTH",
        "HEALTHTECH": "HEALTH",
        "MEDTECH": "HEALTH",
        "VIRTUAL CARE": "HEALTH",
        "PRECISION HEALTH": "HEALTH",
        "REGENERATIVE MEDICINE": "HEALTH",
        "ADVANCED MEDICAL IMAGING": "HEALTH",
        "PERSONALIZED MEDICINE": "HEALTH",
        "PUBLIC HEALTH": "HEALTH",
        "HEALTH SYSTEM INNOVATION": "HEALTH",
        "BIOTECH": "HEALTH",
        "BIOTECHNOLOGY": "HEALTH",
        "PHARMA": "HEALTH",
        "PHARMACEUTICAL": "HEALTH",
        "LIFE SCIENCES": "HEALTH",
        "LIFE_SCIENCES": "HEALTH",
        # Technology/Digital
        "ARTIFICIAL INTELLIGENCE": "TECHNOLOGY",
        "MACHINE LEARNING": "TECHNOLOGY",
        "DATA ANALYTICS": "TECHNOLOGY",
        "REMOTE MONITORING": "TECHNOLOGY",
        "ROBOTICS": "TECHNOLOGY",
        "AUTOMATION": "TECHNOLOGY",
        "SOFTWARE": "TECHNOLOGY",
        "IT": "TECHNOLOGY",
        "INFORMATION TECHNOLOGY": "TECHNOLOGY",
        "INFORMATION_TECHNOLOGY": "TECHNOLOGY",
        "DIGITAL ECONOMY": "TECHNOLOGY",
        "DEEP TECH": "TECHNOLOGY",
        "INNOVATION": "TECHNOLOGY",
        "CLIMATE TECH": "ENERGY",
        # Energy/CleanTech
        "CLEANTECH": "ENERGY",
        "CLEAN TECHNOLOGY": "ENERGY",
        # Agriculture/Food
        "AGTECH": "AGRICULTURE",
        "AGRI-FOOD": "AGRICULTURE",
        "AGRI_FOOD": "AGRICULTURE",
        # Finance
        "FINTECH": "FINANCE",
        # Education
        "EDTECH": "EDUCATION",
        # Arts & Culture
        "ARTS": "CREATIVE",
        "CULTURE": "CREATIVE",
        "ARTS AND CULTURE": "CREATIVE",
        "PERFORMING ARTS": "CREATIVE",
        "VISUAL ARTS": "CREATIVE",
        "LITERARY ARTS": "CREATIVE",
        "MEDIA ARTS": "CREATIVE",
        "CRAFT": "CREATIVE",
        "DESIGN": "CREATIVE",
        "COMMUNITY ARTS": "CREATIVE",
        "CREATIVE INDUSTRIES": "CREATIVE",
        "CREATIVE ARTS": "CREATIVE",
        # Hospitality/Tourism
        "TOURISM": "HOSPITALITY",
        # Manufacturing/Materials
        "ADVANCED MATERIALS": "MANUFACTURING",
        # Science/Research/Academia
        "SCIENCE": "TECHNOLOGY",
        "ENGINEERING": "TECHNOLOGY",
        "SOCIAL SCIENCES": "SOCIAL_SERVICES",
        "HUMANITIES": "EDUCATION",
        # Business/General
        "EXPORT-ORIENTED BUSINESSES": "OPEN_TO_ALL",
        "GENERAL BUSINESS INNOVATION": "OPEN_TO_ALL",
    }
    
    purpose_mappings = {
        # Research & Development
        "INNOVATION": "RESEARCH",
        "RESEARCH_AND_DEVELOPMENT": "RESEARCH",
        "R&D": "RESEARCH",
        "RESEARCH & DEVELOPMENT": "RESEARCH",
        "VALIDATION": "RESEARCH",
        "CLINICAL_TRIALS": "RESEARCH",
        "PROOF_OF_CONCEPT": "RESEARCH",
        # Product Development
        "COMMERCIALIZATION": "PRODUCT_DEVELOPMENT",
        "PROTOTYPING": "PRODUCT_DEVELOPMENT",
        "PRODUCT DEVELOPMENT": "PRODUCT_DEVELOPMENT",
        "PRODUCT_DEVELOPMENT": "PRODUCT_DEVELOPMENT",
        # Business Growth & Operations
        "BUSINESS_GROWTH": "OPERATIONAL",
        "BUSINESS GROWTH": "OPERATIONAL",
        "OPERATING SUPPORT": "OPERATIONAL",
        "PROGRAM DELIVERY": "OPERATIONAL",
        "BUSINESS_DEVELOPMENT": "OPERATIONAL",
        "BUSINESS DEVELOPMENT": "OPERATIONAL",
        "PRODUCTIVITY IMPROVEMENT": "OPERATIONAL",
        "ECONOMIC DEVELOPMENT": "OPERATIONAL",
        # Expansion & Scaling
        "PILOT_PROJECTS": "RESEARCH",
        "SCALING_UP": "PROGRAM_EXPANSION",
        "SCALE_UP": "PROGRAM_EXPANSION",
        "EXPANSION": "PROGRAM_EXPANSION",
        "MARKET_EXPANSION": "MARKETING",
        "MARKET EXPANSION": "MARKETING",
        "MARKET ENTRY & EXPANSION": "MARKETING",
        "EXPORT_DEVELOPMENT": "MARKETING",
        # Capacity & Training
        "HEALTH_SYSTEM_IMPROVEMENT": "CAPACITY_BUILDING",
        "CAPACITY BUILDING": "CAPACITY_BUILDING",
        "CAPACITY_BUILDING": "CAPACITY_BUILDING",
        "PROFESSIONAL DEVELOPMENT": "TRAINING",
        # Technology & Digital
        "TECHNOLOGY_ADOPTION": "TECHNOLOGY",
        "TECH_ADOPTION": "TECHNOLOGY",
        "DIGITAL_ADOPTION": "TECHNOLOGY",
        "TECHNOLOGY ADOPTION": "TECHNOLOGY",
        # Marketing & Market Access
        "MARKET_ACCESS": "MARKETING",
        "MARKET ACCESS": "MARKETING",
        # Community & Engagement
        "ARTS AND CULTURE": "COMMUNITY_ENGAGEMENT",
        "COMMUNITY DEVELOPMENT": "COMMUNITY_ENGAGEMENT",
        # Job Creation
        "JOB CREATION": "HIRING",
    }
    
    equity_mappings = {
        # Black/BIPOC/Racialized
        "BLACK-LED": "BIPOC_LED",
        "BLACK LED": "BIPOC_LED",
        "BLACK": "BIPOC_LED",
        "RACIALIZED COMMUNITIES": "BIPOC_LED",
        "RACIALIZED GROUPS": "BIPOC_LED",
        "VISIBLE_MINORITY": "BIPOC_LED",
        "VISIBLE MINORITY": "BIPOC_LED",
        "MINORITY": "MINORITY_LED",
        "MINORITY-LED": "MINORITY_LED",
        "MINORITY LED": "MINORITY_LED",
        # Indigenous
        "INDIGENOUS": "INDIGENOUS",
        "INDIGENOUS_PEOPLE": "INDIGENOUS",
        "INDIGENOUS PEOPLE": "INDIGENOUS",
        # Women
        "WOMEN-LED": "WOMEN_LED",
        "WOMEN LED": "WOMEN_LED",
        "WOMEN": "WOMEN_LED",
        # LGBTQ+
        "LGBTQ": "LGBTQ_PLUS",
        "LGBTQ+": "LGBTQ_PLUS",
        "LGBTQ2S+": "LGBTQ_PLUS",
        "LGBTQ2S": "LGBTQ_PLUS",
        # Disability
        "DISABLED": "DISABLED",
        "DISABILITY": "DISABLED",
        "PEOPLE_WITH_DISABILITIES": "DISABLED",
        "PEOPLE WITH DISABILITIES": "DISABLED",
        # Geographic
        "RURAL": "RURAL",
        "URBAN": "URBAN",
        "REMOTE": "REMOTE",
        # Age
        "YOUTH": "YOUTH",
        "SENIOR": "SENIOR",
        "SENIORS": "SENIOR",
        # Immigration/Refugee
        "IMMIGRANT": "IMMIGRANT",
        "IMMIGRANTS": "IMMIGRANT",
        "REFUGEE": "REFUGEE",
        "REFUGEES": "REFUGEE",
        # Veterans
        "VETERAN": "VETERAN",
        "VETERANS": "VETERAN",
        # Economic
        "LOW-INCOME": "LOW_INCOME",
        "LOW INCOME": "LOW_INCOME",
        "UNDERSERVED": "UNDERSERVED",
    }
    
    # Choose the right mapping based on field name
    mappings = {}
    if "sector" in field_name.lower():
        mappings = sector_mappings
    elif "purpose" in field_name.lower():
        mappings = purpose_mappings
    elif "equity" in field_name.lower():
        mappings = equity_mappings
    
    validated = []
    seen = set()  # Track what we've added to avoid duplicates
    
    for val in values:
        val_upper = str(val).upper().strip()
        
        # First check if it's already a valid enum
        if val_upper in valid_values:
            if val_upper not in seen:
                validated.append(val_upper)
                seen.add(val_upper)
        # Then check if we have a mapping for it
        elif val_upper in mappings:
            mapped = mappings[val_upper]
            if mapped not in seen:
                validated.append(mapped)
                seen.add(mapped)
                logging.info(f"Mapped {field_name} value '{val}' to '{mapped}'")
        else:
            logging.warning(f"Invalid {field_name} value: {val}. Skipping.")
    
    return validated


def parse_and_validate(raw_json: str, source_url: str) -> tuple:
    """
    Parse Gemini's JSON response and validate each record with enum checking.
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
        logging.error(f"Raw JSON preview (first 500 chars): {raw_json[:500]}")
        logging.error(f"Raw JSON preview (around error): {raw_json[max(0, e.pos-100):min(len(raw_json), e.pos+100)]}")
        
        # Try multiple auto-fix strategies
        fixed = False
        parsed = None
        
        # Strategy 1: Fix missing commas between string values and property names
        if not fixed:
            try:
                # Add comma between }" and next property name
                fixed_json = re.sub(r'"\s*([a-zA-Z_])', r'", \1', raw_json)
                # Also fix closing quote followed by property name without comma
                fixed_json = re.sub(r'([0-9])\s*"([a-zA-Z_])', r'\1, "\2', fixed_json)
                parsed = json.loads(fixed_json)
                logging.info("Successfully parsed JSON after adding missing commas (strategy 1)")
                fixed = True
            except Exception as ex:
                logging.debug(f"Strategy 1 failed: {ex}")
        
        # Strategy 2: Fix unescaped newlines in strings
        if not fixed:
            try:
                fixed_json = re.sub(r'(?<!\\)\n(?=[^,\[\]\{\}:])', ' ', raw_json)
                parsed = json.loads(fixed_json)
                logging.info("Successfully parsed JSON after fixing newlines (strategy 2)")
                fixed = True
            except Exception as ex:
                logging.debug(f"Strategy 2 failed: {ex}")
        
        # Strategy 3: More aggressive - remove all newlines except between elements
        if not fixed:
            try:
                # This removes newlines that aren't followed by whitespace and a structural character
                fixed_json = re.sub(r'\n(?!\s*[,\[\]\{\}"])', ' ', raw_json)
                parsed = json.loads(fixed_json)
                logging.info("Successfully parsed JSON after aggressive newline removal (strategy 3)")
                fixed = True
            except Exception as ex:
                logging.debug(f"Strategy 3 failed: {ex}")
        
        # Strategy 4: Try to find and extract just the first complete JSON object/array
        if not fixed:
            try:
                # Find the first [ or {
                start = raw_json.find('[')
                if start == -1:
                    start = raw_json.find('{')
                
                if start != -1:
                    # Try to balance brackets
                    depth = 0
                    in_string = False
                    escape_next = False
                    
                    for i in range(start, len(raw_json)):
                        char = raw_json[i]
                        
                        if escape_next:
                            escape_next = False
                            continue
                            
                        if char == '\\':
                            escape_next = True
                            continue
                            
                        if char == '"':
                            in_string = not in_string
                            continue
                        
                        if not in_string:
                            if char in '[{':
                                depth += 1
                            elif char in ']}':
                                depth -= 1
                                if depth == 0:
                                    # Found the end
                                    fixed_json = raw_json[start:i+1]
                                    parsed = json.loads(fixed_json)
                                    logging.info("Successfully extracted and parsed complete JSON structure (strategy 4)")
                                    fixed = True
                                    break
            except Exception as ex:
                logging.debug(f"Strategy 4 failed: {ex}")
        
        # Strategy 5: Fix quoted values that break across lines
        if not fixed:
            try:
                # Look for pattern: "some text (more text without closing quote on new line
                fixed_json = re.sub(r'"\s*\n\s*([^"{\[\]},]+)\s*"', r'", "\1"', raw_json)
                parsed = json.loads(fixed_json)
                logging.info("Successfully parsed JSON after fixing multi-line strings (strategy 5)")
                fixed = True
            except Exception as ex:
                logging.debug(f"Strategy 5 failed: {ex}")
        
        if not fixed:
            logging.error("Could not auto-fix JSON. Saving to error file for manual review.")
            error_file = os.path.join(DATA_DIR, f"json_error_{int(time.time())}.txt")
            with open(error_file, "w", encoding="utf-8") as f:
                f.write(f"Source: {source_url}\n")
                f.write(f"Error: {e}\n")
                f.write(f"Error position: {e.pos}\n\n")
                f.write("="*80 + "\n")
                f.write("CONTEXT AROUND ERROR:\n")
                f.write("="*80 + "\n")
                f.write(raw_json[max(0, e.pos-200):min(len(raw_json), e.pos+200)])
                f.write("\n\n")
                f.write("="*80 + "\n")
                f.write("FULL RAW JSON:\n")
                f.write("="*80 + "\n")
                f.write(raw_json)
            logging.error(f"Error details saved to {error_file}")
            return valid_records, invalid_records

    # Handle both single objects and arrays
    if isinstance(parsed, dict):
        parsed = [parsed]
    elif not isinstance(parsed, list):
        logging.warning(f"Unexpected JSON structure for {source_url}")
        return valid_records, invalid_records

    for item in parsed:
        try:
            # Add source URL
            item["sourceURL"] = source_url
            
            # Auto-generate grant_id if missing
            if not item.get("grantID"):
                funder_base = (item.get("funderName") or "UNKNOWN").replace(" ", "_").upper()[:10]
                item["grantID"] = f"GRANT-{datetime.now().year}-{int(time.time())}_{random.randint(100,999)}"
            
            # Validate core enums
            item["funderType"] = validate_enum(item.get("funderType"), VALID_FUNDER_TYPES, "funderType")
            item["programStatus"] = item.get("programStatus", "ACTIVE")
            
            # Validate eligibility enums
            if "eligibility" in item:
                elig = item["eligibility"]
                elig["eligibleSectors"] = validate_enum_array(
                    elig.get("eligibleSectors", []), VALID_SECTORS, "eligibleSectors"
                )
                elig["organizationType"] = validate_enum_array(
                    elig.get("organizationType", []), VALID_APPLICANT_TYPES, "organizationType"
                )
                elig["businessStage"] = validate_enum(
                    elig.get("businessStage"), VALID_BUSINESS_STAGES, "businessStage"
                )
                elig["revenueRange"] = validate_enum(
                    elig.get("revenueRange"), VALID_REVENUE_RANGES, "revenueRange"
                )
                elig["employeeRange"] = validate_enum(
                    elig.get("employeeRange"), VALID_EMPLOYEE_RANGES, "employeeRange"
                )
                elig["equityFocus"] = validate_enum_array(
                    elig.get("equityFocus", []), VALID_EQUITY_FOCUS, "equityFocus"
                )
                elig["grantPurpose"] = validate_enum_array(
                    elig.get("grantPurpose", []), VALID_GRANT_PURPOSE, "grantPurpose"
                )
            
            # Validate funding structure enums
            if "fundingStructure" in item:
                fund = item["fundingStructure"]
                fund["fundingType"] = validate_enum(
                    fund.get("fundingType"), VALID_FUNDING_TYPES, "fundingType"
                )
            
            valid_records.append(item)
            
        except Exception as e:
            logging.warning(f"Validation failed for {source_url} (ID: {item.get('grantID', 'N/A')}): {e}")
            invalid_records.append({"source_url": source_url, "error": str(e), "data_preview": str(item)[:200]})

    return valid_records, invalid_records


def flatten_grant_structure(grant: dict) -> dict:
    """
    Flatten nested grant structure into flat CSV format with proper prefixes
    """
    flat = {
        # Core Grant fields
        "grantID": grant.get("grantID", ""),
        "programName": grant.get("programName", ""),
        "programDescription": grant.get("programDescription", ""),
        "funderName": grant.get("funderName", ""),
        "funderType": grant.get("funderType", ""),
        "programURL": grant.get("programURL", ""),
        "sourceType": grant.get("sourceType", "MANUAL_ENTRY"),
        "sourceURL": grant.get("sourceURL", ""),
        "programStatus": grant.get("programStatus", "ACTIVE"),
        "currency": grant.get("currency", "CAD"),
    }
    
    # Eligibility fields
    elig = grant.get("eligibility", {})
    flat.update({
        "eligibleSectors": "; ".join(elig.get("eligibleSectors", [])),
        "eligibleGeographies": "; ".join(elig.get("eligibleGeographies", [])),
        "businessStage": elig.get("businessStage", ""),
        "organizationType": "; ".join(elig.get("organizationType", [])),
        "revenueRange": elig.get("revenueRange", ""),
        "employeeRange": elig.get("employeeRange", ""),
        "eligibleActivities": "; ".join(elig.get("eligibleActivities", [])),
        "ineligibleActivities": "; ".join(elig.get("ineligibleActivities", [])),
        "equityFocus": "; ".join(elig.get("equityFocus", [])),
        "grantPurpose": "; ".join(elig.get("grantPurpose", [])),
        "eligibilityNotes": elig.get("eligibilityNotes", ""),
        "additionalEligibilityCriteria": elig.get("additionalEligibilityCriteria", ""),
    })
    
    # Funding Structure fields
    fund = grant.get("fundingStructure", {})
    flat.update({
        "fundingType": fund.get("fundingType", ""),
        "amountMin": fund.get("amountMin", ""),
        "amountMax": fund.get("amountMax", ""),
        "fixedAmount": fund.get("fixedAmount", ""),
        "ratePercentage": fund.get("ratePercentage", ""),
        "matchRequired": fund.get("matchRequired", False),
        "matchPercentage": fund.get("matchPercentage", ""),
        "nonRepayable": fund.get("nonRepayable", True),
        "repaymentTerms": fund.get("repaymentTerms", ""),
        "advancePayment": fund.get("advancePayment", False),
        "reimbursementFrequency": fund.get("reimbursementFrequency", ""),
        "eligibleExpenseCategories": "; ".join(fund.get("eligibleExpenseCategories", [])),
    })
    
    # Deadlines fields
    dead = grant.get("deadlines", {})
    flat.update({
        "applicationOpenDate": dead.get("applicationOpenDate", ""),
        "applicationCloseDate": dead.get("applicationCloseDate", ""),
        "rollingDeadlineFlag": dead.get("rollingDeadlineFlag", False),
        "loidDeadline": dead.get("loidDeadline", ""),
        "decisionDate": dead.get("decisionDate", ""),
        "awardStartDate": dead.get("awardStartDate", ""),
        "awardEndDate": dead.get("awardEndDate", ""),
        "renewalDeadline": dead.get("renewalDeadline", ""),
        "reportingFrequency": dead.get("reportingFrequency", ""),
        "keyMilestones": dead.get("keyMilestones", ""),
    })
    
    # Documentation fields
    doc = grant.get("documentation", {})
    flat.update({
        "businessPlanRequired": doc.get("businessPlanRequired", False),
        "financialStatementsRequired": doc.get("financialStatementsRequired", False),
        "taxReturnsRequired": doc.get("taxReturnsRequired", False),
        "incorporationDocumentsRequired": doc.get("incorporationDocumentsRequired", False),
        "lettersOfSupportRequired": doc.get("lettersOfSupportRequired", False),
        "researchProposalRequired": doc.get("researchProposalRequired", False),
        "impactAssessmentRequired": doc.get("impactAssessmentRequired", False),
        "additionalDocuments": "; ".join(doc.get("additionalDocuments", [])),
    })
    
    # Compliance fields
    comp = grant.get("compliance", {})
    flat.update({
        "reportingRequirements": comp.get("reportingRequirements", ""),
        "auditRequirement": comp.get("auditRequirement", ""),
        "siteVisitRequirement": comp.get("siteVisitRequirement", ""),
        "dataCollectionRequirement": comp.get("dataCollectionRequirement", ""),
        "ipRightsClauses": comp.get("ipRightsClauses", ""),
        "publicityRequirement": comp.get("publicityRequirement", ""),
        "complianceScoring": comp.get("complianceScoring", ""),
    })
    
    # Contact fields
    cont = grant.get("contact", {})
    flat.update({
        "primaryContactName": cont.get("primaryContactName", ""),
        "primaryContactEmail": cont.get("primaryContactEmail", ""),
        "primaryContactPhone": cont.get("primaryContactPhone", ""),
        "programManagerName": cont.get("programManagerName", ""),
        "applicationPortalURL": cont.get("applicationPortalURL", ""),
    })
    
    # Program Category fields
    cat = grant.get("programCategory", {})
    flat.update({
        "sector": cat.get("sector", ""),
        "theme": cat.get("theme", ""),
        "pillar": cat.get("pillar", ""),
        "stage": cat.get("stage", ""),
        "ediPriority": cat.get("ediPriority", False),
    })
    
    return flat


def quality_check(grant: dict) -> bool:
    """
    Returns True if grant passes quality checks
    """
    # Check for missing critical core fields
    if not grant.get("programName") or not grant.get("programDescription") or not grant.get("funderName"):
        return False
    
    # Check for funding structure
    fund = grant.get("fundingStructure", {})
    if not fund.get("amountMax") and not fund.get("fixedAmount"):
        return False
    
    # Check description quality
    desc = grant.get("programDescription", "").strip().lower()
    if len(desc) < 100 or "click here" in desc or "learn more" in desc:
        return False
    
    return True


def save_to_csv(valid_records: list, invalid_records: list):
    """
    Saves validated grant data to CSV with flattened structure
    """
    if not valid_records:
        logging.warning("No valid records to save.")
        return

    # Flatten all records
    flattened_records = [flatten_grant_structure(record) for record in valid_records]
    df = pd.DataFrame(flattened_records)

    # Append to existing CSV if it exists, else create new
    write_header = not os.path.exists(VALIDATED_CSV)
    df.to_csv(VALIDATED_CSV, mode="a", header=write_header, index=False, encoding="utf-8")
    logging.info(f"Saved {len(valid_records)} validated records to {VALIDATED_CSV}")

    # Save invalid records
    if invalid_records:
        invalid_path = os.path.join(DATA_DIR, f"invalid_records_{now_utc}.csv")
        df_invalid = pd.DataFrame(invalid_records)
        df_invalid.to_csv(invalid_path, mode="w", header=True, index=False)
        logging.warning(f"{len(invalid_records)} invalid records logged in {invalid_path}")


def load_processed_urls():
    """
    Load URLs that have already been successfully processed
    """
    static_csv_name = os.path.join(DATA_DIR, "validated_grants.csv")
    if not os.path.exists(static_csv_name):
        return set()

    try:
        df = pd.read_csv(static_csv_name, usecols=["sourceURL"], dtype={'sourceURL': str})
        return set(df["sourceURL"].dropna().tolist())
    except Exception as e:
        logging.error(f"Error loading processed URLs: {e}")
        return set()


def run_pipeline():
    """
    Full end-to-end process with new schema structure
    """
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

        # Extract raw JSON from Gemini
        raw = extract_from_gemini(url)
        if not raw:
            all_invalid.append({"source_url": url, "error": "Gemini extraction failed"})
            continue

        # Parse + validate
        valid, invalid = parse_and_validate(raw, url)

        # Aggregate results
        all_valid.extend(valid)
        all_invalid.extend(invalid)

        time.sleep(2)  # Rate limit delay

    # Split between high-quality and manual-review grants
    high_quality, manual_review = [], []

    for grant in all_valid:
        if quality_check(grant):
            high_quality.append(grant)
        else:
            manual_review.append(grant)

    # Save results
    save_to_csv(high_quality, all_invalid)

    if manual_review:
        review_path = os.path.join(DATA_DIR, f"manual_review_{now_utc}.csv")
        flattened_review = [flatten_grant_structure(r) for r in manual_review]
        df_review = pd.DataFrame(flattened_review)
        df_review.to_csv(review_path, mode="w", header=True, index=False, encoding="utf-8")
        logging.warning(f"{len(manual_review)} records moved to manual review at {review_path}")

    logging.info("=== Extraction Complete ===")
    logging.info(f"Total URLs processed: {total - len(processed)}")
    logging.info(f"Valid grants: {len(all_valid)}")
    logging.info(f"High quality: {len(high_quality)}")
    logging.info(f"Manual review: {len(manual_review)}")
    logging.info(f"Invalid grants: {len(all_invalid)}")
    logging.info(f"Output file: {VALIDATED_CSV}")


if __name__ == "__main__":
    run_pipeline()