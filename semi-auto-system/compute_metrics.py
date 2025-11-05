import os
import glob
import pandas as pd
import logging
from dotenv import load_dotenv
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials


# set up logging
def setup_log():
    os.makedirs("data/logs", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = f"data/logs/metrics_{timestamp}.log"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    return log_file



def get_latest_clean_file():
    files = glob.glob("data/clean/grants_clean_*.csv")
    if not files:
        logging.error("No processed CSV files found in data/clean/")
        raise FileNotFoundError("No processed CSV files found.")
    latest = max(files, key=os.path.getctime)
    logging.info(f"Using latest processed file: {latest}")
    return latest


# metrics computing - compute dataset-level completeness and quality metrics
def compute_metrics(df):
    # Required fields
    required_fields = [
        "grant_id", "title", "description", "funder",
        "funder_type", "funding_type", "currency",
        "deadline", "application_url"
    ]

    total_records = len(df)
    total_fields = len(required_fields) * total_records
    missing_fields = sum(df[col].isna().sum() + (df[col] == "").sum() for col in required_fields)
    completeness = round(((total_fields - missing_fields) / total_fields) * 100, 2) if total_fields else 0.0

    # Distribution summaries
    currency_counts = df["currency"].value_counts().to_dict() if "currency" in df.columns else {}
    funding_type_counts = df["funding_type"].value_counts().to_dict() if "funding_type" in df.columns else {}

    # List length averages
    list_fields = [
        "eligible_provinces", "eligible_applicant_type", "eligible_industries",
        "target_beneficiaries", "supported_project_types", "sdg_alignment"
    ]
    avg_list_lengths = {}
    for field in list_fields:
        if field in df.columns:
            avg_list_lengths[field] = (
                df[field].dropna()
                .apply(lambda x: len(eval(x)) if isinstance(x, str) and x.startswith("[") else len(str(x).split(";")))
                .mean()
            )
        else:
            avg_list_lengths[field] = 0

    metrics = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": total_records,
        "missing_required_fields": int(missing_fields),
        "completeness_score": completeness,
        "currency_distribution": str(currency_counts),
        "funding_type_distribution": str(funding_type_counts),
    }
    metrics.update({f"avg_len_{k}": round(v or 0, 2) for k, v in avg_list_lengths.items()})

    logging.info(f"Computed metrics: completeness {completeness}% on {total_records} records")
    return metrics


def upload_to_google_sheets(metrics):

    load_dotenv()
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    SERVICE_ACCOUNT_FILE = "config/google_service_account.json"

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(sheet_id).sheet1

    row = [
        metrics["timestamp"],
        metrics["total_records"],
        metrics["missing_required_fields"],
        metrics["completeness_score"],
        metrics["currency_distribution"],
        metrics["funding_type_distribution"],
    ]

    sheet.append_row(row)
    logging.info(f"Metrics uploaded to Google Sheet successfully.")

# main block

def main():
    load_dotenv()
    os.makedirs("data/metrics", exist_ok=True)

    log_file = setup_log()
    logging.info("...Starting Metrics Computation Phase...")

    input_file = get_latest_clean_file()
    df = pd.read_csv(input_file)

    metrics = compute_metrics(df)

    # Save locally
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    metrics_path = f"data/metrics/validation_metrics_{timestamp}.csv"
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)
    logging.info(f"Computed metrics saved locally: {metrics_path}")

    # Upload to Google Sheets
    try:
        upload_to_google_sheets(metrics)
    except Exception as e:
        logging.error(f"Failed to upload to Google Sheets: {e}")

    logging.info("Metrics phase complete.")


if __name__ == "__main__":
    main()
