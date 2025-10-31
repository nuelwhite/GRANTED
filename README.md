# GRANTED Semi-Automated Grant Data Pipeline

**Created By**: Grant Data Operations Manager

**Version**: v1.0

**Last Updated**: October 2025

## Overview

This document outlines the design and operation of GRANTED’s Semi-Automated Grant Data Pipeline.
The pipeline aims to automate the collection, validation, and delivery of grant data from verified sources into a structured format that powers GRANTED’s grant database.

The system currently uses:

- Gemini API for AI-assisted data extraction

- Python + Pydantic for data validation and transformation

- Google Sheets API for logging and metrics tracking

- Google Drive API for data delivery

- Cron jobs for basic orchestration

- Email notifications for completion alerts

## Objectives

- Automate data extraction from predefined grant source URLs

- Ensure data consistency and completeness against a defined schema

- Track and visualize data quality and pipeline performance metrics

- Store validated data in a centralized, accessible location (Google Drive)

- Provide a scalable foundation for future integration with tools like Looker Studio and Great Expectations

## Architecture Diagram
```
[Scheduled Cron Job]
       │
       │
       ├── Extraction Logs ─────────────────► [Extraction Log]
       ▼
[Gemini API Extractor]
       │
  (Raw CSV)
       ▼
[Transformation + Validation Layer]
 (Python + Pydantic)
       │
       ├── Completeness & Quality Metrics ───► [Google Sheet: Metrics Dashboard]
       │
       │
       ▼
[Validated Clean Data]
       │
       ▼
[Google Drive Upload (API)]
       │
       ▼
[Email Notification → Team]
```

## Pipeline Stages

### Stage 1: Extraction

**Goal**: Retrieve raw structured data from public grant sources.

**Process**:

- Cron job triggers the extraction script `extract_grants.py`.

- Gemini API scrapes data from URLs defined in `sources_list.json`.

- Extracted data is stored as raw CSV or JSON files in `/data/raw/{source}_{date}.csv`.

- Extraction metadata (timestamp, source, records, status) is logged to “Extraction Log”.


**Deliverables**:

- /data/raw/{source_name}_{date}.csv

- Extraction log entry

### Stage 2: Transformation & Validation

**Goal**: Clean and validate raw data against the predefined schema.

**Tools**: Python, Pandas, Pydantic

**Process**:

- Load raw data file into a Pandas DataFrame.

- Apply schema validation using Pydantic models (checking for required fields, data types, and formatting).

- Flag or drop incomplete or invalid rows.

- Compute data quality metrics (e.g., percentage completeness per column).

- Append metrics to Google Sheet: “Data Quality Metrics”.

**Standardize key fields:**

- Dates → (YYYY-MM-DD)

- Currency → Standardized to USD or CAD (depending on rules)

- Funder names → Title case, trimmed


**Deliverables**:

- /data/clean/{source_name}_{date}_validated.csv

- Updated metrics dashboard in Google Sheets

### Stage 3: Load

**Goal**: Save validated data for downstream use and visibility.

**Process**:

For each grant: 
- - IF `application_docs_raw` is present → call `upload_application_package()` to:

       - Create Drive folder /packages/{grant_id}/
       - Upload extracted files
       - Return and store folder URL → `application_package_link`
- - If application_questions_text exists → call `upload_questions_doc()` to:

       - Create Google Doc
       - Insert extracted questions text
       - Return and store doc URL → `application_questions_link`

- Upload validated CSV file to a dedicated Google Drive folder /Final Data/{YYYY-MM-DD}/.

- Add metadata (source, timestamp, record count, completeness score).

- Send automated email notification to the data operations mailing list summarizing:
       
       * Source processed
       * Records count
       * Completeness score
       * Link to Drive file

### Stage 4: Monitoring & Reporting

**Goal**: Provide visibility into pipeline performance and data quality.

**Implementation**:

- Google Sheet Dashboards: Interactive summary of extraction logs and quality metrics.

- Looker Studio (Future Phase): Connect to Google Sheets for visual analytics (data completeness, error rates, timeliness).

- Weekly Summary (Future Phase): Automated weekly email summary of pipeline performance metrics.

## Schema Reference

