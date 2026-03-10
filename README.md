# Outbound Workflows

B2B outbound automation toolkit. Each subfolder is a standalone skill — a Claude Code workflow with its own `SKILL.md`, scripts, and references. Skills chain together to go from ICP research to sequence-ready emails pushed to Apollo.io.

## Skills

### Research & Strategy

| Skill | What it does | Key APIs |
|-------|-------------|----------|
| [`gtm-playbook`](gtm-playbook/) | Analyze a website URL → generate a GTM playbook with verticals, personas, pain points, case study angles | Exa, Claude |
| [`targeting-ideas`](targeting-ideas/) | GTM playbook → 20 B2B campaign targeting ideas with company criteria and persona signals | Claude |
| [`write-sequence`](write-sequence/) | Targeting segment → 3-email cold sequence for the entire segment | Claude |

### List Building

| Skill | What it does | Key APIs |
|-------|-------------|----------|
| [`hiring-intel`](hiring-intel/) | Find companies hiring for social media roles → scrape JDs → generate 1:1 personalized emails → push to Apollo | Apollo, Apify, Crawl4AI, Claude |
| [`hiring-intel-theirstack`](hiring-intel-theirstack/) | Same as hiring-intel using TheirStack API for job discovery | TheirStack, Apollo, Anthropic |
| [`Mentions-enrichment`](Mentions-enrichment/) | Weekly pipeline: fetch competitor brand mentions → enrich company domains → import to Apollo | Mention.com, DataForSEO, Apollo |
| [`reverse-champions`](reverse-champions/) | Closed-won contacts → scrape LinkedIn work history → find previous employers → warm outbound | Apollo, Apify, Claude |
| [`churned-user-detector`](churned-user-detector/) | Churned user CSV → enrich LinkedIn → detect job changes → build win-back campaign lists | Apollo, DataForSEO, Apify, Claude |
| [`competitor-followers`](competitor-followers/) | LinkedIn competitor followers → ICP filter → find personas → output Apollo-ready contact CSVs | Apify, Apollo, Claude |
| [`linkedin-profile-personalizer`](linkedin-profile-personalizer/) | LinkedIn profile → extract signals → personalized outreach hooks | Apify, Claude |
| [`linkedin-company-analytics`](linkedin-company-analytics/) | Company LinkedIn page → scrape analytics and post data | Apify |
| [`Social-profile-discovery`](Social-profile-discovery/) | Company websites → discover social profiles across 9 platforms | Crawl4AI, DataForSEO |

### Content & Scraping

| Skill | What it does | Key APIs |
|-------|-------------|----------|
| [`linkedin-content-scraper`](linkedin-content-scraper/) | LinkedIn profile → formatted `.md` archive of posts | Apify |

### Apollo UI Automation (Chrome DevTools MCP)

| Skill | What it does |
|-------|-------------|
| [`apollo-lead-processor`](apollo-lead-processor/) | Apollo list → select contacts → change owner → add to sequence → push to Salesforce → suppression |
| [`apollo-job-changer-processor`](apollo-job-changer-processor/) | Accept job change updates across EN/FR/DACH lists → enrich → push to Salesforce + campaigns |

### Reference

| Resource | What it is |
|----------|-----------|
| [`knowledge-base/`](knowledge-base/) | Outbound playbook (cold email, signals, discovery, objections) + 12 master sales prompts |

---

## Typical Workflow Chain

```
gtm-playbook → targeting-ideas → write-sequence #N
                               → hiring-intel (with playbook)
                               → reverse-champions (with playbook)
```

1. **GTM Playbook** generates personas, verticals, pain points for a product
2. **Targeting Ideas** creates 20 segment ideas from the playbook
3. **Write Sequence** turns segments into email sequences
4. **Apollo Lead Processor** enrolls contacts into sequences via UI automation

---

## Setup

### Prerequisites

- Python 3.10+
- [Claude Code](https://claude.ai/code) (for Claude-triggered skills)
- Chrome with remote debugging enabled (for Apollo UI automation skills)

### Installation

```bash
git clone https://github.com/lcrvl2/outbound-workflows.git
cd outbound-workflows

# For each skill you want to use:
cd <skill-folder>
cp .env.example .env       # fill in your API keys
pip install -r requirements.txt
```

### Chrome (Apollo automation only)

```bash
open -a "Google Chrome" --args --remote-debugging-port=9222
```

---

## API Keys

| Key | Used by |
|-----|---------|
| `APOLLO_API_KEY` | hiring-intel, hiring-intel-theirstack, reverse-champions, churned-user-detector, competitor-followers |
| `ANTHROPIC_API_KEY` | hiring-intel, hiring-intel-theirstack, reverse-champions, churned-user-detector, gtm-playbook, write-sequence, competitor-followers |
| `APIFY_TOKEN` | hiring-intel, reverse-champions, churned-user-detector, competitor-followers, linkedin-content-scraper, linkedin-company-analytics |
| `DATAFORSEO_USERNAME` / `DATAFORSEO_PASSWORD` | Mentions-enrichment, reverse-champions, churned-user-detector, Social-profile-discovery |
| `MENTION_API_TOKEN` / `MENTION_ACCOUNT_ID` | Mentions-enrichment |
| `THEIRSTACK_API_KEY` | hiring-intel-theirstack |
| `CRAWL4AI_BASE_URL` | hiring-intel, reverse-champions, Social-profile-discovery |

Each skill has a `.env.example` listing only the keys it needs.

---

## Email Writing Rules

All sequence-generating skills follow these rules:

- Max 80 words per email, 2 lines per paragraph
- ONE question mark per email
- No em dashes, no exclamation marks, no signatures, no emojis
- No "I saw that you..." / "Love what you're building" / generic AI phrases
- Merge tags: `{{firstName}}`, `{{companyName}}`
- Signal-based: reference what the signal MEANS, not the signal itself
