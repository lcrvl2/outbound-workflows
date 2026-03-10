---
name: mentions-enrichment
description: >
  Multi-competitor weekly pipeline: fetch brand mentions from Mention.com, enrich company domains via DataForSEO, import to Apollo.io with employee/CRM filters. Tracks 4 competitors (Hootsuite, Sprinklr, Buffer, Brandwatch) with isolated data per competitor. Use when: (1) Running weekly mentions pipeline for a competitor, (2) User says "run mentions", "enrich mentions", "run Hootsuite/Sprinklr/Buffer/Brandwatch pipeline", (3) Testing or debugging a competitor's pipeline run, (4) Setting up cron jobs or configuring alert IDs. Skill directory: Outbound/Mentions-enrichment/
---

# Mentions Enrichment

4-competitor weekly pipeline. Each competitor runs independently with its own data directory.

## Competitors & Alert IDs

| Competitor | Alert ID | Short link | Cron schedule |
|------------|----------|------------|---------------|
| Hootsuite  | 2718028  | ow.ly      | Mon 7:00 AM   |
| Sprinklr   | 2718708  | spr.ly     | Mon 7:15 AM   |
| Buffer     | 2718710  | buff.ly    | Mon 7:30 AM   |
| Brandwatch | 2718709  | brnw.ch    | Mon 7:45 AM   |

## Folder Structure

```
Mentions-enrichment/
├── scripts/               # Shared Python scripts (all competitors)
│   ├── run_pipeline.py    # Orchestrator
│   ├── fetch_mentions.py  # Step 1: Mention.com API
│   ├── enrich_mentions.py # Step 2: DataForSEO enrichment
│   ├── apollo_pipeline.py # Step 3: Apollo import + filter
│   └── generate_unqualified.py  # Post-run: companies with reach that didn't pass filters
├── cron/                  # Weekly cron scripts (1 per competitor)
│   ├── run_hootsuite.sh
│   ├── run_sprinklr.sh
│   ├── run_buffer.sh
│   └── run_brandwatch.sh
└── data/
    └── [competitor]/      # e.g. data/hootsuite/
        ├── master/        [competitor]_master.csv        ← all enriched (permanent, append-only)
        ├── apollo-accounts/ [competitor]_apollo.csv      ← qualified accounts for outreach (overwritten each run)
        ├── unqualified/   [competitor]_unqualified_YYYY-MM-DD.csv  ← had reach but didn't pass filters
        └── generated-outputs/  ← temp artifacts (auto-deleted after run)
```

## Running a Pipeline

### Via cron script (standard)
```bash
cd Mentions-enrichment
./cron/run_hootsuite.sh   # or run_sprinklr.sh, run_buffer.sh, run_brandwatch.sh
```

### Via Python directly
```bash
python3 scripts/run_pipeline.py \
  --alert-id 2718708 \
  --source sprinklr \
  --data-dir data/sprinklr/ \
  --since-date 2026-02-10 \
  --threshold 10000 \
  --min-employees 200
```

### Key flags

| Flag | Default | Notes |
|------|---------|-------|
| `--alert-id` | required | Mention.com alert ID |
| `--source` | required | competitor name (hootsuite, sprinklr, buffer, brandwatch) |
| `--data-dir` | required | e.g. `data/sprinklr/` |
| `--since-date` | all history | YYYY-MM-DD, typically 7 days ago |
| `--threshold` | 10000 | Min cumulative reach to enrich |
| `--min-employees` | 200 | Apollo filter |
| `--yes` | off | Skip confirmations — **never use unless user explicitly requests** |
| `--skip-fetch` + `--input-csv` | — | Resume from existing CSV |
| `--skip-apollo` | off | Enrichment only, no Apollo import |
| `--no-cleanup` | off | Keep generated-outputs after run |

## Pipeline Steps

