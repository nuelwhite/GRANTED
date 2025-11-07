import os
import subprocess
import logging
from datetime import datetime

# --- Setup logging ---
def setup_log():
    os.makedirs("data/logs", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = f"data/logs/pipeline_{timestamp}.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    return log_file


def run_stage(stage_name, command):
    logging.info(f"Starting stage: {stage_name}")
    try:
        subprocess.run(command, check=True)
        logging.info(f"{stage_name} completed successfully.\n")
    except subprocess.CalledProcessError as e:
        logging.error(f"{stage_name} failed with error: {e}")
        raise


def main():
    log_file = setup_log()
    logging.info("=== Starting Semi-Automated Grant Data Pipeline ===")

    stages = [
        ("Extraction", ["python", "extract_grants.py"]),
        ("Transformation + Validation", ["python", "transform_and_validate.py"]),
        ("Metrics Computation", ["python", "compute_metrics.py"]),
        ("Google Drive Upload", ["python", "utils/drive_uploader.py"]),
    ]

    for stage_name, command in stages:
        run_stage(stage_name, command)

    logging.info("All pipeline stages completed successfully.")
    logging.info(f"Logs saved to {log_file}")


if __name__ == "__main__":
    main()
