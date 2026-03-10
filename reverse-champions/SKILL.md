---
name: reverse-champions
description: >
  Pipeline to turn closed-won customer contacts into warm outbound lists. For each CW user,
  scrapes LinkedIn work history, identifies last 2 previous employers, validates against ICP,
  finds personas, and enrolls them into a pre-built Apollo sequence. Use when:
  (1) User mentions "reverse champions", "CW outbound", "champion pipeline", or "closed-won leads",
  (2) Building outbound targeting companies where former CW users previously worked,
  (3) User wants champion-angle outreach without naming the champion.
  Production source is Apollo (filtered by closed date). CSV input is for testing only.
  NEVER use --yes flag unless the user explicitly requests auto-confirmation.
  Always identify the source name before running (check master/ for existing sources).
---

# Reverse Champions Skill

Turn closed-won customer contacts into warm outbound via their work history.

## Pipeline

```
CW users from Apollo (or CSV for testing)
  -> Scrape LinkedIn profiles (Apify)
    -> Filter roles (regex + Haiku)
      -> Validate companies (ICP + competitor exclusion, >200 employees)
        -> Find personas (Apollo People Search, max 3)
          -> Enroll in Apollo sequence
```

Contacts are enrolled into a pre-built 4-email template sequence. No AI email generation — same copy for everyone with {{firstName}} and {{companyName}} merge tags.

## Quick Start

```bash
# Full pipeline (testing with CSV)
python scripts/run_pipeline.py --source q1_champions --csv /path/to/export.csv \
  --min-employees 200 --sequence-id SEQ_ABC123

# Custom column mapping (when CSV headers don't auto-detect)
python scripts/run_pipeline.py --source q1_champions --csv export.csv \
  --min-employees 200 --col-name "Full Name" --col-email "Work Email" --col-company "Account"
```

## Pipeline Options

| Flag | Description | Default |
|------|-------------|---------|
| `--source NAME` | Source name for master file tracking | Required |
| `--csv PATH` | Input CSV with CW contacts (testing only) | Required |
| `--col-name COL` | Column name for contact name | Auto-detect |
| `--col-email COL` | Column name for email | Auto-detect |
| `--col-company COL` | Column name for company | Auto-detect |
| `--col-linkedin COL` | Column name for LinkedIn URL | Auto-detect |
| `--min-employees N` | Minimum employee count | None |
| `--max-employees N` | Maximum employee count | None |
| `--geo GEO` | Geographic filter | All |
| `--sequence-id ID` | Apollo sequence ID | Required |
| `--yes` | Skip all confirmation prompts | Off |
| `--no-cleanup` | Keep generated-outputs | Off |

### Skip Flags (Partial Runs)

```bash
# Skip to persona finding (already have validated companies)
python scripts/run_pipeline.py --source q1_champions \
  --skip-load --skip-scrape --skip-filter --skip-validate \
  --input-companies path/to/validated_companies.json

# Retry failed LinkedIn scrapes
python scripts/run_pipeline.py --source q1_champions \
  --skip-load --csv path/to/scrape_failures.csv
```

## References

- **Champion messaging rules**: See [references/champion_addendum.md](references/champion_addendum.md) for privacy constraints
- **Role filtering rules**: See [references/role_filter_prompt.md](references/role_filter_prompt.md) for Haiku classification of ambiguous titles
- **Competitor exclusion**: See [references/competitors.txt](references/competitors.txt) for auto-excluded domains
- **Apollo setup**: See [references/apollo_setup.md](references/apollo_setup.md) for custom field creation
- **Play brief**: See [brief.md](brief.md) for full context, email copy, and next steps

## Folder Structure

| Folder | Purpose | Lifecycle |
|--------|---------|-----------|
| `master/` | Track all processed target companies per source. Prevents re-processing. | **Permanent** |
| `generated-outputs/` | Intermediate JSON files (champions, work history, roles, companies, personas). | **Temporary** - auto-deleted after pipeline |

## Configuration

Set API keys in `.env`:

```
APOLLO_API_KEY=your_apollo_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
APIFY_TOKEN=your_apify_token_here
```
