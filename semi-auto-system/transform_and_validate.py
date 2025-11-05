import os
import glob
import pandas as pd
import logging
from dotenv import load_dotenv
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional
from utils.email_notifier import send_notification
import ast 
import math


# setup logging
def setup_log():
    os.makedirs("data/logs", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    log_file = f"data/logs/validation_logs_{timestamp}.log"

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
    files = glob.glob("data/raw/grants_raw_*.csv")

    if not files:
        logging.error("No raw CSV files found in data/raw")
        raise FileNotFoundError("No Raw CSV files avaliable")

    latest = max(files, key=os.path.getctime)
    logging.info(f"Using latest raw file: {latest}")

    return latest


# --3. VALIDATION LOGIC
def _is_nan(x):
    try:
        return isinstance(x, float) and math.isnan(x)
    except Exception:
        return False

def preprocess_row(record: dict) -> dict:
    """
    Try to coerce CSV string values into types expected by GrantData.
    - Convert "['A','B']" or '["A","B"]' to Python list via ast.literal_eval
    - Convert semicolon-separated strings "a;b" to list ["a","b"]
    - Convert numeric floats to int for amount_min/amount_max if appropriate
    - Convert NaN to None
    - Convert 'True'/'False'/'1'/'0' to bool for is_recurring
    - Strip whitespace and normalize empty strings to None where appropriate
    """
    out = dict(record)  # copy

    # Fields that should be lists
    list_fields = [
        "eligible_provinces",
        "eligible_applicant_type",
        "eligible_industries",
        "target_beneficiaries",
        "supported_project_types",
        "sdg_alignment",
    ]

    for f in list_fields:
        v = out.get(f, None)
        if v is None or _is_nan(v):
            out[f] = []
            continue
        # If already a list, keep it
        if isinstance(v, list):
            continue
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                out[f] = []
                continue
            # Try literal_eval for python list string
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, list):
                    out[f] = [str(x).strip() for x in parsed]
                    continue
            except Exception:
                pass
            # Try semicolon or comma separated
            if ";" in s:
                out[f] = [x.strip() for x in s.split(";") if x.strip()]
                continue
            if "," in s and not s.startswith("http"):
                out[f] = [x.strip() for x in s.split(",") if x.strip()]
                continue
            # fallback single value
            out[f] = [s]
            continue
        # Other types fallback to empty
        out[f] = []

    # Numeric amounts: accept floats/strings, convert to int (cents)
    for amt_field in ("amount_min", "amount_max"):
        v = out.get(amt_field, None)
        if v is None or _is_nan(v) or (isinstance(v, str) and v.strip() == ""):
            out[amt_field] = None
            continue
        try:
            # if string with currency symbols, remove non-digit
            if isinstance(v, str):
                s = v.replace(",", "").strip()
                # remove currency symbols
                s = "".join(ch for ch in s if (ch.isdigit() or ch in ".-"))
                val = float(s)
            else:
                val = float(v)
            # convert to smallest unit (assumes input was whole dollars; adjust if already cents)
            # If your extraction already outputs cents, remove the *100 below.
            out[amt_field] = int(round(val))  # keep as integer unit (assume whole units)
        except Exception:
            out[amt_field] = None

    # currency: normalize None or empty to "CAD" default if you want
    cur = out.get("currency", None)
    if cur is None or _is_nan(cur) or (isinstance(cur, str) and cur.strip() == ""):
        out["currency"] = "CAD"
    else:
        out["currency"] = str(cur).strip().upper()

    # deadline: keep as string, but convert NaN -> empty string
    d = out.get("deadline", None)
    if d is None or _is_nan(d):
        out["deadline"] = ""
    else:
        out["deadline"] = str(d).strip()

    # is_recurring: coerce to bool
    ir = out.get("is_recurring", None)
    if isinstance(ir, bool):
        out["is_recurring"] = ir
    elif ir in (1, "1", "True", "true", "TRUE", "yes", "Yes"):
        out["is_recurring"] = True
    elif ir in (0, "0", "False", "false", "FALSE", "no", "No", None):
        out["is_recurring"] = False
    else:
        out["is_recurring"] = False

    # Strings: convert NaN to empty string for required string fields
    str_fields = [
        "grant_id", "title", "description", "funder",
        "funder_type", "funding_type", "application_complexity",
        "geography_details", "application_url", "notes",
        "application_docs_raw", "application_questions_text"
    ]
    for f in str_fields:
        v = out.get(f, None)
        if v is None or _is_nan(v):
            out[f] = ""
        else:
            out[f] = str(v).strip()

    return out


def validate_records(df):
    valid_records = []
    invalid_records = []

    for idx, row in df.iterrows():
        record = row.to_dict()
        pre = preprocess_row(record)

        try:
            validated = GrantData(**pre)
            valid_records.append(validated.model_dump())
        except ValidationError as e:
            # structured errors from Pydantic
            errors = e.errors() if hasattr(e, "errors") else str(e)
            record["validation_errors"] = errors
            invalid_records.append(record)
            logging.warning(f"Validation failed for record {pre.get('grant_id', 'N/A')} - errors: {errors}")

    return valid_records, invalid_records


# --4. MAIN EXECUTION
def main():
    load_dotenv()
    os.makedirs("data/clean", exist_ok=True)
    os.makedirs("data/metrics", exist_ok=True)

    log_file = setup_log()
    logging.info("...Starting Data Transformation and Validation...")


    input_file = get_raw_file()
    df = pd.read_csv(input_file)
    logging.info(f"Validating {len(df)} records...")

    valid, invalid = validate_records(df)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    clean_path = f"data/clean/grants_clean_{timestamp}.csv"
    invalid_path = f"data/metrics/invalid_records_{timestamp}.csv"

    pd.DataFrame(valid).to_csv(clean_path, index=False)
    pd.DataFrame(invalid).to_csv(invalid_path, index=False)

    logging.info(f"Valid records: {len(valid)}")
    logging.info(f"Invalid records: {len(invalid)}")
    logging.info(f"Processed data saved to {clean_path}")
    logging.info(f"Invalid data saved to {invalid_path}")

    send_notification(
        success_count=len(valid),
        fail_count=len(invalid),
        csv_path=clean_path,
        log_path=log_file,
    )

    logging.info("Email summary sent to team.")
    logging.info("Validation phase complete.")


if __name__ == "__main__":
    main()