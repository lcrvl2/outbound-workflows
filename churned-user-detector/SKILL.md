---
name: churned-user-detector
description: >
  Detect job changes among churned SaaS users to build win-back campaigns. Takes CSV export of removed users,
  enriches LinkedIn URLs, scrapes profiles, classifies job changes, validates emails, and pushes to Apollo.
  Use when: (1) Processing churned/removed users to find job changers, (2) Building re-engagement campaigns
  for former users at new companies, (3) User mentions "churned users", "job changers", "churn detection",
  or "win-back pipeline". Orchestrates Python pipeline scripts for LinkedIn enrichment (Apollo + DataForSEO),
  Apify scraping, classification, email validation, and Apollo push. Requires --source flag for tracking.
---

# Churned User Detector

Detect job changes among churned SaaS users to build win-back outbound campaigns.

## Pipeline

```
Input CSV (removed users export)
  -> Load & dedup against master
    -> Enrich LinkedIn URLs (Apollo email match + Google fallback)
      -> Scrape LinkedIn profiles (Apify, parallelized batches)
        -> Verify profile (old_company in experience for Google-sourced URLs)
          -> Classify (job_changer / still_there / competitor / no_current_role)
            -> Filter by title relevance (qualified vs unqualified)
              -> Email validation for still_there (Apollo status + SMTP)
                -> Output CSVs
                  -> Push to Apollo (update company/title + add to enriched list)
                    -> apollo-job-changer-processor Phase 2 picks up for Salesforce
```

## Quick Start

```bash
# Full pipeline
python scripts/run_pipeline.py --source agorapulse_churned_feb25 --csv removed_users.csv

# Recurring weekly run (auto-confirm)
python scripts/run_pipeline.py --source agorapulse_weekly_w07 --csv weekly_export.csv --yes

# Skip CSV loading (already have JSON)
python scripts/run_pipeline.py --source agorapulse_churned_feb25 --skip-load --input-users users.json

# Detection only, skip Apollo push
python scripts/run_pipeline.py --source agorapulse_churned_feb25 --csv export.csv --skip-apollo

# Skip email validation
python scripts/run_pipeline.py --source agorapulse_churned_feb25 --csv export.csv --skip-email-check --yes
```

## Pipeline Options

| Flag | Description | Default |
|------|-------------|---------|
| `--source NAME` | Source name for master file tracking | Required |
| `--csv PATH` | Input CSV with removed users | Required |
| `--col-name COL` | Column name for user name | Auto-detect |
| `--col-email COL` | Column name for email | Auto-detect |
| `--col-company COL` | Column name for company | Auto-detect |
| `--col-mrr COL` | Column name for MRR | Auto-detect |
| `--col-country COL` | Column name for country | Auto-detect |
| `--col-plan COL` | Column name for plan | Auto-detect |
| `--max-concurrent-batches N` | Parallel Apify batches | 3 |
| `--skip-email-check` | Skip SMTP email validation | Off |
| `--skip-load` | Skip CSV parsing, use `--input-users` | Off |
| `--skip-apollo` | Skip Apollo push (detection only) | Off |
| `--input-users PATH` | Path to removed_users.json | None |
| `--list-id ID` | Apollo list ID for enriched list | Built-in default |
| `--yes` | Skip all confirmation prompts | Off |

## Output Files

| File | Description | Use |
|------|-------------|-----|
| `job_changers.csv` | Qualified job changers with relevant titles | BDR-ready, Salesforce campaign import |
| `job_changers_unqualified.csv` | Job changers with irrelevant titles | Review / discard |
| `in_between_jobs.csv` | Bounced email or no current LinkedIn role | Follow up later |
| `detection_failures.csv` | No LinkedIn found, wrong profile, competitor | Debug / audit |

## Detection Logic

### Phase A: LinkedIn URL Enrichment
- **Tier 1**: Apollo `people/match` by email (most reliable)
- **Tier 2**: Apollo `people/match` by name + company
- **Tier 3**: Google search `site:linkedin.com/in` via DataForSEO SERP API

### Phase B: LinkedIn Profile Scraping
- Apify `harvestapi~linkedin-profile-scraper`, batches of 25
- Up to N concurrent batches (default 3)
- Locale URLs (fr.linkedin.com, etc.) normalized before scraping

### Phase C: Classification
1. **Profile verification** (Google-sourced URLs only): check that old_company appears in LinkedIn experience history. Apollo email_match profiles skip this check.
2. **Current position extraction**: first experience with no end date / "present"
3. **Company matching**: fuzzy match (normalize + substring) against old_company
4. **Competitor filter**: exclude people who moved to a competitor (loaded from `references/competitors.txt`)
5. **Title relevance filter**: split qualified (marketing/social/content roles) vs unqualified

### Phase D: Email Validation (still_there users)
- Apollo email status: `unavailable`/`bounced` -> in_between_jobs
- SMTP handshake: MX lookup + RCPT TO check -> if mailbox gone -> in_between_jobs
- Catch-all/personal domains skipped

### Phase E: Push to Apollo
- For each qualified job changer in `job_changers.csv`:
  1. Find contact in Apollo by email (`people/match`)
  2. Update `organization_name` + `title` with LinkedIn-detected data
  3. Add to enriched list (same list used by `apollo-job-changer-processor`)
- Deduped against push master file to prevent re-processing
- The enriched list is then picked up by `apollo-job-changer-processor` Phase 2 (filter verified → push to Salesforce → add to campaign)

## References

- **Competitor exclusion**: See [references/competitors.txt](references/competitors.txt) for auto-excluded domains (symlink to reverse-champions)

## Folder Structure

| Folder | Purpose | Lifecycle |
|--------|---------|-----------|
| `master/` | Track all processed emails per source. Prevents re-processing. | **Permanent** |
| `generated-outputs/` | Per-run output directory with dated subfolder. Contains CSVs. | **Permanent** (one folder per run) |
| `references/` | Competitor list for filtering. | **Permanent** |

## Configuration

Set API keys in `.env` (symlinked from reverse-champions):

```
APOLLO_API_KEY=your_apollo_api_key
APIFY_TOKEN=your_apify_token
DATAFORSEO_USERNAME=your_username    # optional, enables Google fallback
DATAFORSEO_PASSWORD=your_password    # optional
```

Optional: `pip install dnspython` for SMTP email validation in Phase D.

## Cost & Time Estimates

| Volume | Time | Cost |
|--------|------|------|
| 1,000 users | ~40 min | ~$4.50 (Apify) |
| 100 users (weekly) | ~8 min | ~$0.45 |
| 50 users (test) | ~5 min | ~$0.20 |
