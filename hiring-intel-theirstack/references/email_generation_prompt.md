# Email Generation Prompt

Used by `generate_emails.py` (Claude Sonnet) to create 3 complete 1:1 emails per company from extracted intel + product truth table.

## Philosophy

**"The list IS the message" - adapted for 1:1 personalization.**

Each company gets 3 fully unique emails (not templates with variables). The intel from their job posting is woven naturally into the email so it feels like deep industry expertise, not "I saw you're hiring."

## Prompt Architecture: 3 Sections

The prompt is structured in three sections to anchor the model on intel first, constrain claims second, and enforce structure third:

### Section 1: "What I Know About Them" (Intel — primary material)
- Company details, JD intel, pain signals, tools, team context
- This section comes FIRST in the prompt (model anchors on what it sees first)
- Every email must be anchored in a SPECIFIC detail from this section
- Includes mirror-back language rule (use prospect's own JD vocabulary)
- Includes company context rule (only use when it adds info the JD doesn't have)
- Includes competitor tools guidance (reference if known, don't guess if unknown)

### Section 2: "What I Can Claim" (Product truth table + case studies — constraint)
- Product capabilities from `references/product_truth_table.md`
- Case studies injected dynamically by `select_case_studies()`
- Tool classification (direct competitors vs adjacent tools)
- What we do NOT do
- Acts as a hard constraint: only capabilities listed here can be claimed

### Section 3: Email Structure (Format + identity + rules)
- Who you are (Agorapulse identity)
- Who you're writing to (VP/CMO, not the IC being hired)
- Core logic ("the list IS the message")
- Assume they already have a tool (200+ employee companies)
- 3-email structure with paragraph-level guidance
- Writing style rules
- Banned patterns

## Hard Rules (Non-Negotiable)

| Constraint | Specification |
|-----------|--------------|
| Email 1 length | STRICT max 120 words (count every word including merge tags) |
| Email 2 length | STRICT max 80 words |
| Email 3 length | STRICT max 120 words |
| Paragraph structure | Max 2 lines per paragraph |
| Questions | Exactly ONE question mark per email |
| Dashes | Regular dash only (never em dash) |
| Exclamation marks | Forbidden |
| Emojis | Forbidden |
| Merge tags | `{{firstName}}`, `{{companyName}}` only |
| Feature-listing | ONE capability per email, described by outcome not mechanics |

## Three-Email Structure

### Email 1: The Why Email
- **New thread** with subject line (2-4 words, segment-relevant)
- **Paragraph 1 - Their world**: What the JD reveals about their situation (2-3 sentences max)
- **Paragraph 2 - Who you are + why it matters**: "I'm with Agorapulse — [one sentence about outcome]" (2 sentences max)
- CTA: Soft interest check (e.g., "Worth a quick look?")

### Email 2: The Proof Point
- **New thread** with subject line (different angle from Email 1)
- Lead with case study — explicitly an Agorapulse customer
- ONLY verbatim facts from the case study (no rephrasing, no additions)
- Bridge back to their situation as a question

### Email 3: The Breakup
- **New thread** with new subject line (different angle)
- Opens with "Last one from me." + observation about a FUNDAMENTALLY DIFFERENT business challenge than Email 1 (not the same theme from a different angle — a genuinely distinct problem)
- Bridges to Agorapulse outcome (mentions Agorapulse or "we")
- CTA: Easy out/easy in, framed as a question

## CTA Style

- Email 1: Soft interest check (e.g., "Worth a quick look?")
- Email 2: Bridge question connecting case study to their situation
- Email 3: Easy out/easy in as a question (e.g., "If timing's off, no worries - but would it help to see how teams set this up?")
- NEVER mention a specific product name in the CTA
- NEVER include calendar links or URLs

## Sender Identity

- Sender works at Agorapulse (social media management platform)
- Email 1: Mention Agorapulse by name ("I'm with Agorapulse")
- Email 2: Agorapulse appears via case study ("switched to Agorapulse")
- Email 3: "We" is sufficient — reader knows who's writing by then
- Intro must be ONE sentence, no feature list

## Audience Assumption

Writing to the MANAGER of the person being hired — VP Marketing, Head of Marketing, CMO. NOT to the IC in the JD. The JD reveals team challenges; emails address the budget owner.

**200+ employee companies already have a social media management tool.** The angle is "you're scaling into something your current setup wasn't designed for" — NOT "you need a tool." Even "build from scratch" in JDs refers to programs/markets, not tooling.

## Mirror-Back Language Rule

Use the prospect's own words from the JD. Match their vocabulary exactly:
- JD says "scale community programs" → write "scaling community programs" (not "grow your online presence")
- JD says "content calendars" → use "content calendars" (not "editorial planning")

## Banned Patterns

| Pattern | Why |
|---------|-----|
| "X means Y" / "which means" | Lazy connector |
| "our" + feature name | Feature-pitching with possessive framing |
| "Most teams I work with" / "From what I've seen" | Sender is not an observer |
| "browser tabs" / "browser-switching" / "platform-hopping" | Cliche |
| "drowning in" / "juggling" / "chaos" / "overwhelm" | Melodramatic |
| Starting with "Hi" | Use `{{firstName}},` directly |
| "that's a lot of" / "that's hard when" | Filler |
| Feature-listing (3+ capabilities in a row) | Product datasheet, not email |
| "one inbox/place/workspace/view/system/platform" | Generic, says nothing about why it matters |
| "a single workspace/platform/tool" | Same as above |
| "eliminated browser-switching chaos" | Hallucinated case study fact |
| "most [X] underestimate/end up" | Fake authority |
| "[Product] is a [category]. It [verb]" | Product-brief phrasing |

**Post-generation enforcement**: `generate_emails.py` runs a deterministic regex scan on every email body after generation. If any banned phrase is detected, the email is rejected and regenerated (up to 2 retries). After max retries, emails are returned with a warning status.

## Case Studies

Injected dynamically based on company's `industry` field via `select_case_studies()`:

| Vertical | Case Studies Selected |
|----------|-----------|
| Agency | **Adtrak** (UK, switched from Hootsuite, doubled team 3→7, 100+ profiles) + **Digital Butter** (SA, switched from Buffer, clients +300% sales) |
| E-commerce / Retail | **Homefield Apparel** (US, replaced manual Excel tracking, now proves organic ROI) + **Digital Butter** |
| Education | **Nexford University** (US, switched from Hootsuite, 75% less reporting time) + **Homefield Apparel** |
| B2B SaaS / Tech | **Nexford University** + **Digital Butter** |
| Enterprise | **Nexford University** + **Digital Butter** |
| Unknown | **Homefield Apparel** + **Nexford University** + **Digital Butter** (all three) |

**Case study verbatim rule**: Only facts stated exactly in the case study can be used. No rephrasing, no additions, no invented details.

## Multi-Posting Intel Merge

When a company has multiple job postings, `merge_company_intel()` combines intel from all postings:
- Lists (pain_signals, tools, etc.) are merged and deduped
- Highest seniority and urgency are used
- Team context includes job count signal (e.g., "hiring 3 social media roles")
- Single-posting companies use intel as-is

## Inputs Required

1. **Product Truth Table** (from `references/product_truth_table.md`): Features, pricing, positioning, limitations
2. **Extracted Intel** (from extract_intel.py): Company-specific signals (merged if multi-posting)
3. **Company Website Summary** (from Step 2 homepage scraping): Brief description of what the company does
4. **Case Studies** (selected by industry): Verified customer stories

## Data Flow

```
Step 2 output (job_descriptions.json)
  └── company_context: homepage content or metadata
        ↓
Step 3 output (intel_extracted.json)
  ├── company_context: passed through
  └── jobs[].intel: extracted fields per JD
        ↓
Step 4 (generate_emails.py)
  ├── merge_company_intel(): combines intel from all postings
  ├── load_product_truth_table(): reads references/product_truth_table.md
  ├── select_case_studies(): picks industry-matched case studies
  └── Prompt receives: intel FIRST (Section 1) + truth table + case studies (Section 2) + structure (Section 3)
```

## Self-Check Rules (12 total)

The prompt includes 12 self-check rules the model must verify before returning:

1. Exactly one `?` per email
2. No paragraph > 2 lines
3. No invented statistics (only verbatim from case studies/truth table)
4. Anchored in specific Section 1 detail
5. Only claims capabilities from Section 2
6. No banned patterns (word-by-word scan)
7. Email 2 case study facts are verbatim
8. No feature-listing (max 1 verb about product per sentence)
9. BDR credibility (sounds like a person, not a product page)
10. Value check (Email 1 para 1 has insight, not just restatement)
11. Word count verification (120/80/120)
12. Email 3 different challenge verification

## Model & Cost

- **Model**: `claude-opus-4-6` (highest quality for email writing)
- **Cost**: ~$0.01 per company (3 emails, may retry once on banned phrase violation)
- **Latency**: ~10-15s per company
