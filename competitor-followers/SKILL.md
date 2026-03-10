---
trigger: "process competitor followers" OR "scrape LinkedIn followers" OR "competitor follower outreach"
description: Extract LinkedIn followers from competitor pages, filter by ICP + persona, and output qualified contact CSVs
requires_chrome: false
requires_apis: APIFY_TOKEN, APOLLO_API_KEY, ANTHROPIC_API_KEY
estimated_cost: "$20-25 per 1k followers (pilot), $2.5k-5k for full 5-competitor extraction"
output_format: CSV (contacts_enriched.csv + contacts_needs_enrichment.csv)
---

# Competitor Followers — List Building Skill

Build a qualified prospect list from competitors' LinkedIn followers. Use LinkedIn follower status as a relevance signal, then filter aggressively by ICP + persona to produce a clean, enriched CSV of target companies and contacts.

**Scope**: List creation ONLY (not outreach). Output is a ready-to-import CSV with qualified companies, decision-maker contacts, and emails. Email generation and sequence enrollment are OUT OF SCOPE for v1.

## Use Case

People who follow your competitors on LinkedIn have shown interest in your product category. This skill helps you:

1. **Extract** follower lists from competitor LinkedIn pages (Apify)
2. **Deduplicate** across competitors (many people follow multiple tools)
3. **Qualify** companies by ICP (200-2k employees, relevant industries)
4. **Find** 2-3 decision-makers at each qualified company (Apollo)
5. **Enrich** with verified emails + check suppression lists

The output is a CSV of qualified contacts ready for outreach via Apollo, Instantly, or your CRM.

## Campaign Flow

```
Competitor LinkedIn Pages
         ↓
Extract Followers (Apify: $0.02/follower)
         ↓
Deduplicate Across Competitors (master file)
         ↓
Qualify Companies (Sonnet ICP filter: 200-2k employees)
         ↓
Find Decision-Makers (Apollo: 2-3 per company)
         ↓
Enrich + Suppression Check (Apollo API)
         ↓
contacts_enriched.csv (PRIMARY OUTPUT)
contacts_needs_enrichment.csv (secondary, for manual follow-up)
```

## Pipeline Stages

### 1. Follower Extraction (Apify)
- Apify actor: `alizarin_refrigerator-owner/linkedin-company-followers-scraper`
- Cost: $0.02 per follower
- Cap: `--max-followers N` (default: 5000, use 0 for unlimited)
- Recency: LinkedIn API returns recent followers first → capping = recency filter
- Output: `followers_raw.json` (linkedin_url, name, title, company, source_competitor)

### 2. Deduplication (Master File)
- Load: `master/{source_name}_followers_master.csv`
- Dedupe: By LinkedIn URL across all competitors
- Track: Which competitor each follower came from (attribution)
- Output: `followers_deduped.json`

### 3. ICP Qualification (Claude Sonnet)
- Enrich: Company metadata via Apollo API (`POST /api/v1/organizations/enrich`)
- Filter: 200-2,000 employees, relevant industries (SaaS, agencies, e-commerce, media)
- Exclude: Stealth startups, competitors (from `references/competitors.txt`)
- AI: Claude Sonnet 4.5 classification (accuracy > cost)
- Output: `companies_qualified.json`

### 4. Find Decision-Makers (Apollo)
- Strategy: Use follower's **company** as signal (ignore their personal title)
- Search: Apollo for 2-3 decision-makers at each ICP-qualified company
- Titles: CMO, VP Marketing, Head of Social, Director Marketing, Social Media Manager, Content Manager
- Priority: Seniority ranking (CMO > VP > Director > Manager)
- Rate limit: 1 request per second
- Output: `personas_found.json`

### 5. Enrich + Suppression Check (Apollo)
- Check: Apollo suppression list (unsubscribed/opted-out contacts)
- Verify: Email quality (not generic info@/support@ addresses)
- Split:
  - **contacts_enriched.csv** — Contacts with verified emails (ready for outreach)
  - **contacts_needs_enrichment.csv** — Qualified companies where Apollo found no email
- Update: Master file with all processed companies
- Output: Two CSV files (primary deliverables)

## Usage

### Basic Usage (Pilot)
```bash
cd competitor-followers
python scripts/run_pipeline.py \
  --source "hootsuite_pilot_feb_2026" \
  --competitors "https://www.linkedin.com/company/hootsuite/" \
  --max-followers 1000
```

### Full Extraction (5 Competitors, No Cap)
```bash
python scripts/run_pipeline.py \
  --source "competitor_followers_full_feb_2026" \
  --competitors "https://www.linkedin.com/company/hootsuite/,https://www.linkedin.com/company/sprout-social-inc/,https://www.linkedin.com/company/sprinklr/,https://www.linkedin.com/company/brandwatch/,https://www.linkedin.com/company/meltwater/" \
  --max-followers 0 \
  --contacts-per-company 3
```

### Custom ICP Filters
```bash
python scripts/run_pipeline.py \
  --source "smb_segment_march_2026" \
  --competitors "https://www.linkedin.com/company/buffer/" \
  --max-followers 2000 \
  --min-employees 50 \
  --max-employees 500 \
  --persona-titles "Social Media Manager,Content Manager,Marketing Coordinator"
```

### Partial Runs (Resume from Checkpoint)
```bash
# Skip extraction, start from deduplication
python scripts/run_pipeline.py \
  --source "hootsuite_pilot_feb_2026" \
  --skip-extract \
  --input-followers generated-outputs/hootsuite_pilot_feb_2026-2026-02-13/followers_raw.json

# Skip to enrichment only
python scripts/run_pipeline.py \
  --source "hootsuite_pilot_feb_2026" \
  --skip-extract --skip-dedupe --skip-qualify --skip-personas \
  --input-contacts generated-outputs/hootsuite_pilot_feb_2026-2026-02-13/personas_found.json
```

