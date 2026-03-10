---
name: hiring-intel
description: >
  End-to-end pipeline to find companies hiring for social media roles, scrape job descriptions,
  extract structured intel, generate fully personalized 1:1 cold email sequences, and push to
  Apollo.io contacts with custom fields. Use when: (1) User mentions "hiring intel", "companies
  hiring", "job posting intel", or "hiring pipeline", (2) Building outbound sequences targeting
  companies actively hiring for social media roles, (3) User wants to generate personalized emails
  from job posting data, (4) User wants to enrich Apollo contacts with hiring intelligence.
  Requires a GTM playbook for email generation. NEVER use --yes flag unless the user explicitly
  requests auto-confirmation. Always identify the source name before running (check master/ for
  existing sources).
---

# Hiring Intel Skill

Turn job postings into hyper-relevant 1:1 email sequences.

## Pipeline

```
Step 1: Apollo Org Search (job title filter)
  -> Apollo Job Postings API (get posting URLs)

Step 2: Scrape job descriptions (Crawl4AI for careers pages, Apify for LinkedIn URLs)
  -> Scrape company homepages for additional context (Crawl4AI with metadata fallback)

Step 3: Claude Sonnet: extract structured intel from JDs + company context

Step 4: Claude Opus: generate 3 complete emails per company
  (uses condensed Agorapulse playbook, industry-matched case studies,
   merged intel from all postings, company website context)
  Post-generation: deterministic banned phrase validator (20 regex patterns)
  + retry loop (up to 2 retries on banned phrases or JSON parse errors)

Step 5: Push to Apollo custom fields + sequence
```

Each contact gets 3 completely unique emails written from their actual job posting data, company website context, and Agorapulse playbook.

## Quick Start

```bash
# Full pipeline
python scripts/run_pipeline.py --source weekly_feb02 --playbook /path/to/playbook.md

# With filters
python scripts/run_pipeline.py --source weekly_feb02 --playbook playbook.md \
  --min-employees 50 --max-employees 1000 --geo "United States"

# With Apollo sequence
python scripts/run_pipeline.py --source weekly_feb02 --playbook playbook.md \
  --sequence-id SEQ_ABC123
```

## Pipeline Options

| Flag | Description | Default |
|------|-------------|---------|
| `--source NAME` | Source name for master file tracking | Required |
| `--playbook PATH` | GTM playbook markdown file | Required |
| `--min-employees N` | Minimum employee count | None |
| `--max-employees N` | Maximum employee count | None |
| `--geo GEO` | Geographic filter | All |
| `--max-pages N` | Max search pages per keyword | 5 |
| `--sequence-id ID` | Apollo sequence ID | None |
| `--yes` | Skip all confirmation prompts | Off |
| `--no-cleanup` | Keep generated-outputs | Off |

## Operational Mode

> **Current Configuration**: Mode B only (list-based)

The pipeline operates in **Mode B** — it uses a pre-curated Apollo People List as input, not live org search.

| Parameter | Value |
|-----------|-------|
| Input mode | `--list-id` (Apollo People List) |
| List name | `NEW 2025-09 Growth Squad: Final People List Companies Hiring Social Media Roles` |
| Contact source | Contacts from this list, grouped by org domain |

This list is the **only** input for current operations. To change the list, update the `LIST_NAME` constant in `find_companies.py` or pass a new `--list-id`.

### Skip Flags (Partial Runs)

```bash
# Skip to email generation (already have intel)
python scripts/run_pipeline.py --source weekly_feb02 --playbook playbook.md \
  --skip-find --skip-scrape --skip-extract --input-intel path/to/intel_extracted.json

# Generate emails only, don't push to Apollo
python scripts/run_pipeline.py --source weekly_feb02 --playbook playbook.md --skip-apollo

# Push existing emails to Apollo
python scripts/run_pipeline.py --source weekly_feb02 --playbook playbook.md \
  --skip-find --skip-scrape --skip-extract --skip-generate \
  --input-emails path/to/emails_generated.json
```

## References

- **Intel extraction fields & rules**: See [references/extraction_prompt.md](references/extraction_prompt.md) when reviewing or modifying what gets extracted from job descriptions
- **Email generation rules**: See [references/email_generation_prompt.md](references/email_generation_prompt.md) when reviewing email quality, structure, or writing rules
- **Apollo one-time setup**: See [references/apollo_setup.md](references/apollo_setup.md) for custom field creation and sequence template setup

## Folder Structure

| Folder | Purpose | Lifecycle |
|--------|---------|-----------|
| `master/` | Track all processed companies per source. Prevents re-processing. | **Permanent** |
| `generated-outputs/` | Intermediate JSON files (companies, JDs, intel, emails). | **Temporary** - auto-deleted after pipeline |

## Step Details

### Step 1: Find Companies (`find_companies.py`)
- Searches Apollo for organizations with matching job titles, or loads from an existing Apollo list
- Supports `--list-id` for pre-curated Apollo lists (account or people lists)
- Outputs `companies_with_jobs.json`

### Step 2: Scrape Descriptions (`scrape_descriptions.py`)
- **Non-LinkedIn URLs**: Scraped via Crawl4AI (self-hosted) with direct HTTP fallback
- **LinkedIn URLs**: Batched via Apify actor `apimaestro~linkedin-job-detail` (takes job IDs, not full URLs)
- **Company homepages**: Each company's domain is scraped for additional context. For JS-heavy SPAs where markdown is empty, falls back to page metadata (title, description, keywords)
- Outputs `job_descriptions.json` with `company_context` field per company

### Step 3: Extract Intel (`extract_intel.py`)
- Claude Sonnet extracts structured fields from each JD: pain signals, tools, seniority, team context, etc.
- Company website context (from Step 2) is injected into the extraction prompt to enrich pain signal inference
- Post-processing filters hallucinated tool names and reclassifies non-competitors
- Outputs `intel_extracted.json` with `company_context` passed through

### Step 4: Generate Emails (`generate_emails.py`)
- Claude Opus generates 3 emails per company (Reality Check / Proof Point / Breakup)
- Uses condensed Agorapulse context (hardcoded, not raw playbook truncation) with industry-matched case studies (Adtrak, Digital Butter, Homefield Apparel, Nexford University)
- Merges intel from all job postings when a company has multiple (deduped lists, highest seniority/urgency)
- Company website context included in prompt for additional personalization
- **Post-generation enforcement**: 20 compiled regex patterns detect banned phrases; emails retry up to 2 times
- **Retry resilience**: JSON parse errors and missing fields also trigger retries (transient failures); hard API errors bail immediately
- Outputs `emails_generated.json`

### Step 5: Push to Apollo (`push_to_apollo.py`)
- Uses `PATCH /contacts/{id}` with `typed_custom_fields` (field IDs as keys, `x-api-key` header auth)
- Populates 3 body custom fields per contact (no subject fields — subjects are set in the sequence template)
- Uses pre-loaded contacts from Step 1 (list-based flow) or searches by domain
- Optionally adds contacts to a sequence

## Configuration

Set API keys in `.env`:

```
APOLLO_API_KEY=your_apollo_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
APIFY_TOKEN=your_apify_token_here          # Required: LinkedIn job scraping
CRAWL4AI_BASE_URL=http://localhost:11235    # Self-hosted Crawl4AI instance
```
