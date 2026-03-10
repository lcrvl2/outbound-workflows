# Hiring Intel TheirStack

**Autonomous TheirStack → Apollo pipeline for social media hiring signals**

Fetches job postings from TheirStack API, extracts structured intel, generates personalized emails, and pushes to Apollo custom fields. Fully autonomous with incremental fetching and two-tier contact matching.

## Overview

This skill is an alternative version of `hiring-intel` that uses **TheirStack API** instead of Apollo org search + web scraping. The key advantage: **job descriptions are already provided by TheirStack**, eliminating the need for scraping and reducing costs by ~$2.50 per 100 companies.

### What It Does

1. **Fetch jobs from TheirStack API** (incremental since last run)
2. **Transform API response** to pipeline format (group by company domain)
3. **Extract structured intel** from job descriptions (Claude Sonnet)
4. **Generate 3-email sequences** per company (Claude Opus + GTM playbook)
5. **Push to Apollo** with two-tier contact matching + sequence enrollment

### Key Differences from hiring-intel

**What gets ELIMINATED:**
- ❌ Step 1 (find_companies.py) — Replaced with TheirStack API fetch
- ❌ Step 2 (scrape_descriptions.py) — Job descriptions already in API response
- ❌ All filter flags (`--list-id`, `--min-employees`, `--geo`) — Filtering done via API

**What gets REUSED:**
- ✅ Intel extraction (extract_intel.py)
- ✅ Email generation (generate_emails.py)
- ✅ Apollo push logic (push_to_apollo.py) — with enhanced contact matching

**What's NEW:**
- 🆕 TheirStack API client with pagination and rate limiting
- 🆕 Incremental fetching (only new jobs since last run)
- 🆕 Two-tier contact matching (name+domain → potential manager fallback)
- 🆕 Autonomous execution (auto-generated source names, auto-push enabled)

## Quick Start

### Prerequisites

1. **API Keys** (add to `.env` file):
   ```bash
   cp .env.example .env
   # Add your API keys:
   # - THEIRSTACK_API_KEY (from https://app.theirstack.com/settings/api)
   # - APOLLO_API_KEY (from Apollo.io)
   # - ANTHROPIC_API_KEY (from console.anthropic.com)
   ```

2. **GTM Playbook** (required for email generation):
   - Create using `gtm-playbook` skill or provide your own markdown file
   - Must include: personas, pain points, value props, case studies

### Run Full Pipeline

```bash
# Autonomous execution (only playbook required)
python scripts/run_pipeline.py --playbook /path/to/playbook.md

# With Apollo sequence enrollment
python scripts/run_pipeline.py \
  --playbook playbook.md \
  --sequence-id SEQ_ABC123
```

**That's it!** The pipeline will:
- Auto-generate source name: `theirstack_2026-02-24`
- Fetch jobs discovered since last run (or 7 days ago for first run)
- Extract intel, generate emails, push to Apollo
- Auto-push enabled (no confirmation needed)
- Auto-cleanup generated-outputs/ after completion

### Dry-Run Mode

```bash
# Skip Apollo push (test fetch → transform → extract → generate)
python scripts/run_pipeline.py --playbook playbook.md --skip-apollo
```

### Resume from Previous Step

```bash
# Already have intel extracted, skip to email generation
python scripts/run_pipeline.py \
  --playbook playbook.md \
  --skip-fetch \
  --skip-transform \
  --skip-extract \
  --input-intel path/to/intel_extracted.json
```

## Pipeline Flow

```
Step 0: Fetch TheirStack Jobs (API)
         ↓ jobs_raw.json
Step 1: Transform API Response
         ↓ job_descriptions.json
Step 2: Extract Intel (Claude Sonnet)
         ↓ intel_extracted.json
Step 3: Generate Emails (Claude Opus + Playbook)
         ↓ emails_generated.json
Step 4: Push to Apollo (Two-Tier Contact Matching)
         ↓ master/{source}_hiring_master.csv
```

### Step 0: Fetch TheirStack Jobs

**What it does:**
- Fetches jobs from TheirStack API with pagination
- Filters by job title keywords: `["social media", "community manager", "content manager", "social media strategist", "social media coordinator"]`
- Only fetches jobs discovered since last run (incremental fetching)
- Handles rate limiting (HTTP 429 with exponential backoff)
- Saves raw API response: `jobs_raw.json`

