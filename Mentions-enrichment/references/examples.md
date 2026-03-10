# Example Usage Sessions

## Basic Enrichment Session

```
User: I have a CSV export from Mention.com with companies. Can you enrich them with domains for Apollo?

Claude: I'll use the mentions-enrichment skill to process your CSV and enrich the companies with website domains.

[Reads CSV file]
[Runs dry-run analysis]

Mentions Enrichment - Dry Run Complete
======================================

Source file: mentions_export.csv
Tracking source: ow.ly mentions
Master file: master/owly_mentions_master.csv (959 existing entries)

Input Analysis:
- Total rows: 5,869
- After deduplication: 2,809 unique companies
- After reach filter (≥10,000): 847 companies
- Already in master: 312 (will be skipped)
- New companies to enrich: 535

Cost Estimate:
- Queries: 535
- Estimated cost: $0.32 (535 × $0.0006)
- DataForSEO balance: $49.40 ✓

Top 10 new companies by reach:
1. Business Today - 1,500,000 reach (US)
2. Tech Innovation Corp - 890,000 reach (UK)
3. Global Solutions Inc - 750,000 reach (CA)
4. Digital Media Group - 680,000 reach (US)
5. Future Systems Ltd - 620,000 reach (UK)
6. Enterprise Solutions - 580,000 reach (US)
7. Smart Technologies - 540,000 reach (DE)
8. Cloud Services Pro - 510,000 reach (US)
9. Data Analytics Inc - 490,000 reach (CA)
10. Innovation Labs - 470,000 reach (US)

Proceed with enrichment?

User: yes

Claude: [Executes enrichment...]

Enrichment Complete ✓
=====================
Processing time: 3m 42s

Results:
- Successful enrichments: 512 (95.7%)
- Failed enrichments: 23 (4.3%)
- Total cost: $0.32

Output files created:
📄 Apollo import CSV: generated-outputs/owly_mentions-2026-01-27/apollo_import_2026-01-27.csv
   (512 companies ready for Apollo.io import)

📄 Detailed log: generated-outputs/owly_mentions-2026-01-27/enrichment_log.txt

📄 Run summary: generated-outputs/owly_mentions-2026-01-27/run_summary.txt

Master file updated:
📊 master/owly_mentions_master.csv (1,494 total entries, +535 new)

You can now import the apollo_import_2026-01-27.csv file directly into Apollo.io.
```

## Custom Threshold Session

```
User: Enrich this mentions CSV but only include companies with reach over 50,000

Claude: I'll process the CSV with a custom reach threshold of 50,000.

[Runs script with --threshold 50000]

Mentions Enrichment - Dry Run Complete
======================================

Source file: high_reach_mentions.csv
Tracking source: competitor brand tracking
Master file: master/competitor_brand_tracking_master.csv (245 existing entries)

Input Analysis:
- Total rows: 3,200
- After deduplication: 1,850 unique companies
- After reach filter (≥50,000): 287 companies
- Already in master: 89 (will be skipped)
- New companies to enrich: 198

Cost Estimate:
- Queries: 198
- Estimated cost: $0.12 (198 × $0.0006)
- DataForSEO balance: $49.40 ✓

Proceed with enrichment?

User: yes

Claude: [Executes enrichment...]

Enrichment Complete ✓
=====================
Results:
- Successful enrichments: 191 (96.5%)
- Failed enrichments: 7 (3.5%)
- Total cost: $0.12

Output: generated-outputs/competitor_brand_tracking-2026-01-27/apollo_import_2026-01-27.csv
```

## No New Companies Session

```
User: Enrich this mentions export

Claude: [Analyzes CSV]

Mentions Enrichment - Analysis Complete
========================================

Source file: recent_mentions.csv
Tracking source: ow.ly mentions
Master file: master/owly_mentions_master.csv (1,494 existing entries)

Input Analysis:
- Total rows: 892
- After deduplication: 420 unique companies
- After reach filter (≥10,000): 156 companies
- Already in master: 156 (all companies already enriched)
- New companies to enrich: 0

✓ All companies have already been enriched. No API calls needed.

You can find previously enriched data in master/owly_mentions_master.csv
```

## Insufficient Balance Warning

```
User: Enrich this large mentions export

Claude: [Runs dry-run analysis]

Mentions Enrichment - Dry Run Complete
======================================

Source file: large_export.csv
Tracking source: product mentions
Master file: master/product_mentions_master.csv (150 existing entries)

Input Analysis:
- Total rows: 12,450
- After deduplication: 8,300 unique companies
- After reach filter (≥10,000): 2,150 companies
- Already in master: 85 (will be skipped)
- New companies to enrich: 2,065

Cost Estimate:
- Queries: 2,065
- Estimated cost: $1.24 (2,065 × $0.0006)
- DataForSEO balance: $0.85 ⚠️

WARNING: Estimated cost ($1.24) exceeds current DataForSEO balance ($0.85)
The enrichment may fail partway through when balance runs out.

Options:
1. Add funds to DataForSEO account
2. Proceed anyway (will enrich until balance exhausted)
3. Cancel and split into smaller batches

How would you like to proceed?
```

## First-Time Source Session

```
User: Process this new competitor tracking CSV

Claude: [Analyzes CSV]

Mentions Enrichment - Dry Run Complete
======================================

Source file: new_competitor_data.csv
Tracking source: competitor brand x
Master file: master/competitor_brand_x_master.csv (NEW - will be created)

This is the first enrichment for this tracking source.

Input Analysis:
- Total rows: 1,200
- After deduplication: 890 unique companies
- After reach filter (≥10,000): 340 companies
- Already in master: 0 (new source)
- New companies to enrich: 340

Cost Estimate:
- Queries: 340
- Estimated cost: $0.20 (340 × $0.0006)
- DataForSEO balance: $49.40 ✓

Proceed with enrichment?

User: yes

Claude: [Executes enrichment and creates new master file]

Enrichment Complete ✓
=====================
Results:
- Successful enrichments: 327 (96.2%)
- Failed enrichments: 13 (3.8%)
- Total cost: $0.20

New master file created:
📊 master/competitor_brand_x_master.csv (340 entries)

Output: generated-outputs/competitor_brand_x-2026-01-27/apollo_import_2026-01-27.csv
```

## Manual Source Override

```
User: Enrich this CSV and track it as "product launch mentions"

Claude: I'll process the CSV with the custom source name "product launch mentions"

[Runs script with --source "product launch mentions"]

Mentions Enrichment - Dry Run Complete
======================================

Source file: user_provided.csv
Tracking source: product launch mentions (manual override)
Master file: master/product_launch_mentions_master.csv (NEW - will be created)

Input Analysis:
- Total rows: 450
- After deduplication: 380 unique companies
- After reach filter (≥10,000): 125 companies
- Already in master: 0 (new source)
- New companies to enrich: 125

[... continues as normal ...]
```