## CLI Arguments

### Required
- `--source NAME` — Source identifier (e.g., "hootsuite_pilot_feb_2026")
- `--competitors URL1,URL2,URL3` — Comma-separated LinkedIn company URLs

### Optional
- `--max-followers N` — Cap followers per competitor (default: 5000, use 0 for unlimited)
- `--contacts-per-company N` — Decision-makers per qualified company (default: 3)
- `--min-employees N` — Minimum employee count (default: 200)
- `--max-employees N` — Maximum employee count (default: 2000)
- `--persona-titles "title1,title2,title3"` — Override default target titles

### Flags
- `--no-cleanup` — Keep generated-outputs directory after completion
- `--skip-extract` — Skip follower extraction (provide `--input-followers`)
- `--skip-dedupe` — Skip deduplication (provide `--input-deduped`)
- `--skip-qualify` — Skip ICP qualification (provide `--input-companies`)
- `--skip-personas` — Skip persona search (provide `--input-personas`)
- `--skip-enrich` — Skip final enrichment (provide `--input-contacts`)

## Output Files

### Primary Output
`generated-outputs/{source_name}-{date}/contacts_enriched.csv`

Columns:
- `company_name` — Company name
- `domain` — Company domain
- `employee_count` — Number of employees
- `industry` — Industry classification
- `source_competitor` — Which competitor they follow
- `contact_name` — Decision-maker name
- `contact_title` — Job title
- `contact_email` — Verified email address
- `contact_phone` — Phone number (if available)
- `contact_linkedin_url` — LinkedIn profile URL
- `date_processed` — Processing date

### Secondary Output
`generated-outputs/{source_name}-{date}/contacts_needs_enrichment.csv`

Same columns as above, but `contact_email` is empty (Apollo found no email). Use for manual enrichment or alternative outreach channels (LinkedIn InMail, company phone).

### Master File (Persistent)
`master/{source_name}_followers_master.csv`

Tracks all processed companies to prevent re-processing across runs. Same columns as primary output.

## Cost Estimation

### Pilot (1,000 Hootsuite followers)
- Extraction: 1,000 × $0.02 = **$20**
- ICP qualification (Sonnet): ~200 companies × $0.001 = **$0.20**
- Apollo enrichment: **Free** (within rate limits)
- **Total: ~$20-25**

### Full Scale (5 competitors, no cap)
- Hootsuite: ~50k-100k followers → $1,000-2,000
- Sprout Social: ~20k-40k followers → $400-800
- Sprinklr: ~30k-50k followers → $600-1,000
- Brandwatch: ~15k-30k followers → $300-600
- Meltwater: ~10k-20k followers → $200-400
- **Total extraction: ~$2,500-4,800**
- **Total with Sonnet qualification: ~$2,550-4,900**
- **NOTE**: Requires management budget approval before proceeding

## Success Metrics

Track in master file CSV:
- **Extraction**: Total followers extracted per competitor
- **Unique Companies**: Unique companies after deduplication
- **ICP Pass Rate**: % of companies that pass ICP filter
- **Email Found Rate**: % of qualified companies with emails
- **Contacts per Company**: Average decision-makers found (target: 2-3)
- **Cost per Qualified Company**: Total spend / ICP-qualified companies with emails

**Pilot Success Threshold**: If 1,000 Hootsuite followers yield 100+ qualified companies with emails → proceed to full 5-competitor extraction (pending budget approval)

## Integration with Other Skills

### Outreach (Future v2)
1. Run `competitor-followers` to generate `contacts_enriched.csv`
2. Use `write-sequence` skill with competitor-follower-specific messaging:
   - "Noticed you follow [Competitor] → offer benchmark/checklist/insights"
   - Don't mention "we pulled followers" (avoid creepy factor)
3. Import CSV to Apollo/Instantly for sequence enrollment

### GTM Playbook Integration
1. Run `gtm-playbook` on your own product to understand positioning
2. Use playbook context in `references/company_icp_filter_prompt.md` for better qualification
3. Reference playbook pain points in future email generation (v2)

## API Credentials

Required `.env` file:
```bash
APIFY_TOKEN=apify_api_xxx
APOLLO_API_KEY=xxx
ANTHROPIC_API_KEY=sk-ant-xxx
```

## Troubleshooting

### Error: "Apify actor returned no followers"
- Check LinkedIn URL format (must be company page, not personal profile)
- Verify company page has public followers (some pages hide follower lists)
- Try smaller `--max-followers` value first to test

### Error: "Apollo rate limit exceeded"
- Reduce `--contacts-per-company` from 3 to 1-2
- Add longer delays in `find_personas.py` (increase rate limit from 1s to 2s)

### Error: "No companies passed ICP filter"
- Review `references/company_icp_filter_prompt.md` criteria
- Adjust `--min-employees` / `--max-employees` range
- Check if follower list contains mostly individuals vs. companies

### Low Email Found Rate (<30%)
- Apollo may not have coverage in target geo/industry
- Use `contacts_needs_enrichment.csv` for manual enrichment via:
  - LinkedIn Sales Navigator
  - Hunter.io / RocketReach
  - Manual research

## References

- **Apify Actor**: [linkedin-company-followers-scraper](https://apify.com/alizarin_refrigerator-owner/linkedin-company-followers-scraper)
- **Apollo API Docs**: [https://apolloio.github.io/apollo-api-docs/](https://apolloio.github.io/apollo-api-docs/)
- **Pattern Reference**: `hiring-intel/` and `reverse-champions/` skills for Apollo integration examples
