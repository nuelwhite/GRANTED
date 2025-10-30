🧩 GRANTED Semi-Automated Grant Data Pipeline

Owner: Grant Data Operations Manager
Version: v1.0
Last Updated: October 2025

1. Overview

This document outlines the design and operation of GRANTED’s Semi-Automated Grant Data Pipeline.
The pipeline aims to automate the collection, validation, and delivery of public grant data from verified sources into a structured format that powers GRANTED’s grant database.

The system currently uses:

Gemini API for AI-assisted data extraction

Python + Pydantic for data validation and transformation

Google Sheets API for logging and metrics tracking

Google Drive API for data delivery

Cron jobs for basic orchestration

Email notifications for completion alerts

2. Objectives

Automate data extraction from predefined grant source URLs

Ensure data consistency and completeness against a defined schema

Track and visualize data quality and pipeline performance metrics

Store validated data in a centralized, accessible location (Google Drive)

Provide a scalable foundation for future integration with tools like Looker Studio and Great Expectations

3. Architecture Diagram

(To be drawn)
I can generate this for you visually — but conceptually:

[Scheduled Cron Job]
       │
       ▼
[Gemini API Extractor]
       │
  (Raw JSON/CSV)
       ▼
[Transformation + Validation Layer]
 (Python + Pydantic)
       │
  ├── Completeness & Quality Metrics ───► [Google Sheet: Metrics Dashboard]
  │
  ├── Extraction Logs ─────────────────► [Google Sheet: Extraction Log]
  │
  ▼
[Validated Clean Data]
 (Local / Cloud Folder)
       │
       ▼
[Google Drive Upload (API)]
       │
       ▼
[Email Notification → Team]

4. Pipeline Stages
Stage 1: Extraction

Goal: Retrieve raw structured data from public grant sources.

Process:

Cron job triggers the extraction script.

Gemini API scrapes data from URLs defined in sources_list.json.

Extracted data is stored as raw CSV or JSON files in /data/raw/.

Extraction metadata (timestamp, source, records, status) is logged to Google Sheet: “Extraction Log”.

Deliverables:

/data/raw/{source_name}_{date}.csv

Extraction log entry in Google Sheet

Stage 2: Transformation & Validation

Goal: Clean and validate raw data against the predefined schema.

Tools: Python, Pandas, Pydantic

Process:

Load raw data file into a Pandas DataFrame.

Apply schema validation using Pydantic models (checking for required fields, data types, and formatting).

Flag or drop incomplete or invalid rows.

Standardize key fields:

Dates → ISO 8601 (YYYY-MM-DD)

Currency → Standardized to USD or CAD (depending on rules)

Funder names → Title case, trimmed

Compute data quality metrics (e.g., percentage completeness per column).

Append metrics to Google Sheet: “Data Quality Metrics”.

Deliverables:

/data/clean/{source_name}_{date}_validated.csv

Updated metrics dashboard in Google Sheets

Stage 3: Load

Goal: Save validated data for downstream use and visibility.

Process:

Upload validated CSV file to a dedicated Google Drive folder /Final Data/{YYYY-MM-DD}/.

Add metadata (source, timestamp, record count, completeness score).

Send automated email notification to the data operations mailing list summarizing:

Source processed

Records count

Completeness score

Link to Drive file

Stage 4: Monitoring & Reporting

Goal: Provide visibility into pipeline performance and data quality.

Implementation:

Google Sheet Dashboards: Interactive summary of extraction logs and quality metrics.

Looker Studio (Optional): Connect to Google Sheets for visual analytics (data completeness, error rates, timeliness).

Weekly Summary (Future Phase): Automated weekly email summary of pipeline performance metrics.

5. Schema Reference
Field Name	Description	Required	Example
grant_id	Unique identifier	✅	GRT2025_001
title	Grant title	✅	Women in Tech Innovation Grant
funder	Funding organization	✅	Government of Canada
funding_type	Category of funding	✅	Grant
amount_min	Minimum amount		10000
amount_max	Maximum amount		50000
currency	Currency code	✅	CAD
deadline	Application deadline	✅	2025-12-31
eligible_provinces	Geographic eligibility		Ontario; Quebec
eligible_applicant_type	Applicant type		Small Business
target_beneficiaries	Beneficiary group		Women-Owned Businesses
application_url	Application link	✅	https://example.com/apply
6. Scheduling
Task	Frequency	Method
Data Extraction	Daily	Cron (0 6 * * *)
Transformation & Validation	After extraction	Script trigger
Google Drive Upload	After validation	Script trigger
Email Notification	On completion	SMTP/Google Mail API
7. Notifications

Recipients: Grant Data Ops team (can expand later).
Contents:

Batch ID

Source name

Records processed

Completeness score

Errors detected

Links to:

Extraction Log Sheet

Quality Metrics Sheet

Final CSV on Drive
