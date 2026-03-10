# Intel Extraction Prompt

Used by `extract_intel.py` (Claude Haiku) to extract structured hiring intelligence from raw job descriptions + company website context.

## Fields Extracted

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `job_title` | string | Exact title from the posting | "Senior Social Media Manager" |
| `seniority` | enum | junior, mid, senior, lead, director, vp, c-level | "senior" |
| `responsibility_summary` | string | 1-2 sentence summary of key responsibilities | "Own social strategy across 5 platforms, manage 2 reports" |
| `tools_mentioned` | array | All tools, platforms, software mentioned | ["Hootsuite", "Canva", "Google Analytics"] |
| `competitor_tools` | array | Only social media management platform competitors | ["Hootsuite", "Sprout Social"] |
| `pain_signals` | array | Inferred pain points from the JD context | ["No analytics process", "Inconsistent posting cadence"] |
| `team_context` | string | Team size, reporting structure, hire type | "First dedicated hire, reports to CMO" |
| `hiring_urgency` | enum | low, medium, high | "high" |
| `key_metrics` | array | KPIs or metrics mentioned | ["engagement rate", "follower growth", "ROI tracking"] |
| `platforms_managed` | array | Social platforms they manage | ["Instagram", "LinkedIn", "TikTok"] |

## Company Website Context

When available (scraped in Step 2), the company's homepage content is injected into the extraction prompt as a `Company Website Context` section before the job description. This helps Claude:
- Better understand the company's product/market
- Infer more relevant pain signals (e.g., a design tool company managing many social platforms)
- Identify industry-specific context that the JD alone may not reveal

For JS-heavy SPAs where full page content isn't available, metadata (title, description, keywords) is used as fallback.

## Pain Signal Inference Rules

The extraction prompt instructs Claude to INFER pain signals from context (both the JD and company website), not just extract stated problems:

- "First dedicated hire" → No existing process, likely ad-hoc social media management
- "Manage 5+ platforms" → Struggling with scale, likely no unified tool
- "Build from scratch" → No existing strategy or playbook
- "Report to CMO directly" → High visibility role, strategic importance
- "Inconsistent posting" or "content calendar" → Current posting is reactive, not planned
- "Track ROI" or "analytics" → Currently can't measure social media impact
- "Cross-functional collaboration" → Siloed teams, content bottlenecks
- "Agency transition" → Moving from outsourced to in-house, need tools

## Competitor Tool Detection

The prompt specifically flags tools that compete with social media management platforms:

**Direct Competitors** (we replace these): Hootsuite, Sprout Social, Buffer, Iconosquare, Sprinklr, Later, Planable, Sendible, SocialBee, Loomly, Publer, SocialFlow, Khoros, Emplifi, Brandwatch, Meltwater, Falcon.io, Facelift, Oktopost, Zoho Social, eClincher, SocialPilot, Crowdfire, CoSchedule, Statusbrew, Vista Social, Metricool, Swello, Kontentino

**Adjacent Tools** (not flagged as competitor): Manychat, Chatfuel, Asana, Trello, Monday, Notion, Slack, Canva, Figma, Adobe, HubSpot, Salesforce, Pipedrive, Mailchimp, Klaviyo, Brevo, Google Analytics, Semrush, Ahrefs, CapCut, Descript

## Post-Processing

After extraction, `filter_hallucinated_tools()` applies two filters:
1. **Hallucination filter**: Removes tool names from `tools_mentioned` and `competitor_tools` that don't appear verbatim in the JD text. Prevents the model from guessing specific tools from generic mentions like "social media management tools."
2. **Reclassification**: Moves non-direct-competitor tools from `competitor_tools` to `tools_mentioned`. Only tools in the `DIRECT_COMPETITORS` set stay as competitor tools.

Our own product (Agorapulse) is always filtered out.

## Model & Cost

- **Model**: `claude-haiku-4-5-20251001` (fast, cheap)
- **Cost**: ~$0.001 per extraction
- **Latency**: ~2-3s per JD
