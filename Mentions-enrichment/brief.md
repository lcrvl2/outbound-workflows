# URL Shortener Outreach — Brief

## Context

Some brands publicly share links that use competitor shorteners (ow.ly, spr.ly, buff.ly, brnw.ch). This is a light intent signal that they use — or have used — a social media management tool.

The signal is noisy (ow.ly / buff.ly especially), so the campaign only works with hard ICP filtering before any outreach.

We track 4 competitors via Mention.com, enriching each mention source against DataForSEO + Apollo weekly. The detection → enrichment → list-push pipeline runs automatically every Monday morning.

## Objective

Use competitor-shortener signals to:
- Start conversations with ICP-fit companies (meetings → SQL)
- Tag the competitor signal in Salesforce for future plays and segmentation

## How Detection Works

Mention.com alerts track every public page that references the shortener domains. Each mention has a `source_name` (the website or social profile publishing the link) and a `reach` value. We filter out low-reach sources and map `source_name` → company domain → Apollo account.

4 alerts, 1 per competitor:

| Competitor | Shortener | Alert ID | Cron |
|------------|-----------|----------|------|
| Hootsuite  | ow.ly     | 2718028  | Mon 7:00 AM |
| Sprinklr   | spr.ly    | 2718708  | Mon 7:15 AM |
| Buffer     | buff.ly   | 2718710  | Mon 7:30 AM |
| Brandwatch | brnw.ch   | 2718709  | Mon 7:45 AM |

## Pipeline (live, runs weekly)

Built in Python — no n8n needed.

1. **Fetch** — Mention.com API pulls last 7 days of mentions per competitor
2. **Enrich** — DataForSEO domain lookup ($0.0006/company). New companies only — master file prevents re-enrichment
3. **Apollo** — Bulk create accounts → org enrichment (real employee counts) → filter by size + exclude current clients
4. **Unqualified** — Companies with reach that didn't pass Apollo filters, saved for manual review
5. **Cleanup** — Temp files deleted

Output per competitor:
- `apollo-accounts/[c]_apollo.csv` — qualified accounts, ready for sequencing (>200 employees, not current client)
- `unqualified/[c]_unqualified_DATE.csv` — had reach but didn't pass filters
- `logs/run_history.jsonl` — per-run stats (mentions fetched, companies enriched, qualified count, master total)

## ICP Filter

Currently applied at Apollo step:
- **Min employees:** 200 (filters out most noise from ow.ly / buff.ly)
- **Exclude:** "Current Client" account stage in Apollo

Pending confirmation:
- Geo / segment rules
- Whether to raise the floor for ow.ly/buff.ly specifically (recommend starting with spr.ly / brnw.ch — higher signal quality, smaller volume)

## Contacts to Enrich

Per qualified account, find via Apollo People Search:
- Primary: Social Media Lead / Head of Social
- Secondary: VP Marketing / Demand Gen

Not automated yet — manual Apollo search or Apollo sequence enrollment from the apollo-accounts CSV.

## Salesforce Tagging

Not yet implemented. Signal should be logged as a competitor tag on the Apollo/SF account so future plays can segment by competitor used.

Pending:
- Define field or tag in Salesforce for competitor signal (e.g., "competitor_shortener: spr.ly")
- Log signal at time of outreach, not at detection — avoid polluting accounts that never respond

## Messaging

**Core angle:** "I noticed {{companyName}} is sharing links via [shortener]. If link tracking matters to you, Agorapulse's shortener ties social posts directly to revenue — not just shorter URLs."

**Guidelines:**
- Be direct about the signal ("saw links using [domain]") — don't explain how you detected it
- Value prop: ROI tracking / attribution / measurable outcomes — not feature list
- Ask a qualifying question before pitching a call
- Low-friction CTA: quick walkthrough or example of the ROI view

### Email 1 — New Thread

**Subject:** Your links on [platform]

> {{firstName}},
>
> Noticed {{companyName}} is using [shortener] links in social posts.
>
> If you're tracking social ROI, Agorapulse links go a step further — they tie social content to measurable results, not just shorter URLs.
>
> Are you currently able to attribute clicks or conversions back to specific posts?

### Email 2 — Reply to Email 1

> {{firstName}},
>
> To make it concrete: Adtrak replaced their previous SMM tool with Agorapulse and scaled from 3 to 7 social managers running 100+ profiles — without adding complexity.
>
> Here's the full story: [Adtrak case study link]

### Email 3 — New Thread

**Subject:** Social ROI at {{companyName}}

> {{firstName}},
>
> Most marketing teams I talk to have the same blind spot — they know social is working but can't put a number on it when leadership asks.
>
> Agorapulse has a built-in ROI report that ties posts directly to revenue. No spreadsheets.
>
> No worries if {{companyName}} already has this covered. If not, happy to show you what it looks like.

### Sequence Timing

| Step | Day | Thread | Subject |
|------|-----|--------|---------|
| Email 1 | Day 0 | New | Your links on [platform] |
| Email 2 | Day 3 | Reply to 1 | — |
| Email 3 | Day 7 | New | Social ROI at {{companyName}} |

## Next Steps

- [ ] Confirm ICP floor per competitor — recommend higher threshold for ow.ly / buff.ly (200 may not be enough)
- [ ] Decide on geo / segment exclusions
- [ ] Define Salesforce field / tag for competitor signal
- [ ] Start with spr.ly + brnw.ch before scaling to ow.ly (lower noise)
- [ ] Enroll apollo-accounts CSV contacts into Apollo sequence
- [ ] Brief BDRs: reply routing, discovery call framing
- [ ] Track outcomes by shortener domain (signal quality varies)
