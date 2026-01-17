# Grant Extraction Pipeline

Automated pipeline for extracting and standardizing grant data for the GRANTED platform.

## Current Version: V2 (extract-to-csv-model2)

**Active Development**: `extract-to-csv-model2/`

This is the production-ready version that extracts grant data from URLs and outputs CSV files matching the GRANTED database schema.

📖 **[View Full Documentation](extract-to-csv-model2/README.md)**

### Quick Start
```bash
cd extract-to-csv-model2
pip install -r requirements.txt
# Add your GEMINI_API_KEY to .env file
python extract_grants_to_csv.py
```

### Features
- ✅ Automated web scraping using Gemini AI
- ✅ Smart enum mapping (100+ variations)
- ✅ Data validation against GRANTED schema
- ✅ Quality checks with auto/manual review separation
- ✅ Duplicate prevention
- ✅ Comprehensive logging and error handling

## Version History

### V2 - extract-to-csv-model2/ (CURRENT) ⭐
**Status**: Production Ready  
**Date**: January 2026

**Key Features**:
- Nested schema support (eligibility, funding, deadlines, documentation, compliance, contact, category)
- Smart enum mapping system with 100+ common variations
- Automatic quality checks separating high-quality from manual review records
- Comprehensive logging and audit trails
- Raw response preservation for debugging

**Output**: CSV files ready for direct import into GRANTED database

[📖 Full Documentation](extract-to-csv-model2/README.md)

---

### V1.5 - extract-to-csv/ (LEGACY)
**Status**: Superseded  
**Date**: October 2025

Basic extraction pipeline with flat schema. Superseded by V2's more robust nested schema and validation system.

[View Legacy Docs](extract-to-csv/README.md)

---

### V1 - semi-auto-sys/ (ARCHIVED)
**Status**: Experimental - Not Implemented  
**Date**: October 2025

Ambitious multi-stage pipeline design with Google Drive integration, automated scheduling, and advanced monitoring. Design proved too complex for initial implementation but kept for reference and potential future enhancements.

[View Design Document](semi-auto-system/DESIGN.md)

## Repository Structure

```
grant-extraction-pipeline/
├── README.md                          # This file
├── semi-auto-sys/                     # V1 (archived design document)
│   ├── DESIGN.md                      # Original pipeline design
│   └── README.md
├── extract-to-csv/                    # V1.5 (legacy version)
│   └── README.md
└── extract-to-csv-model2/             # V2 (CURRENT - production)
    ├── README.md                      # Complete documentation
    ├── extract_grants_to_csv.py       # Main pipeline script
    ├── config/
    │   └── sources_list.json          # URLs to process
    ├── data/
    │   ├── processed/                 # Output files
    │   └── log/                       # Execution logs
    └── .env                           # API credentials (not in repo)
```

## Getting Started

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd grant-extraction-pipeline
   ```

2. **Navigate to current version**
   ```bash
   cd extract-to-csv-model2
   ```

3. **Install dependencies**
   ```bash
   pip install google-generativeai pandas python-dotenv pydantic
   ```

4. **Configure environment**
   ```bash
   # Create .env file
   echo "GEMINI_API_KEY=your_api_key_here" > .env
   ```

5. **Add source URLs**
   ```bash
   # Edit config/sources_list.json
   # Add URLs of grant pages to scrape
   ```

6. **Run pipeline**
   ```bash
   python extract_grants_to_csv.py
   ```

7. **Check outputs**
   - `data/processed/validated_grants_*.csv` - High-quality validated grants
   - `data/processed/manual_review_*.csv` - Records needing review
   - `data/log/pipeline-run_*.log` - Execution logs

## Output Data

The pipeline generates CSV files with grant data structured for the GRANTED platform:

**Core Information**: Grant ID, program name, description, funder details  
**Eligibility**: Sectors, geographies, organization types, business stages  
**Funding**: Amounts, types, requirements, expense categories  
**Deadlines**: Application dates, decision dates, reporting frequency  
**Requirements**: Documentation needs, compliance, reporting  
**Contact**: Primary contacts, application portals  

All fields are validated and enum values are automatically mapped to standardized formats.

## Support & Maintenance

### Adding New Sources
Edit `extract-to-csv-model2/config/sources_list.json`:
```json
{
  "sources": [
    "https://example.com/grant-program"
  ]
}
```

### Adding Enum Mappings
When you see "Invalid... Skipping" warnings, add mappings in `extract_grants_to_csv.py`:
```python
sector_mappings = {
    "YOUR_VARIATION": "STANDARD_ENUM",
}
```

### Troubleshooting
- Check logs in `data/log/pipeline-run_*.log`
- Review raw responses in `data/processed/*_YYYY-MM-DD.json`
- See full troubleshooting guide in [V2 Documentation](extract-to-csv-model2/README.md#troubleshooting)

## Performance

- **Average Processing**: 5-10 seconds per URL
- **Rate Limiting**: 2-second delay between URLs
- **Retry Strategy**: 3 attempts with exponential backoff
- **Token Usage**: ~2000-8000 tokens per grant

## Contributing

This is an internal tool for the GRANTED platform. For questions or issues:

1. Check the [V2 Documentation](extract-to-csv-model2/README.md)
2. Review execution logs
3. Contact the Grant Data Operations team

## License

Internal use only - GRANTED Platform

---

**Last Updated**: January 2026  
**Maintained By**: Grant Data Operations Team