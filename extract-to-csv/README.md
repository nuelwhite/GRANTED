# V1.5 - Legacy Extraction Pipeline

**Status**: 🔴 Superseded  
**Date**: October 2025

## Overview

This was an intermediate version of the grant extraction pipeline that used a flat schema structure.

## Why It Was Superseded

Version 2 (extract-to-csv-model2) introduced:

- **Nested Schema**: Properly structured data matching the GRANTED database (eligibility, funding, deadlines, documentation, compliance, contact, category)
- **Smart Enum Mapping**: Automatic conversion of 100+ common variations
- **Quality Checks**: Automatic separation of high-quality vs manual review records
- **Better Validation**: Comprehensive Pydantic validation with detailed error messages
- **Improved Logging**: Detailed audit trails and debugging information

## Original Schema

This version used a flat schema with these fields:

```python
- grant_id
- title
- description
- funder
- funder_type
- funding_type
- amount_min
- amount_max
- currency
- deadline
- application_complexity
- eligible_provinces (list)
- geography_details
- eligible_applicant_type (list)
- eligible_industries (list)
- target_beneficiaries (list)
- supported_project_types (list)
- sdg_alignment (list)
- application_url
- is_recurring
- notes
- application_questions_link
- application_package_link
```

## Key Limitations

1. **No nested structure**: All fields were at the root level
2. **Limited validation**: Basic type checking only
3. **No enum mapping**: Raw values from extraction
4. **No quality checks**: All records treated equally
5. **Basic error handling**: Limited retry and recovery logic

## Migration to V2

If you have data from this version:

1. The core fields map directly to V2's structure
2. List fields need to be reorganized into nested objects
3. Enum values may need manual mapping
4. Quality checks should be applied to existing data

## Current Version

**For all new development**, use:

👉 **[extract-to-csv-model2](../extract-to-csv-model2/)**

**[View V2 Documentation](../extract-to-csv-model2/README.md)**

## Files in This Directory

This directory is kept for reference only. The code may not run without modifications as dependencies and configurations have evolved.

---

**Note**: This version is no longer maintained. Do not use for production.

**Active Version**: [extract-to-csv-model2](../extract-to-csv-model2/)