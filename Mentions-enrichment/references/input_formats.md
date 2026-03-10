# Input Format Specifications

## CSV Format Requirements

The skill auto-detects columns from various CSV export formats. The following column names are supported:

### Required Fields

| Field | Accepted Column Names |
|-------|----------------------|
| Company Name | `source_name`, `company`, `name`, `Company Name` |
| Reach | `cumulative_reach`, `reach`, `Cumulative Reach` |
| Country | `country`, `Country` |
| Source/Alert | `alert_name`, `tracking_name`, `alert` |

### Minimum Requirements

For successful processing, the CSV must contain:
- **Company name column** (required) - At least one of the accepted column names
- **Reach column** (required for filtering) - Used to filter companies by reach threshold
- **At least one company with reach ≥ 10,000** (default threshold)

### Column Detection

The script automatically detects columns by checking for recognized column names. If multiple accepted names exist for the same field, the first match found is used.

**Example valid CSV structures:**

**Mention.com export format:**
```csv
source_name,cumulative_reach,country,alert_name
Business Today,1500000,US,ow.ly mentions
Tech Corp,890000,UK,ow.ly mentions
```

**Generic format:**
```csv
Company Name,Reach,Country
Example Inc,250000,CA
Another Corp,180000,US
```

### Source Detection

The skill automatically identifies the tracking source from:
1. `alert_name` column value (preferred)
2. `tracking_name` column value
3. Manual override via `--source` parameter

The source name determines which master file is used:
- Source: "ow.ly mentions" → `master/owly_mentions_master.csv`
- Source: "competitor brand x" → `master/competitor_brand_x_master.csv`

### Reach Threshold

**Default:** 10,000

Companies below this threshold are automatically filtered out before enrichment.

**Custom threshold:**
```bash
python scripts/enrich_mentions.py input.csv --threshold 50000
```

### Common Issues

| Issue | Resolution |
|-------|-----------|
| "Could not detect company name column" | Rename column to one of the accepted names |
| "Could not detect reach column" | Add a reach/cumulative_reach column with numeric values |
| "No companies above threshold" | Lower threshold with `--threshold` flag or check data |
| Missing source/alert column | Use `--source "name"` parameter to manually specify |
