---
name: linkedin-company-analytics
description: Scrape LinkedIn company follower count + post frequency for 1800+ companies. Outputs enriched CSV for sequence personalization signals (inactivity, post cadence, follower size). Maintains a master file for future follower growth tracking.
triggers:
  - "analyze LinkedIn companies"
  - "scrape follower counts"
  - "get post frequency"
  - "linkedin company analytics"
---

# LinkedIn Company Analytics

## What It Does

For a list of companies (with LinkedIn URLs), scrapes:
- **Follower count** — current snapshot via rigelbytes actor ($0.01/company, fixed cost)
- **Post frequency** — all original posts in the last 3 months via harvestapi actor ($0.002/post, variable)

Outputs `metrics_enriched.csv` with 14 signal columns ready for sequence personalization.

## Key Output Signals

| Column | Description | Use In Copy |
|--------|-------------|-------------|
| `follower_count` | Current LinkedIn followers | "Scale signal" — SMB vs enterprise |
| `posts_last_30d` | Original posts in last 30 days | Recent activity |
| `posts_last_90d` | Original posts in last 90 days | Broader cadence |
| `avg_posts_per_week` | `posts_last_90d / 13` | High/low activity angle |
| `days_since_last_post` | Days since most recent post | Inactivity angle |
| `top_post_likes` | Max likes on any post in period | Engagement signal |
| `follower_growth` | Growth vs previous snapshot (null on first run) | Momentum angle |
| `follower_growth_pct` | Growth % vs previous snapshot | |

## Quick Start

```bash
cd Outbound/linkedin-company-analytics

# 1. Set up credentials
cp .env.example .env
# Edit .env → add APIFY_TOKEN

# 2. Install dependencies
pip install -r requirements.txt

# 3. FIRST: Test on 5 companies to confirm actor field names
python scripts/test_actors.py --input test_5.csv
# → Inspect generated-outputs/test-{date}/raw_followers.json
# → Confirm the follower count field name (e.g. 'followersCount')
# → Update FOLLOWER_FIELD in analyze_metrics.py if needed

# 4. Full pipeline
python scripts/run_pipeline.py --input companies.csv --source li_analytics_q1_2026
# → Shows cost estimate and asks for confirmation
# → Outputs metrics_enriched.csv in generated-outputs/{source}-{date}/
```

## Input CSV Format

Must have a `linkedin_url` column. Optionally `domain`.

```csv
linkedin_url,domain
https://www.linkedin.com/company/hootsuite,hootsuite.com
https://www.linkedin.com/company/buffer,buffer.com
```

## Pipeline Steps

```
Input CSV
  → Step 1: scrape_followers.py   → raw_followers.json   ($18 for 1800 companies)
  → Step 2: scrape_posts.py       → raw_posts.json        (~$11-36 variable)
  → Step 3: analyze_metrics.py    → metrics_enriched.csv
                                  → master/{source}_master.csv
```

### Step 1: Scrape Followers
```bash
python scripts/scrape_followers.py --input companies.csv --output-dir generated-outputs/q1/
```
- Actor: `rigelbytes/linkedin-company-details`
- Batch size: 50 companies/run
- Cost: $0.01/company (fixed)
- Requires RESIDENTIAL proxy (configured automatically)
- Incremental writes after each batch — crash-safe

### Step 2: Scrape Posts
```bash
python scripts/scrape_posts.py --input companies.csv --output-dir generated-outputs/q1/
```
- Actor: `harvestapi/linkedin-company-posts`
- Period: 3 months (`postedLimit='3months'`)
- Original posts only (`includeReposts=false`)
- Cost: $0.002/post × actual post count (unknown until run)
- Incremental writes after each batch — crash-safe

### Step 3: Analyze
```bash
python scripts/analyze_metrics.py \
  --followers generated-outputs/q1/raw_followers.json \
  --posts generated-outputs/q1/raw_posts.json \
  --input companies.csv \
  --source q1 \
  --output-dir generated-outputs/q1/
```

## Resuming Interrupted Runs

```bash
# Followers done, skip re-spending
python scripts/run_pipeline.py --input companies.csv --source q1 \
    --skip-followers --input-followers generated-outputs/q1-2026-02-18/raw_followers.json

# Both actors done, re-run analysis only
python scripts/run_pipeline.py --input companies.csv --source q1 \
    --skip-followers --input-followers PATH \
    --skip-posts --input-posts PATH
```

## Master File (Follower Growth Tracking)

On each run, `master/{source}_master.csv` is updated with one snapshot row per company.

On the **second run**, `analyze_metrics.py` loads the previous snapshot → computes:
- `follower_count_prev` — follower count from last run
- `follower_growth` — absolute change
- `follower_growth_pct` — % change

First run: these three columns will be empty (baseline only).

## Cost Estimates (1800 companies)

| Actor | Unit cost | Fixed/Variable | Estimate |
|-------|-----------|---------------|---------|
| rigelbytes (followers) | $0.01/company | Fixed | **$18.00** |
| harvestapi (posts) | $0.002/post | Variable | **$11–$36** |
| **Total** | | | **~$29–$54** |

harvestapi cost depends on post volume. Companies with 5 posts/month cost more than inactive ones.

## Critical: Run test_actors.py First

rigelbytes has **no documented output schema** in the Apify store. Field names for follower count (`followersCount`? `followerCount`? `followers`?) are unknown until tested.

```bash
python scripts/test_actors.py --input test_5.csv
```

This prints a full field audit of both actors' output. Update `FOLLOWER_FIELD` in [scripts/analyze_metrics.py](scripts/analyze_metrics.py) if the actual field name differs from `followersCount`.

## Credentials

Only needs `APIFY_TOKEN` in `.env`:
```
APIFY_TOKEN=apify_api_...
```

## Actors Used

| Actor | ID | Pricing |
|-------|-----|---------|
| rigelbytes/linkedin-company-details | `rigelbytes~linkedin-company-details` | $0.01/company |
| harvestapi/linkedin-company-posts | `harvestapi~linkedin-company-posts` | $0.002/post |
