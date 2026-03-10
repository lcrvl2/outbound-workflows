# Role Filter Prompt

Used by `filter_roles.py` (Claude Haiku) to classify ambiguous job titles that regex couldn't confidently categorize.

## Context

We're building a list of target companies from a champion's work history. We only care about companies where the champion held a **marketing, social media, content, or communications role** - because these are the companies most likely to need social media management tools.

Roles in finance, engineering, HR, legal, etc. are excluded because those companies hired the champion for non-relevant work.

## Two-Pass System

**Pass 1 (Regex - handled in code, not by this prompt):**
- Auto-INCLUDE: titles containing `social media`, `community`, `content`, `marketing`, `digital`, `communications`, `brand`, `growth`, `cmo`
- Auto-EXCLUDE: titles containing `intern`, `stagiaire`, `cfo`, `cto`, `cio`, `finance`, `legal`, `counsel`, `engineer`, `developer`, `hr`, `human resources`, `accountant`, `advisory`, `board member`, `investor`

**Pass 2 (This prompt - Haiku, only for ambiguous titles):**

## Prompt

You are classifying job titles to determine if they are relevant to social media management or marketing.

A title is RELEVANT if the person likely managed or influenced social media, content, or digital marketing activities. A title is EXCLUDED if it's clearly unrelated (sales, operations, admin, etc.) or too generic to indicate marketing involvement.

Classify each title below as RELEVANT or EXCLUDED. Return ONLY valid JSON.

```
{
  "classifications": [
    {"title": "...", "verdict": "RELEVANT" | "EXCLUDED", "reason": "brief reason"}
  ]
}
```

Rules:
- RELEVANT: marketing, social media, content, communications, PR, brand, digital, community management, growth roles
- RELEVANT: C-level/VP only if marketing-adjacent (CMO, VP Marketing, Chief Communications Officer)
- EXCLUDED: pure sales, operations, admin, customer success, product, engineering, finance, HR, legal
- EXCLUDED: generic titles like "Manager", "Director", "Consultant" without marketing context
- EXCLUDED: "Account Manager", "Project Manager", "Business Development" (these are sales/ops)
- EDGE CASES: "Head of Strategy" → EXCLUDED (too generic). "Digital Strategist" → RELEVANT. "Creative Director" → RELEVANT.

Titles to classify:
{titles_json}

## Cost Model

- Regex handles ~70-80% of titles (free, instant)
- Haiku handles remaining ~20-30% at ~$0.0003 per batch
- Titles are batched per champion (one API call per champion's ambiguous titles)
