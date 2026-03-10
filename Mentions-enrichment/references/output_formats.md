# Output Format Specifications

## Generated Files Structure

Each enrichment run creates a timestamped output folder:

```
generated-outputs/
└── [source-name]-[date]/
    ├── apollo_import_[date].csv      # Apollo.io-ready import file (success only)
    ├── enrichment_log.txt             # Detailed log of all enrichment attempts
    └── run_summary.txt                # Statistics summary for this run
```

**Example:**
```
generated-outputs/
└── owly_mentions-2026-01-27/
    ├── apollo_import_2026-01-27.csv
    ├── enrichment_log.txt
    └── run_summary.txt
```

## Apollo Import CSV Format

The `apollo_import_[date].csv` file contains only successfully enriched companies ready for Apollo.io import.

### Columns

| Column Name | Description | Example |
|-------------|-------------|---------|
| Company Name | Original company name from source CSV | "Business Today" |
| Website | Enriched website domain (without http/https) | "businesstoday.com" |
| Country | Country code from source CSV | "US" |
| Cumulative Reach | Reach value from source CSV | "1500000" |

### Format Details

- **Headers:** First row contains column names
- **Encoding:** UTF-8
- **Delimiter:** Comma (`,`)
- **Quoting:** Fields with commas are quoted
- **Only successful enrichments:** Failed lookups are excluded from this file

**Example file content:**
```csv
Company Name,Website,Country,Cumulative Reach
Business Today,businesstoday.com,US,1500000
Tech Innovation Corp,techinnovation.io,UK,890000
Global Solutions Inc,globalsolutions.com,CA,750000
```

## Master File Format

Master files are stored in the `master/` directory with naming pattern: `[source-name]_master.csv`

### Purpose

- Track all enriched companies by source
- Prevent re-enriching the same company multiple times
- Maintain historical enrichment data

### Columns

| Column Name | Description | Example |
|-------------|-------------|---------|
| Company Name | Original company name | "Business Today" |
| Website | Enriched domain (empty if enrichment failed) | "businesstoday.com" or "" |
| Country | Country code | "US" |
| Cumulative Reach | Highest reach value seen across all runs | "1500000" |
| Status | Enrichment result status | "success" or "no_domain" |
| Enriched Date | ISO format date of enrichment | "2026-01-27" |
| Normalized Name | Lowercase, no spaces version for matching | "businesstoday" |

### Status Values

- **`success`**: Domain found and enriched successfully
- **`no_domain`**: Enrichment attempted but no valid domain found

### Normalized Name Matching

Companies are matched using normalized names to prevent duplicates:
- "Business Today" → normalized: "businesstoday"
- "business today" → normalized: "businesstoday"
- "Business  Today" → normalized: "businesstoday"

This ensures variations of the same company name are treated as duplicates.

**Example master file content:**
```csv
Company Name,Website,Country,Cumulative Reach,Status,Enriched Date,Normalized Name
Business Today,businesstoday.com,US,1500000,success,2026-01-27,businesstoday
Failed Corp,,US,500000,no_domain,2026-01-27,failedcorp
Tech Solutions,techsolutions.io,UK,890000,success,2026-01-27,techsolutions
```

## Enrichment Log Format

The `enrichment_log.txt` file contains detailed information about every enrichment attempt.

### Structure

```
[TIMESTAMP] Company: [name] | Reach: [value] | Country: [code]
[TIMESTAMP] → Query: "[search query used]"
[TIMESTAMP] → Result: [outcome]
[TIMESTAMP] ✓ Domain: [domain] or ✗ Failed: [reason]
[blank line]
```

**Example:**
```
2026-01-27 14:32:15 Company: Business Today | Reach: 1500000 | Country: US
2026-01-27 14:32:15 → Query: "Business Today"
2026-01-27 14:32:16 → Result: Found 10 results, selected businesstoday.com
2026-01-27 14:32:16 ✓ Domain: businesstoday.com

2026-01-27 14:32:17 Company: Ambiguous Name | Reach: 250000 | Country: US
2026-01-27 14:32:17 → Query: "Ambiguous Name"
2026-01-27 14:32:18 → Result: All results filtered (social media)
2026-01-27 14:32:18 ✗ Failed: No valid domain found
```

## Run Summary Format

The `run_summary.txt` file contains statistics for the enrichment run.

### Structure

```
Mentions Enrichment Summary
===========================
Run Date: [ISO date]
Source: [tracking source name]
Input File: [original CSV filename]

Input Statistics:
- Total rows: [number]
- Unique companies: [number]
- After reach filter (≥[threshold]): [number]

Enrichment Results:
- Already in master: [number] (skipped)
- New companies processed: [number]
- Successful enrichments: [number] ([percentage]%)
- Failed enrichments: [number] ([percentage]%)

Cost:
- Queries made: [number]
- Estimated cost: $[amount]

Output Files:
- Apollo import: [filepath]
- Enrichment log: [filepath]
- Master file: [filepath] ([total entries] total entries)
```

**Example:**
```
Mentions Enrichment Summary
===========================
Run Date: 2026-01-27
Source: ow.ly mentions
Input File: mentions_export.csv

Input Statistics:
- Total rows: 5,869
- Unique companies: 2,809
- After reach filter (≥10,000): 847

Enrichment Results:
- Already in master: 312 (skipped)
- New companies processed: 535
- Successful enrichments: 512 (95.7%)
- Failed enrichments: 23 (4.3%)

Cost:
- Queries made: 535
- Estimated cost: $0.32

Output Files:
- Apollo import: generated-outputs/owly_mentions-2026-01-27/apollo_import_2026-01-27.csv
- Enrichment log: generated-outputs/owly_mentions-2026-01-27/enrichment_log.txt
- Master file: master/owly_mentions_master.csv (1,494 total entries)
```