1. **Fetch** — Mention.com API → `generated-outputs/[source]-[date]/mentions_export_*.csv`
2. **Enrich** — Dedupe new mentions vs master → DataForSEO domain lookup → dry-run preview → user confirmation → append to master
3. **Apollo** — Bulk create accounts → enrich via org API → search with employee filters → overwrite apollo-accounts file
4. **Unqualified** — `master - apollo-accounts` → dated unqualified file (companies with reach that didn't pass filters)
5. **Cleanup** — Delete generated-outputs

### Cost
- DataForSEO: $0.0006/company. Dry-run always shows exact count + cost before any API call.
- Apollo & Mention.com: no per-call cost (subscription/credits)

## 3-File System Per Competitor

| File | Updated how | Purpose |
|------|-------------|---------|
| `master/[c]_master.csv` | Append each run | All enriched companies ever. **Prevents re-enrichment** (real deduplication). |
| `apollo-accounts/[c]_apollo.csv` | Overwritten each run | Companies filtered by Apollo (>200 emp, not current client) — **ready for outreach** |
| `unqualified/[c]_unqualified_DATE.csv` | New file each run | Had reach but didn't pass Apollo filters (too small, current client, etc.) — kept for manual review |

### How deduplication actually works
- **Real dedupe = Step 2 (enrich_mentions.py)**: Before any DataForSEO call, new mentions are checked against the master file. Companies already in master are skipped — no re-enrichment, no re-cost.
- **apollo-accounts** = the outreach deliverable. Companies that passed Apollo org enrichment with >200 employees and are not current clients.
- **unqualified** = the reject pile. Enriched companies that didn't meet criteria (e.g. <200 employees). Kept for later manual review, not for immediate outreach.

## Apollo Pipeline Details (Step 3)

The Apollo step uses 2 API calls in sequence:
1. **Bulk create accounts** (`POST /api/v1/accounts/bulk_create`) — imports all enriched companies into Apollo
2. **Org enrichment** (`POST /api/v1/organizations/enrich`) — enriches each domain with real employee count, industry, etc.
3. **Search + filter** (`POST /api/v1/mixed_companies/search`) — queries Apollo for accounts matching employee ranges + excluding "Current Client" stage

Matching between master (source_name from Mention.com) and apollo-accounts uses **domain-based normalization** (strips protocol/www/trailing slash) since company names from Mention.com (e.g. "SamsungFrance") often differ from Apollo org names (e.g. "Samsung Electronics").

### Apollo Filters Applied

1. `organization_num_employees_ranges`: `["201-500", "501-1000", "1001-2000", "2001-5000", "5001-10000", "10001+"]`
2. Exclude "Current Client" account stage (fetched dynamically from Apollo)

## Post-run: Generate Unqualified File

After each pipeline run, generate the unqualified file manually:

```bash
python3 scripts/generate_unqualified.py \
  --source sprinklr \
  --data-dir data/sprinklr/
```

This is also called automatically by the cron scripts with `--yes`.

## Installing Crontab

```bash
crontab -e
# Add:
0 7 * * 1  cd Mentions-enrichment && ./cron/run_hootsuite.sh >> logs/hootsuite.log 2>&1
15 7 * * 1  cd Mentions-enrichment && ./cron/run_sprinklr.sh >> logs/sprinklr.log 2>&1
30 7 * * 1  cd Mentions-enrichment && ./cron/run_buffer.sh >> logs/buffer.log 2>&1
45 7 * * 1  cd Mentions-enrichment && ./cron/run_brandwatch.sh >> logs/brandwatch.log 2>&1
```

## Agent Rules

- **Never use `--yes`** unless user explicitly requests auto-confirmation
- Dry-run preview is mandatory before any DataForSEO calls
- The `--source` name must match the competitor's data directory (e.g. `sprinklr` → `data/sprinklr/`)
- First run for new competitors (sprinklr/buffer/brandwatch) starts from empty master files — cost may be higher
- **apollo-accounts = outreach list** (passed all filters, ready to sequence)
- **unqualified = rejects for review** (had reach but <200 employees or current client)
- Domain matching is used for master vs apollo-accounts comparison — Mention.com source names don't match Apollo org names