**Incremental Fetching:**
- First run: Fetches jobs discovered in last 7 days
- Subsequent runs: Reads `master/{source}_hiring_master.csv` for last `date_processed` timestamp
- Uses `discovered_at_gte` parameter to prevent re-processing

**Manual execution:**
```bash
python scripts/fetch_theirstack_jobs.py --limit 100
```

### Step 1: Transform API Response

**What it does:**
- Groups jobs by company domain (multiple jobs per company)
- Extracts domain from `company_url` (with fallback to LinkedIn URL)
- Parses hiring manager name → first_name, last_name
- Builds company context from `company_seo_description` + `company_description` (max 5000 chars)
- Maps TheirStack fields → pipeline format

**Manual execution:**
```bash
python scripts/transform_theirstack_data.py generated-outputs/theirstack_*/jobs_raw.json
```

### Step 2: Extract Intel

**What it does:**
- Uses Claude Sonnet 4.5 to extract 10 structured fields from job descriptions:
  - `job_title`, `seniority`, `responsibility_summary`
  - `tools_mentioned`, `competitor_tools` (only social media management tools)
  - `pain_signals` (inferred from context)
  - `team_context`, `hiring_urgency`
  - `key_metrics`, `platforms_managed`
- Filters hallucinated tools (only keeps tools that appear verbatim in JD)
- Enriches with company context for better pain signal inference

**Manual execution:**
```bash
python scripts/extract_intel.py generated-outputs/theirstack_*/job_descriptions.json --yes
```

**Cost:** ~$0.001 per job description (Sonnet)

### Step 3: Generate Emails

**What it does:**
- Uses Claude Opus 4.6 + GTM playbook to generate 3-email sequences per company
- Merges intel across multiple job postings (if company has 5+ jobs, one company = one 3-email sequence)
- Validates against 20 banned phrase rules (no "I saw that you...", no em dashes, etc.)
- Max 80 words per email, 2 lines per paragraph
- ONE question mark per email

**Manual execution:**
```bash
python scripts/generate_emails.py \
  generated-outputs/theirstack_*/intel_extracted.json \
  --playbook /path/to/playbook.md \
  --yes
```

**Cost:** ~$0.01 per company (Opus 4.6)

### Step 4: Push to Apollo

**What it does:**
- Two-tier contact matching (see below)
- Updates 3 custom fields per contact (Email 1/2/3 bodies)
- Adds contacts to Apollo sequence (optional)
- Saves to master file: `master/{source}_hiring_master.csv`

**Manual execution:**
```bash
python scripts/push_to_apollo.py \
  generated-outputs/theirstack_*/emails_generated.json \
  --source theirstack_2026-02-24 \
  --yes
```

## Two-Tier Contact Matching

**Challenge:** TheirStack provides hiring manager names but NOT Apollo contact IDs.

**Solution:**

### Tier 1: Exact Name + Domain Match
- Search Apollo for contact by `first_name + last_name + domain`
- Uses Apollo People Search API
- If exact match found → use this contact

### Tier 2: Potential Manager Fallback
- If no name match, search by title keywords + domain:
  - `["social media", "community", "content", "marketing", "digital", "brand"]`
- If multiple matches, rank by seniority:
  - `c-level (7) > vp (6) > director (5) > head (4) > lead (3) > senior (2) > mid (1) > junior (0)`
- Use highest-seniority match (prefer CMO over Social Media Coordinator)

**Logs:**
```
✓ Matched by name: Leonard Wittig (Cultural Affairs Manager)
⚠ No name match, using potential manager: Sarah Johnson (VP Marketing)
✗ No contact found for example.com, skipping
```

## TheirStack API Setup

1. **Get API Key:**
   - Sign up at https://theirstack.com
   - Navigate to Settings → API
   - Copy your API key

2. **Add to .env:**
   ```bash
   THEIRSTACK_API_KEY=your_api_key_here
   ```

3. **Configure Job Filters:**
   - Edit `JOB_TITLES` in `scripts/fetch_theirstack_jobs.py`
   - Default filters:
     ```python
     JOB_TITLES = [
         'social media',
         'community manager',
         'content manager',
         'social media strategist',
         'social media coordinator',
     ]
     ```

## Command Reference

### run_pipeline.py

**Required:**
- `--playbook PATH` — GTM playbook markdown file (for email generation)

