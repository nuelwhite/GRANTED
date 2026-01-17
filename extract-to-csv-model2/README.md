# Grant Extraction Pipeline V2

An automated pipeline for extracting, validating, and standardizing grant program data from websites using Google's Gemini AI.

## Overview

This pipeline scrapes grant program information from URLs, validates the data against a standardized schema with proper enum mappings, and outputs clean CSV files ready for import into the GRANTED platform database.

## Features

- **Automated Web Scraping**: Extracts grant data from any URL using Gemini AI
- **Smart Enum Mapping**: Automatically maps 100+ common variations to standardized enum values
- **Data Validation**: Validates all fields against the GRANTED database schema
- **Quality Checks**: Separates high-quality records from those needing manual review
- **Duplicate Prevention**: Skips already-processed URLs automatically
- **Comprehensive Logging**: Detailed logs for debugging and audit trails
- **Raw Data Preservation**: Saves all raw API responses for reference

## Requirements

### Dependencies
```bash
pip install google-generativeai pandas python-dotenv pydantic
```

### Environment Setup
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_api_key_here
```

## Project Structure

```
extract-to-csv-model2/
├── config/
│   └── sources_list.json          # URLs to process
├── data/
│   ├── processed/                 # Output files
│   │   ├── validated_grants_*.csv # High-quality validated grants
│   │   ├── manual_review_*.csv    # Records needing review
│   │   ├── invalid_records_*.csv  # Failed validations
│   │   ├── *_YYYY-MM-DD.json     # Raw API responses
│   │   └── json_error_*.txt       # Parsing errors
│   └── log/
│       └── pipeline-run_*.log     # Execution logs
├── extract_grants_to_csv.py       # Main pipeline script
├── .env                           # API credentials (not in git)
└── README.md                      # This file
```

## Configuration

### Adding Sources

Edit `config/sources_list.json`:
```json
{
  "sources": [
    "https://example.com/grant-program-1",
    "https://example.com/grant-program-2"
  ]
}
```

### Model Settings

In `extract_grants_to_csv.py`:
```python
MODEL_NAME = "gemini-2.5-flash"  # Gemini model to use
TEMPERATURE = 0.3                # Lower = more consistent
MAX_TOKENS = 8096                # Maximum response length
```

## Usage

### Basic Execution

```bash
python extract_grants_to_csv.py
```

### What Happens

1. **Loads Sources**: Reads URLs from `config/sources_list.json`
2. **Checks Processing Status**: Skips URLs already in `validated_grants.csv`
3. **Extracts Data**: For each new URL:
   - Calls Gemini API to extract grant data
   - Saves raw response as `{grant-name}_YYYY-MM-DD.json`
   - Validates and maps all enum values
   - Applies quality checks
4. **Generates Outputs**:
   - `validated_grants_{datetime}.csv` - High-quality records
   - `manual_review_{datetime}.csv` - Records needing review (if any)
   - `invalid_records_{datetime}.csv` - Failed validations (if any)

### Processing Multiple Batches

The pipeline maintains a master file at `data/processed/validated_grants.csv`. Each run:
- Appends new validated records to this file
- Skips URLs already present in the file
- Creates timestamped copies for each run

You can safely run the pipeline multiple times - it won't re-process existing URLs.

## Output Format

### Validated Grants CSV

The output CSV has a flattened structure with these main sections:

**Core Fields:**
- `grantID`, `programName`, `programDescription`
- `funderName`, `funderType`, `programURL`
- `currency`, `programStatus`

**Eligibility Fields:**
- `eligibleSectors` (semicolon-separated)
- `eligibleGeographies` (semicolon-separated)
- `organizationType` (semicolon-separated)
- `businessStage`, `revenueRange`, `employeeRange`
- `equityFocus` (semicolon-separated)
- `grantPurpose` (semicolon-separated)

**Funding Structure:**
- `fundingType`, `amountMin`, `amountMax`
- `matchRequired`, `matchPercentage`
- `eligibleExpenseCategories`

**Deadlines:**
- `applicationOpenDate`, `applicationCloseDate`
- `rollingDeadlineFlag`
- `reportingFrequency`

**Documentation Requirements:**
- `businessPlanRequired`, `financialStatementsRequired`
- `taxReturnsRequired`, etc.

**Contact Information:**
- `primaryContactName`, `primaryContactEmail`
- `applicationPortalURL`

See the data dictionary documentation for complete field definitions.

## Enum Mappings

The pipeline automatically maps common variations to standardized enum values:

### Sectors
- "Healthcare", "Life Sciences", "Biotech" → `HEALTH`
- "AI", "Machine Learning", "Software" → `TECHNOLOGY`
- "CleanTech", "Climate Tech" → `ENERGY`
- "Agri-food", "AgTech" → `AGRICULTURE`
- "Arts", "Culture", "Creative Industries" → `CREATIVE`
- And 50+ more mappings...

### Grant Purpose
- "R&D", "Innovation" → `RESEARCH`
- "Commercialization" → `PRODUCT_DEVELOPMENT`
- "Business Growth" → `OPERATIONAL`
- "Job Creation" → `HIRING`
- "Market Expansion" → `MARKETING`
- And 40+ more mappings...

### Equity Focus
- "Black-led", "Racialized Communities" → `BIPOC_LED`
- "Women", "Women-led" → `WOMEN_LED`
- "LGBTQ+", "LGBTQ2S+" → `LGBTQ_PLUS`
- "Indigenous_people" → `INDIGENOUS`
- And 25+ more mappings...

## Quality Checks

Records are automatically classified as:

### High Quality (Auto-approved)
- All required fields present
- Valid funding amounts
- Description ≥ 100 characters
- No generic phrases like "click here"

### Manual Review
Records moved to manual review if:
- Missing `amountMax` and `fixedAmount`
- Missing 2+ critical fields (title, description, funder, URL)
- Description < 100 characters
- Contains generic placeholders

## Troubleshooting

### Common Issues

**1. "No GEMINI API KEY found"**
```bash
# Solution: Create .env file with your API key
echo "GEMINI_API_KEY=your_key_here" > .env
```

**2. "JSON parsing error"**
- Check `data/processed/json_error_*.txt` for details
- Raw response saved in `data/processed/*_YYYY-MM-DD.json`
- The pipeline has 5 auto-fix strategies - if all fail, manual review needed

**3. "Invalid {field} value: {value}. Skipping."**
- This is a warning, not an error
- The value wasn't mapped and was excluded
- To include it, add a mapping in `validate_enum_array()` function

**4. Empty Results**
- Check if Gemini can access the URL
- Some sites block automated access
- Review raw response JSON to see what was extracted

### Adding New Enum Mappings

When you see "Invalid... Skipping" warnings for values that should be included:

1. Open `extract_grants_to_csv.py`
2. Find the `validate_enum_array()` function
3. Add mapping to appropriate dictionary:

```python
sector_mappings = {
    # Add your new mapping here
    "NEW_VARIATION": "STANDARD_ENUM",
    # Example:
    "HEALTHTECH": "HEALTH",
}
```

4. Re-run the pipeline

## Logging

### Log Levels

- **INFO**: Normal operation (URL processing, mappings, saves)
- **WARNING**: Skipped values, quality issues, retries
- **ERROR**: Failed extractions, parsing errors, missing files

### Log Locations

- **Console**: Real-time output during execution
- **File**: `data/log/pipeline-run_{datetime}.log`

### Understanding Logs

```
---- [1/5] Processing https://example.com/grant ----
Extracting from https://example.com/grant (attempt 1/3)
Raw response saved to data/processed\grant-program_2026-01-17.json
Mapped eligibleSectors value 'Healthcare' to 'HEALTH'
Invalid grantPurpose value: New Purpose. Skipping.
Saved 1 validated records to validated_grants_2026-01-17.csv
```

- `[1/5]` - Processing source 1 of 5
- `(attempt 1/3)` - First attempt (retries up to 3 times)
- `Mapped...` - Successfully converted value
- `Invalid... Skipping` - Value not recognized, excluded from output
- `Saved X records` - Number of grants extracted from this URL

## Performance

- **Average Processing Time**: 5-10 seconds per URL
- **Rate Limiting**: 2-second delay between URLs
- **Retry Strategy**: Exponential backoff (2s, 4s, 8s)
- **Token Usage**: ~2000-8000 tokens per grant (depending on complexity)

## Best Practices

1. **Start Small**: Test with 1-2 URLs before running large batches
2. **Review Mappings**: Check logs for common "Invalid... Skipping" patterns
3. **Verify Quality**: Spot-check `manual_review_*.csv` files
4. **Keep Raw Responses**: Don't delete JSON files - useful for debugging
5. **Monitor Logs**: Watch for repeated errors on specific URLs
6. **Batch Processing**: Process 20-50 URLs at a time for easier monitoring

## Data Import

After running the pipeline:

1. Review `validated_grants_{datetime}.csv`
2. Check `manual_review_{datetime}.csv` for records needing attention
3. Import validated records into GRANTED database
4. The CSV format matches the database schema exactly

## Maintenance

### Regular Tasks

- **Weekly**: Review and add new enum mappings from logs
- **Monthly**: Clean up old JSON files and error logs
- **As Needed**: Update `sources_list.json` with new URLs

### Updating the Schema

If the GRANTED database schema changes:

1. Update enum mappings in `validate_enum_array()`
2. Update field validation in `parse_and_validate()`
3. Update CSV flattening in `flatten_grant_structure()`
4. Test with sample data before production run

## Support

For issues or questions:
1. Check logs in `data/log/pipeline-run_*.log`
2. Review raw JSON responses in `data/processed/`
3. Check error details in `data/processed/json_error_*.txt`

## Version History

- **V2.0** (2026-01-17): Complete rewrite with new schema support
  - Added nested grant structure (eligibility, funding, deadlines, etc.)
  - Implemented smart enum mapping
  - Added quality checks and manual review
  - Improved error handling and logging

- **V1.0** (2024): Initial version with flat schema

## License

Internal use only - GRANTED Platform