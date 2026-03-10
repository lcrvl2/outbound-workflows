# Outbound — Agentic Workflows

B2B outbound automation toolkit. Each subfolder is a standalone **skill** (a Claude Code workflow with its own `SKILL.md`, scripts, and references). Skills chain together to go from ICP research to sequence-ready emails pushed to Apollo.io.

## Project Structure

```
Outbound/
├── CLAUDE.md                    # This file
├── .mcp.json                    # Chrome DevTools MCP server config
├── SKILLS-ROADMAP.md            # Full roadmap with planned skills
├── knowledge-base/              # Shared sales frameworks & prompts
│   ├── outbound-playbook.md     # Cold email, signals, discovery, objections
│   └── master-prompts.md        # 12 sales prompt templates
│
├── gtm-playbook/                # Generate GTM playbooks from website URLs
├── targeting-ideas/             # Generate 20 targeting ideas from a playbook
├── write-sequence/              # Write 3-email sequences per segment
├── hiring-intel/                # Job postings → personalized emails → Apollo
├── reverse-champions/           # CW contacts → work history → warm outbound
├── churned-user-detector/       # Churned users → job change detection
├── Mentions-enrichment/         # Mention.com exports → domain enrichment → Apollo
├── Social-profile-discovery/    # Company websites → social profiles (9 platforms)
├── linkedin-content-scraper/    # LinkedIn profiles → formatted .md post archives
├── apollo-lead-processor/       # Apollo UI automation (list → sequence → SF)
└── apollo-job-changer-processor/# Apollo job changer enrichment automation
```

## Skill Overview

### Research & Strategy
| Skill | Trigger | What It Does |
|-------|---------|--------------|
| `gtm-playbook` | "create a GTM playbook for [url]" | Analyzes website → generates playbook with verticals, personas, case studies |
| `targeting-ideas` | `[targeting-ideas]` | Playbook → 20 targeting ideas with interactive HTML table |
| `write-sequence` | `[write-sequence]` or `[write-sequence] #N` | Targeting idea + playbook → 3-email cold sequence for entire segment |

### Pipeline Skills (Python scripts)
| Skill | Command | Pipeline |
|-------|---------|----------|
| `hiring-intel` | `python scripts/run_pipeline.py --source NAME --playbook PATH` | Apollo search → scrape JDs → extract intel → generate 1:1 emails → push to Apollo |
| `reverse-champions` | `python scripts/run_pipeline.py --source NAME --csv PATH --playbook PATH` | CW contacts → LinkedIn scrape → role filter → ICP validate → find personas → champion emails → Apollo |
| `churned-user-detector` | `python scripts/run_pipeline.py --source NAME --csv PATH` | Churned user CSV → LinkedIn enrich → scrape → classify job changes → email check |
| `Mentions-enrichment` | `python scripts/run_pipeline.py --alert-id ID --source NAME` | Mention.com API → domain enrichment (DataForSEO) → Apollo import + filter |
| `Social-profile-discovery` | `python scripts/scrape_social_profiles.py INPUT --source NAME` | 3-layer cascade (Crawl4AI → Playwright → DataForSEO) → social profile pivot CSV |

### Content & Scraping
| Skill | Trigger | What It Does |
|-------|---------|--------------|
| `linkedin-content-scraper` | "scrape LinkedIn posts from [profile]" | Apify actor → formatted .md file per creator |

### Apollo UI Automation (Chrome DevTools MCP)
| Skill | Trigger | What It Does |
|-------|---------|--------------|
| `apollo-lead-processor` | "process Apollo leads" | List → select contacts → add to list → change owner → sequence → SF → suppression |
| `apollo-job-changer-processor` | "process job changers" | Accept job updates across EN/FR/DACH lists → enrich → push to SF |

## Conventions

### Folder Layout (per skill)
Every pipeline skill follows this structure:
- `SKILL.md` — Skill definition (frontmatter + full docs)
- `scripts/` — Python scripts, each runnable standalone or via `run_pipeline.py`
- `references/` — Prompts, templates, config docs
- `master/` — Permanent tracking files (prevent re-processing)
- `generated-outputs/` — Temporary run artifacts (auto-cleaned after pipeline)

### Shared Patterns
- **Master files** prevent duplicate processing across runs
- **Dry-run previews** show what will be processed before executing (cost estimates for paid APIs)
- **`--yes` flag** skips confirmations — **never use unless user explicitly requests it**
- **`--source NAME`** is always required to track provenance
- **Timestamped output dirs**: `generated-outputs/{source}-{YYYY-MM-DD}/`
- **Skip flags** (`--skip-find`, `--skip-scrape`, etc.) allow partial/resumed runs

### API Credentials
All skills read from `.env` files in their respective directories:
- `APOLLO_API_KEY` — Apollo.io API
- `ANTHROPIC_API_KEY` — Claude (Haiku for extraction, Sonnet for generation)
- `APIFY_TOKEN` — LinkedIn scraping, content scraping
- `CRAWL4AI_BASE_URL` — Self-hosted Crawl4AI instance
- `DATAFORSEO_USERNAME` / `DATAFORSEO_PASSWORD` — Domain enrichment, SERP fallback
- `MENTION_API_TOKEN` / `MENTION_ACCOUNT_ID` — Mention.com API

### Chrome DevTools MCP
Apollo UI automation skills require Chrome with remote debugging:
```bash
open -a "Google Chrome" --args --remote-debugging-port=9222
```
Config in `.mcp.json` — uses `chrome-devtools-mcp@latest`.

## Typical Workflow Chain

```
gtm-playbook → [targeting-ideas] → [write-sequence] #N
                                  → hiring-intel (with playbook)
                                  → reverse-champions (with playbook)
```

1. **GTM Playbook** generates personas, verticals, pain points for a product
2. **Targeting Ideas** creates 20 segment ideas from the playbook
3. **Write Sequence** or **Hiring Intel** turns segments into email sequences
4. **Apollo Lead Processor** enrolls contacts into sequences via UI automation

## Email Writing Rules (all skills)

- Max 80 words per email, 2 lines per paragraph
- ONE question mark per email
- No em dashes, no exclamation marks, no signatures, no emojis
- No "I saw that you..." / "Love what you're building" / generic AI phrases
- Merge tags: `{{firstName}}`, `{{companyName}}`
- Signal-based: reference what the signal MEANS, not the signal itself

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3 | All pipeline scripts |
| Apollo.io API | Contact search, enrichment, sequence enrollment |
| Anthropic API | Haiku (extraction/classification), Sonnet (email generation) |
| Apify | LinkedIn job scraping, LinkedIn profile scraping, content scraping |
| Crawl4AI | Web scraping (self-hosted) |
| DataForSEO | Domain enrichment, SERP fallback |
| Mention.com | Brand mention tracking |
| Chrome DevTools MCP | Apollo.io UI automation |
| Exa | Web search for GTM research |

## Self-Improvement
At the start of each session, read `lessons.md` in this directory. After each session, document mistakes, false assumptions, and corrections in `lessons.md`.