**Optional:**
- `--sequence-id ID` — Apollo sequence ID to add contacts to
- `--skip-fetch` — Skip TheirStack API fetch (provide `--input-jobs-raw`)
- `--skip-transform` — Skip transformation (provide `--input-descriptions`)
- `--skip-extract` — Skip intel extraction (provide `--input-intel`)
- `--skip-generate` — Skip email generation (provide `--input-emails`)
- `--skip-apollo` — Skip Apollo push step
- `--input-jobs-raw PATH` — Use existing jobs_raw.json
- `--input-descriptions PATH` — Use existing job_descriptions.json
- `--input-intel PATH` — Use existing intel_extracted.json
- `--input-emails PATH` — Use existing emails_generated.json
- `--no-cleanup` — Keep generated-outputs after completion

**Examples:**

```bash
# Full autonomous pipeline
python scripts/run_pipeline.py --playbook playbook.md

# With sequence enrollment
python scripts/run_pipeline.py --playbook playbook.md --sequence-id SEQ_ABC123

# Dry-run (no Apollo push)
python scripts/run_pipeline.py --playbook playbook.md --skip-apollo

# Resume from intel extraction
python scripts/run_pipeline.py \
  --playbook playbook.md \
  --skip-fetch \
  --skip-transform \
  --input-intel path/to/intel_extracted.json

# Keep generated-outputs for debugging
python scripts/run_pipeline.py --playbook playbook.md --no-cleanup
```

## File Structure

```
hiring-intel-theirstack/
├── SKILL.md                          # This file
├── .env.example                      # API key template
├── .env                              # User's API keys (local, gitignored)
├── scripts/
│   ├── run_pipeline.py              # Orchestrator (autonomous)
│   ├── fetch_theirstack_jobs.py     # Step 0: TheirStack API client
│   ├── transform_theirstack_data.py # Step 1: API → pipeline format
│   ├── extract_intel.py             # Step 2: Claude Sonnet extraction
│   ├── generate_emails.py           # Step 3: Claude Opus email generation
│   └── push_to_apollo.py            # Step 4: Two-tier contact matching
├── references/                       # Prompts and config docs
│   ├── extraction_prompt.md
│   ├── email_generation_prompt.md
│   ├── product_truth_table.md
│   └── apollo_setup.md
├── master/                           # Permanent tracking files
│   └── theirstack_{YYYY-MM-DD}_hiring_master.csv
└── generated-outputs/                # Temporary run artifacts (auto-cleaned)
    └── theirstack_{YYYY-MM-DD}/
        ├── jobs_raw.json             # Raw API response
        ├── job_descriptions.json     # Transformed pipeline format
        ├── intel_extracted.json
        └── emails_generated.json
```

## Master File Tracking

**Purpose:** Prevent duplicate processing across runs.

**Location:** `master/theirstack_{YYYY-MM-DD}_hiring_master.csv`

**Fields:**
- `domain` — Company domain (deduplication key)
- `company_name` — Company name
- `contact_first_name`, `contact_last_name` — Matched contact
- `contact_id` — Apollo contact ID
- `email_1_subject`, `email_1_body` — Email 1
- `email_2_body` — Email 2 (same thread)
- `email_3_subject`, `email_3_body` — Email 3 (new thread)
- `date_processed` — ISO 8601 timestamp
- `sequence_id` — Apollo sequence ID (if enrolled)

**Deduplication:**
- Companies already in master file are skipped in subsequent runs
- Incremental fetching uses `date_processed` to determine `discovered_at_gte`

## Cost Estimates

**Per 100 companies (avg 1.5 jobs each = 150 job descriptions):**

- Step 0 (TheirStack API): $0 (included in subscription)
- Step 1 (Transform): $0 (no API calls)
- Step 2 (Intel extraction): 150 × $0.001 = **$0.15** (Sonnet)
- Step 3 (Email generation): 100 × $0.01 = **$1.00** (Opus 4.6)
- Step 4 (Apollo push): $0 (PATCH is free, consumes monthly quota)

**Total: ~$1.15 per 100 companies**

**Savings vs hiring-intel:**
- hiring-intel scraping: $2.50 per 100 companies (Crawl4AI + Apify LinkedIn)
- hiring-intel-theirstack: $0 (job descriptions already provided)
- **Net savings: ~$2.50 per 100 companies**

## Troubleshooting

### TheirStack API Rate Limiting

