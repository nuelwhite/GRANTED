import json 
import os
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. Define the Pydantic Schema for Structured Output ---
# This ensures the model returns VALID JSON that strictly follows this structure.
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


# --- 2. Setup and Source Loading ---

# load environment variables
load_dotenv()

# load api key
api_key = os.getenv("GEMINI_API_KEY")

# configure gemini
client = genai.Client(api_key=api_key)

# Handle gracefully if API does not exist
if not api_key:
    raise ValueError("No GEMINI AI API key found in the .env file")

# load sources file
SOURCES_FILE = 'semi-auto-system\config\sources_list.json'

try:
    with open(SOURCES_FILE, 'r') as f:
        sources = json.load(f).get('sources', [])
except FileNotFoundError:
    print(f"Error: Could not find sources file at {SOURCES_FILE}")
    sources = []

print(f'loaded {len(sources)} sources.')
print(f'first source: {sources[0] if sources else None}')

if not sources:
    raise ValueError("No sources found in sources_list.json or failed to load.")

# select a source
url = sources[0]
print(f"using data source {url}")


# --- 3. Prompt and API Call (Using Structured Output) ---

prompt = f"""
    You are a data extraction assistant for a grant management platform.
    Extract all required grant-related information from the following page:
    {url}
    
    Ensure amounts are converted to the smallest currency unit (e.g., CENTS if currency is USD/CAD).
    Populate all fields with the best available data. If data is unavailable, use default/empty values like None for Optionals, or empty lists for List fields.
    """


# make the request to gemini with the Structured Output configuration
print("\nMaking request to Gemini model...")
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=genai.types.GenerateContentConfig(
        response_mime_type="application/json", # Enforce JSON output
        response_schema=GrantData,          # Use the Pydantic model for schema
    ),
)


# --- 4. Processing and Saving the Response ---

raw_text = response.text.strip()
print("First 300 characters of raw text response:\n", raw_text[:300], "...\n")

# Safely parse JSON (this should now succeed consistently)
try:
    data = json.loads(raw_text)
    print("\nSuccessfully Parsed JSON Output:\n")
    print(json.dumps(data, indent=2))
except json.JSONDecodeError as e:
    # This block is now a fallback, primarily for debugging model failures if they occur
    print("could not parse response as json", e)
    print("Raw text causing error:", raw_text)


# Save response file (FIXED: os.makedirs ensures the directory exists)
os.makedirs("data/raw", exist_ok=True) 
with open("data/raw/sample_response.txt", "w", encoding="utf-8") as f:
    f.write(raw_text)
    print("\nSaved raw response to data/raw/sample_response.txt")

# The grant data is also available as a Pydantic object for direct use in Python:
parsed_grant: GrantData = response.parsed
print(f"\nTitle: {parsed_grant.title}")