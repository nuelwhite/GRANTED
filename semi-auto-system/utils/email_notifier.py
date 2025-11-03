import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv


load_dotenv


def send_notification(success_count, fail_count, csv_path, log_path):
    
    sender = os.getenv("EMAIL_SENDER")
    recipient = os.getenv("EMAIL_RECIPIENT")
    password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "stmp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not all([sender, recipient, password]):
        print("Email credentials not set in .env - skipping email notification...")
        return

    subject = f"Grant Data Extraction Completed"
    body = f"""
    Hello,

    Grant data extraction pipeline completed successfully.

    Successful URLs processed: {success_count}
    Failed process: {fail_count}

    Output File: {csv_path}
    Log File: {log_path} 
    
    """

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            print(f"Email notification sent to {recipient}")
    except Exception as e:
        print(f"Failed to send email: {e}")
