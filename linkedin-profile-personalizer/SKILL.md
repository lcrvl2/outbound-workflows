---
skill: linkedin-profile-personalizer
version: 1.0.0
status: active
---

# LinkedIn Profile Personalizer

Generate personalized cold email hooks from LinkedIn profiles. Takes a list of LinkedIn URLs, scrapes profiles via Apify, infers the implied business pain via Claude Haiku, and generates a 1–2 sentence personalized opening via Claude Sonnet. Exports CSV and optionally patches Apollo contacts with the hook.

## Usage

```bash
python scripts/run_pipeline.py \
  --source NAME \
  --input contacts.csv \
  [--apollo-field-id FIELD_ID] \
  [--sequence-id SEQ_ID]
```

## Pipeline

```
Step 1: Load contacts from CSV (dedup against master)
Step 2: Scrape LinkedIn profiles via Apify
Step 3: Extract pain signals via Claude Haiku
Step 4: Generate personalized hooks via Claude Sonnet
Step 5: Export CSV + optionally push to Apollo
```

## Input

A CSV with at least one column containing LinkedIn URLs. Column names are auto-detected or overridden with `--col-*` flags.

**Minimum required columns:**
- `linkedin_url` (auto-detected from common variants)

**Optional columns (enhance output):**
- `first_name`, `last_name`, `email`, `company`, `apollo_id`

## Output

**Always generated:**
- `generated-outputs/{source}-{YYYY-MM-DD}/personalized_hooks.csv`

**Columns in CSV:**
| Column | Description |
|--------|-------------|
| `first_name` | From input CSV or scraped profile |
| `last_name` | From input CSV or scraped profile |
| `email` | From input CSV |
| `company` | From input CSV or scraped profile |
| `linkedin_url` | Normalized LinkedIn URL |
| `hook` | Generated 1–2 sentence personalized opening |
| `confidence` | Haiku confidence: high / medium / low |
| `pain_signal` | Inferred pain (1 sentence) |
| `hook_warnings` | Flags: banned_phrase, over_word_limit, contains_question |
| `hook_error` | Error if hook was skipped or failed |

**Optional (if flags provided):**
- Apollo contact patched with hook in custom field
- Contact enrolled in sequence

## Hook Quality Rules

The generated hook must:
- Reference the implied situation (not the job title)
- Mirror vocabulary from their LinkedIn headline
- Imply the pain — not name it directly
- Be ≤40 words, no question marks, no em dashes
- No "I saw that you...", no flattery, no generic openers

Contacts with `confidence: low` are skipped (no hook generated) — flagged in CSV with `hook_error: skipped_low_confidence`.

## Options

| Flag | Description |
|------|-------------|
| `--source NAME` | Required. Used for output dir naming and master tracking |
| `--input PATH` | Input CSV path |
| `--apollo-field-id ID` | Apollo custom field ID to write hook to |
| `--sequence-id ID` | Apollo sequence ID to enroll contacts into |
| `--col-linkedin COL` | Override column name for LinkedIn URL |
| `--col-first-name COL` | Override column name for first name |
| `--col-last-name COL` | Override column name for last name |
| `--col-email COL` | Override column name for email |
| `--col-company COL` | Override column name for company |
| `--col-apollo-id COL` | Override column name for Apollo contact ID |
| `--yes` | Skip all confirmation prompts |
| `--skip-scrape` | Skip scraping (use `--input-profiles`) |
| `--skip-extract` | Skip extraction (use `--input-intel`) |
| `--skip-generate` | Skip generation (use `--input-hooks`) |
| `--skip-push` | Skip Apollo push (CSV still exports) |
| `--input-profiles PATH` | Use existing `profiles_scraped.json` |
| `--input-intel PATH` | Use existing `intel_extracted.json` |
| `--input-hooks PATH` | Use existing `hooks_generated.json` |

## Environment Variables

```
ANTHROPIC_API_KEY=...
APIFY_TOKEN=...
APOLLO_API_KEY=...       # Only needed for --apollo-field-id / --sequence-id
```

## Cost Estimates (per profile)

| Step | Model | Cost |
|------|-------|------|
| Scrape | Apify | ~$0.002 |
| Extract | Claude Haiku | ~$0.0003 |
| Generate | Claude Sonnet | ~$0.003 |
| **Total** | | **~$0.005** |

50 profiles ≈ $0.25 | 100 profiles ≈ $0.50

## Resuming a Partial Run

```bash
# Scrape done, resume from extraction
python scripts/run_pipeline.py \
  --source NAME \
  --skip-scrape \
  --input-profiles generated-outputs/NAME-YYYY-MM-DD/profiles_scraped.json

# Extract done, resume from generation
python scripts/run_pipeline.py \
  --source NAME \
  --skip-scrape --skip-extract \
  --input-intel generated-outputs/NAME-YYYY-MM-DD/intel_extracted.json
```

## Files

```
linkedin-profile-personalizer/
├── SKILL.md                            # This file
├── scripts/
│   ├── run_pipeline.py                 # Orchestrator
│   ├── load_contacts.py                # CSV loading + dedup
│   ├── scrape_profiles.py              # Apify LinkedIn profile scraper
│   ├── extract_intel.py                # Haiku pain signal extraction
│   ├── generate_hooks.py               # Sonnet hook generation + validation
│   └── push_output.py                  # CSV export + Apollo patch
├── references/
│   ├── extraction_prompt.md            # System prompt for Haiku
│   └── hook_generation_prompt.md       # System prompt for Sonnet
├── master/
│   └── {source}_profiles_master.csv    # Tracks processed LinkedIn URLs
└── generated-outputs/
    └── {source}-{YYYY-MM-DD}/
        ├── contacts_to_process.json
        ├── profiles_scraped.json
        ├── intel_extracted.json
        ├── hooks_generated.json
        └── personalized_hooks.csv
```