**Symptom:** HTTP 429 responses

**Fix:** The script automatically handles rate limiting with:
- Exponential backoff (respects `Retry-After` header)
- Proactive 0.5s delay between pagination requests
- Max backoff time: 120 seconds

### No Jobs Found

**Symptom:** "No jobs found. Exiting."

**Possible causes:**
1. No new jobs discovered since last run (check master file for `date_processed`)
2. Job title filters too restrictive (edit `JOB_TITLES` in fetch script)
3. TheirStack API key invalid (check `.env`)

**Debug:**
```bash
# Test with small limit
python scripts/fetch_theirstack_jobs.py --limit 10
```

### Contact Matching Failures

**Symptom:** "✗ No contact found for example.com, skipping"

**Possible causes:**
1. No contacts at company in Apollo (run People Search manually to verify)
2. Hiring manager name doesn't match Apollo records (check typos, nicknames)
3. Title keywords don't match any contacts (edit `PERSONA_TITLES` in push_to_apollo.py)

**Debug:**
```bash
# Check what contacts Apollo returns for a domain
# Use Apollo UI: People Search → filter by domain + title keywords
```

### Missing Hiring Manager Data

**Symptom:** Companies with `contacts: []` in job_descriptions.json

**Fix:** This is expected for some TheirStack records. The two-tier contact matching will fallback to potential manager search in Step 4.

### Email Generation Validation Failures

**Symptom:** Emails fail banned phrase validation

**Fix:** The script auto-retries with Claude Opus (max 3 attempts). If all attempts fail:
1. Check `references/email_generation_prompt.md` for banned phrase rules
2. Inspect `emails_generated.json` to see which phrases triggered failures
3. Update playbook to avoid triggering patterns (e.g., no "I noticed" language)

## Advanced Usage

### Run for Specific Time Period

```bash
# Edit fetch_theirstack_jobs.py:
# Change get_last_run_timestamp() to return specific date
discovered_at_gte = '2026-02-01T00:00:00Z'
```

### Change Job Title Filters

```bash
# Edit scripts/fetch_theirstack_jobs.py:
JOB_TITLES = [
    'content creator',
    'influencer marketing',
    'brand manager',
]
```

### Multi-Source Runs

```bash
# Different source names create separate master files
# Example: weekly runs with date-based sources

# Week 1
python scripts/run_pipeline.py --playbook playbook.md
# Creates: master/theirstack_2026-02-24_hiring_master.csv

# Week 2 (auto-generates new source: theirstack_2026-03-03)
python scripts/run_pipeline.py --playbook playbook.md
# Creates: master/theirstack_2026-03-03_hiring_master.csv
```

## Migration from hiring-intel

**Scenario 1: New user (no hiring-intel history)**
- Start fresh with hiring-intel-theirstack
- No migration needed

**Scenario 2: Existing hiring-intel user switching to TheirStack**
- Master files are source-specific (different source names)
- No conflict — can run both skills in parallel
- hiring-intel: `master/weekly_runs_hiring_master.csv`
- hiring-intel-theirstack: `master/theirstack_2026-02-24_hiring_master.csv`

**Scenario 3: Want unified master tracking**
- Option A: Manually merge CSV files (dedupe by domain)
- Option B: Use same source name for both (e.g., `--source unified`)

## Future Enhancements

**Planned (out of scope for v1):**
1. Company website scraping for enriched company_context (currently uses SEO description only)
2. LinkedIn profile scraping for hiring managers (enrich contact data beyond API fields)
3. TheirStack webhooks for real-time job posting alerts (push-based instead of polling)
4. Apollo contact creation if not found (currently skips with warning)
5. Advanced filtering (technology stack, industry verticals, employee count ranges)
6. Multi-persona targeting (generate different emails for CMO vs Social Media Manager)

## References

- TheirStack API Docs: https://theirstack.com/en/docs/api-reference
- TheirStack OpenAPI Spec: https://api.theirstack.com/openapi
- TheirStack Jobs Guide: https://theirstack.com/en/docs/guides/fetch-jobs-periodically
- Apollo.io API Docs: https://developers.apollo.io
- Anthropic API Docs: https://docs.anthropic.com

## Support

**For bugs or feature requests:**
- Internal: Update `SKILLS-ROADMAP.md` in Outbound/
- TheirStack API issues: support@theirstack.com
- Apollo API issues: https://developers.apollo.io
