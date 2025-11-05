import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import logging



load_dotenv


def send_notification(success_count, fail_count, csv_path, log_path):
    
    sender = os.getenv("EMAIL_SENDER")
    recipient = os.getenv("EMAIL_RECIPIENT")
    password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not all([sender, recipient, password]):
        logging.warning("Email credentials not set — skipping email")
        return

    subject = f"Grant Validation Completed — {success_count} Success, {fail_count} Failed"
    body = f"Successful: {success_count}\nFailed: {fail_count}\nOutput: {csv_path}\nLog: {log_path}\n"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Try STARTTLS first, fallback to SSL
    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.ehlo()
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        logging.info(f"Email sent to {recipient} via STARTTLS")
        return
    except Exception as e1:
        logging.warning(f"STARTTLS failed: {e1}. Trying SSL on port 465...")
        try:
            server = smtplib.SMTP_SSL(smtp_server, 465, timeout=30)
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            logging.info(f"Email sent to {recipient} via SSL")
            return
        except Exception as e2:
            logging.error(f"Failed to send email by SSL as well: {e2}")
            # do not raise — we don't want the pipeline to fail on email send
            return