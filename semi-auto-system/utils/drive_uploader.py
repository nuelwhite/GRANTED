import os
import glob
import logging
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
flow = InstalledAppFlow.from_client_secrets_file("config/oauth_client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)
drive_service = build("drive", "v3", credentials=creds)



# setting up logging
def setup_log():
    os.makedirs("data/logs", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = f"data/logs/drive_upload_{timestamp}.log"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    return log_file


# Get latest processed files - find latest processed and metrics csvs to upload
def get_latest_files():

    clean_files = glob.glob("./data/clean/grants_clean_*.csv")
    metric_files = glob.glob("./data/metrics/validation_metrics_*.csv")

    if not clean_files:
        raise FileNotFoundError("No clean CSV file found.")
    if not metric_files:
        raise FileNotFoundError("No metrics CSV file found.")

    latest_clean = max(clean_files, key=os.path.getctime)
    latest_metric = max(metric_files, key=os.path.getctime)
    return latest_clean, latest_metric


# upload function to load file to google drive
def upload_to_drive(file_path, drive_folder_id, drive_service):

    file_name = os.path.basename(file_path)

    media = MediaFileUpload(file_path, resumable=True, mimetype="text/csv")
    file_metadata = {"name": file_name, "parents": [drive_folder_id]}

    uploaded_file = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    file_id = uploaded_file.get("id")
    logging.info(f"Uploaded '{file_name}' to Drive (file ID: {file_id})")
    return file_id


# main block
def main():
    load_dotenv()
    log_file = setup_log()
    logging.info("...Starting Google Drive Upload Phase...")

    # Prepare credentials
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    SERVICE_ACCOUNT_FILE = "config/google_service_account.json"
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build("drive", "v3", credentials=creds)

    # Locate files
    clean_path, metrics_path = get_latest_files()
    logging.info(f"Found files to upload:\n - Clean: {clean_path}\n - Metrics: {metrics_path}")

    # Get base Drive folder from .env
    parent_folder = os.getenv("GOOGLE_DRIVE_PARENT_ID")
    if not parent_folder:
        raise ValueError("Missing GOOGLE_DRIVE_PARENT_ID in .env")

    # Create subfolders for month/year
    now = datetime.utcnow()
    subfolder_name = f"{now.year}_{now.month:02d}"

    def ensure_subfolder_exists(name):
        """Check or create a subfolder under the parent folder."""
        query = f"'{parent_folder}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get("files", [])
        if items:
            return items[0]["id"]
        folder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder],
        }
        folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
        logging.info(f"Created folder '{name}' (ID: {folder['id']})")
        return folder["id"]

    # Create/locate subfolders
    clean_folder = ensure_subfolder_exists("CleanData")
    metrics_folder = ensure_subfolder_exists("Metrics")

    month_clean_folder = ensure_subfolder_exists(f"CleanData/{subfolder_name}")
    month_metrics_folder = ensure_subfolder_exists(f"Metrics/{subfolder_name}")

    # Upload files
    upload_to_drive(clean_path, month_clean_folder, drive_service)
    upload_to_drive(metrics_path, month_metrics_folder, drive_service)

    logging.info("Upload phase complete.")
    logging.info(f"Log file: {log_file}")


if __name__ == "__main__":
    main()
