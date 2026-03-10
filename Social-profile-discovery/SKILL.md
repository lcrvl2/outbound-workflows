---
name: social-profile-discovery
description: >
  Discover all social media profiles for a list of companies by scraping their websites.
  Uses a three-layer cascade (Crawl4AI → Playwright → DataForSEO SERP) to achieve ~97-99% coverage.
  Surfaces main, regional (@brand_fr), and category (@brand_careers) profiles across 9 platforms:
  Facebook, Instagram, Twitter/X, LinkedIn, TikTok, YouTube, Pinterest, Threads, Bluesky.
  Use when: (1) User wants to find social profiles for companies, (2) User mentions "social profile discovery",
  "social scraping", "find social accounts", "social media profiles", or "profile count",
  (3) User has a CSV of companies/domains and needs their social presence mapped,
  (4) User wants to estimate ACV based on social footprint size.
  Output: pivot CSV — one row per company with per-platform counts and pipe-delimited URLs.
---

# Social Profile Discovery

Discover every social media profile a company operates — main, regional, category — across 9 platforms via a three-layer scraping cascade.

## Folder Structure

```
Social-profile-discovery/
├── SKILL.md
├── scripts/
│   ├── scrape_social_profiles.py      # Main CLI — runs the three-layer cascade
│   └── social_platform_patterns.py    # URL classification, normalization, profile typing
└── generated-outputs/                 # Temporary run artifacts (auto-created)
    └── [source]-[date]/
```

## Usage

```bash
python scripts/scrape_social_profiles.py <input_csv> --source NAME [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `input_csv` | CSV with a Website column | Required |
| `--source NAME` | Source name for output file naming | Required |
| `--output-dir PATH` | Output directory | `generated-outputs/` |
| `--skip-serp` | Skip Layer 3 (no DataForSEO API cost) | Off |
| `--concurrency N` | Max concurrent browser sessions | 5 |
| `--yes` | Skip confirmation prompt | Off |

### Input CSV

Accepts any CSV with a website/domain column. Auto-detects columns by alias:
- **Website**: `website`, `Website`, `domain`, `Domain`, `url`, `URL`, `company_website`
- **Company Name**: `Company Name`, `company_name`, `company`, `name`, `source_name`, `Name`

If no company name column is found, derives name from domain.

### Output CSV

Pivot format — one row per company, sorted by total profile count (descending):

| Column | Example |
|--------|---------|
| Company Name | Hootsuite |
| Website | https://hootsuite.com |
| Total Profiles | 14 |
| Facebook (count) | 3 |
| Facebook (URLs) | `https://facebook.com/hootsuite \| https://facebook.com/hootsuite_fr \| ...` |
| *(repeat for all 9 platforms)* | |
| Discovery Layers Used | crawl4ai, playwright |

## Three-Layer Cascade

Each layer only processes companies that the previous layer failed to find profiles for.

### Layer 1 — Crawl4AI (all companies)

- Headless browser via `crawl4ai` Python library
- Crawls: homepage + `/about` + `/about-us` + `/contact` + `/contact-us`
- Extracts hreflang `<link rel="alternate">` from homepage, then crawls **all** locale pages
- Extraction sources (6): `<a href>`, `<link rel="me">`, JSON-LD `sameAs`, `twitter:site` meta, `og:see_also`, `data-href`
- Expected coverage: ~90%

### Layer 2 — Playwright (Layer 1 failures only)

- Stealth Chromium with realistic UA, 1920x1080 viewport
- Scrolls to bottom to trigger lazy-loaded footers
- Same extraction logic + hreflang crawling as Layer 1
- Expected coverage: +7% (brings total to ~97%)

### Layer 3 — DataForSEO SERP (Layer 1+2 failures only)

- 9 SERP queries per company: `site:platform.com "Company Name"`
- Batch POST → poll `tasks_ready` → fetch results (same pattern as Mentions-enrichment)
- Cost: ~$0.003/company (9 queries x $0.0006)
- Expected coverage: +2% (brings total to ~97-99%)

**Requires `.env`:**
```
DATAFORSEO_USERNAME=
DATAFORSEO_PASSWORD=
```

## Profile Classification

### Platforms (9)

Facebook, Instagram, Twitter/X, LinkedIn, TikTok, YouTube, Pinterest, Threads, Bluesky

### Profile Types

| Type | Detection | Example |
|------|-----------|---------|
| `main` | Handle matches company name | `@hootsuite` |
| `regional` | Handle ends with locale suffix | `@hootsuite_fr`, `@hootsuitebrasil` |
| `category` | Handle contains category keyword | `@hootsuitecareers`, `@hootsuitesupport` |

### URL Normalization

All discovered URLs are normalized before deduplication:
- Force https, strip `www.`/`m.`/`mobile.` prefixes
- Canonicalize `x.com` → `twitter.com`
- Canonicalize localized subdomains (`fr.linkedin.com` → `linkedin.com`)
- Strip query params and fragments, lowercase, remove trailing slashes

### Filtering

Share/intent URLs are rejected: `/share`, `/sharer`, `/intent/`, `/dialog/`, `/plugins/`

## Agent Instructions

### Mandatory Dry Run

The script always shows a dry-run preview before processing. **Never use `--yes` unless the user explicitly asks to skip confirmation.** The preview shows:
- Company count and first 10 companies
- Layer breakdown with estimates
- SERP cost estimate and DataForSEO balance (if Layer 3 enabled)

### Standalone Tool

This skill is **independent** from the Mentions-enrichment pipeline. Do not reference `run_pipeline.py` or attempt to integrate the two. Run `scrape_social_profiles.py` directly.

### Interpreting Output

- **Total Profiles** is the key ACV indicator — more profiles = higher deal value
- **Per-platform count** shows breadth of social presence
- Companies with 0 profiles after all layers likely have no social presence or use non-standard platforms

## Cost Estimation

| Component | Cost | When |
|-----------|------|------|
| Crawl4AI | Free | Always |
| Playwright | Free | ~10% of companies |
| DataForSEO SERP | ~$0.003/company | ~3-5% of companies |
| **Average per company** | **~$0.00015** | |

For 1,000 companies: ~$0.15 total (if SERP enabled).

## Dependencies

```
crawl4ai        # Layer 1 — batch web scraping with built-in browser
playwright       # Layer 2 — targeted fallback (also used by crawl4ai internally)
requests         # Layer 3 — DataForSEO API
python-dotenv    # .env loading (optional)
```

Install: `pip install crawl4ai playwright requests python-dotenv && playwright install chromium`