| **Field Name** | **Data Type** | **Description** | **Required** |**Example**|
| --- | --- | --- | --- | --- |
| `grant_id` | String  | Unique identifier for the grant. | ✅  | `GOVYUKON-EDF-T1-2025`  |
| `title`    | String  | The full, official title of the grant program. | ✅ | Women in Tech Innovation Grant |
| `description` | Text | Crucial for AI. The full, detailed description from the source. The richer, the better for semantic matching.  | ✅ | Provides funding for women-led tech startups to scale innovation across Canada. |
| `funder`| String        | The name of the government body, foundation, or corporation offering the grant. | ✅ | Government of Canada                                                                  |
| `funder_type` | Enum  | *(Canadian context)* The type of funder (e.g., Federal Grant, Provincial Grant, Municipal Grant, Foundation Grant, Corporate Grant). | ✅ | Provincial Grant |
| `funding_type` | Enum | *(Canadian context)* The specific type of funding offered (e.g., Grant, Loan, Tax Credit, Contribution). | ✅ | Grant |
| `amount_min` | Integer | Minimum funding amount. |  | 10000   |
| `amount_max` | Integer       | Maximum funding amount.    | ✅    | 50000             |
| `currency`                   | Enum          | The currency of the grant (e.g., CAD, USD). Defaults to CAD.                                                                                   | ✅            | CAD                                                                                   |
| `deadline`                   | Date          | The application deadline in `YYYY-MM-DD` format. Accepts nulls for rolling or ongoing grants.                                                  |        | 2025-12-31                                                                            |
| `application_complexity`     | Enum          | User-facing rating (Low, Medium, High) reflecting time commitment required.                                                                    |              | Medium                                                                                |
| `eligible_provinces`         | Enum Array    | Multi-select list of provinces/territories for high-level filtering. Standardized for search (e.g., “Show me all grants in British Columbia”). |             | [“Ontario”, “Quebec”]                                                                 |
| `geography_details`          | String        | Optional text field for granular location details (e.g., city- or region-level restrictions).                                                  |              | Toronto or GTA region                                                                 |
| `eligible_applicant_type`    | Enum Array    | Crucial for matching. Entity types eligible to apply (supports multiple selections, e.g., both Non-Profit and Charity).                        |   ✅   | [“Small Business”, “Non-Profit”]                                                      |
| `eligible_industries`        | String Array  | Crucial for matching. Semicolon-separated list of relevant industries.                                                                         |    ✅      | software;healthcare;clean_tech                                                        |
| `target_beneficiaries`       | Enum Array    | Crucial for matching. Populations the grant aims to serve.                                                                                     |      ✅        | [“Women-Owned Businesses”, “Indigenous Entrepreneurs”]                                |
| `supported_project_types`    | String Array  | Semicolon-separated list of project focus areas the grant supports (e.g., workforce_development;R&D;community_arts).                           |              | workforce_development;R&D                                                             |
| `sdg_alignment`              | Enum Array    | Multi-select list of UN Sustainable Development Goals the grant supports.                                                                      |              | [“SDG5: Gender Equality”, “SDG9: Industry, Innovation and Infrastructure”]            |
| `application_url`            | URL           | The direct link to apply.                                                                                                                      | ✅            | [https://example.com/apply](https://example.com/apply)                                |
| `is_recurring`               | Boolean       | `TRUE` if the grant is offered annually or on a regular cycle.                                                                                 |              | TRUE                                                                                  |
| `notes`                      | Text          | Any additional context such as multi-stage processes (e.g., LOI first) or specific ineligibility criteria.                                     |              | LOI required before full application.                                                 |
| `application_questions_link` | URL           | Direct link to a Google Doc with all application questions for this specific grant.                                                            |              | [https://docs.google.com/document/d/](https://docs.google.com/document/d/)...         |
| `application_package_link`   | URL           | Direct link to a shared Google Drive folder containing the complete application package (guidelines, FAQs, forms, etc.).                       |              | [https://drive.google.com/drive/folders/](https://drive.google.com/drive/folders/)... |



## Scheduling

| Task	| Frequency |	Method |
|---|---|---|
|Data Extraction | Daily | Cron (0 6 * * *) |
| Transformation & Validation | After extraction | Script trigger |
| Google Drive Upload | After validation	| Script trigger |
| Email Notification	| On completion	| SMTP/Google Mail API |


## Notifications

Recipients: Grant Data Ops team.

Contents:

       - Batch ID
       -  Source name
       - Records processed
       - Completeness score
       - Errors detected
       - Links to:
              - Extraction Log Sheet
              - Quality Metrics Sheet
              - Final CSV on Drive

## Monitoring and Reporting

- Extraction Log Sheet: Tracks batch runs, record counts, and failures.
- Quality Metrics Sheet: Shows completeness and error rates.
- Email Notification: Summarizes each run with metrics and links

## Project Structure

```markdown
/semi-auto-sys/
│
├── extract_grants.py
├── transform_validate.py
├── load_and_notify.py
│
│
├── packages/                      # where downloaded PDFs and docs are saved
│
│
├── utils/
│   ├── drive_uploader.py          # Uploads folder/files to Google Drive
│   ├── doc_uploader.py            # Creates/updates Google Docs for questions
│   ├── sheets_logger.py           # Pushes extraction + quality metrics
│   └── email_notifier.py          # Sends completion summary email
│
└── config/
    ├── credentials.json           # Google API creds
    ├── drive_folders.yaml         # Folder IDs for raw_data, clean_data, etc.
    ├── email_recipients.yaml
    └── sources_list.json          # json file containing source urls
```