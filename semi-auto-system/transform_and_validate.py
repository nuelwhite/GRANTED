import os
import glob
import pandas as pd
import logging
from dotenv import load_dotenv
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional
from utils.email_notifier import send_notification


# setup logging
def setup_log():
    os.makedirs("semi-auto-system/data/logs", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    log_file = f"semi-auto-system/data/logs/validation_logs_{timestamp}.log"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    return log_file


# --1. DEFINE SCHEMA
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

# - 2. LOAD RAW FILE
def get_raw_file():
    files = glob.glob("semi-suto-system/data/raw/grants_raw_*.csv")

    if not files:
        logging.error("No raw CSV files found in data/raw")
        raise FileNotFoundError("No Raw CSV files avaliable")

    latest = max(files, key=os.path.getctime)
    logging.info(f"Using latest raw file: {latest}")

    return latest


# --3. VALIDATION LOGIC
def validate_records(df):
    valid_records = []
    invalid_records = []

    for _, row in df.iterrows():
        record = row.to_dict()

        try:
            validated_grant = GrantData(**record)
            valid_records.append(validated_grant.model_dump())
        except ValidationError as e:
            record["validation_errors"] = str(e)
            invalid_records.append(record)
            logging.warning(f"Validation failed for record {record.get('grant_id', 'N/A')}")

    return valid_records, invalid_records



