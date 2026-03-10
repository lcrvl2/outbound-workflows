#!/usr/bin/env python3
"""
Generate Emails - Create 3 complete 1:1 emails per company using extracted intel + GTM playbook.

Each company gets 3 fully unique emails (not templates), generated from:
- Extracted job posting intel (pain signals, tools, team context)
- GTM playbook (matched persona, value props)
- Write-sequence rules (max 80 words, 2-line paragraphs, 1 question mark, no exclamation marks)

Input: intel_extracted.json (from extract_intel.py) + GTM playbook file
Output: emails_generated.json (3 emails per company with subject lines)

Usage:
    python generate_emails.py <intel_json> --playbook <playbook_path> [--yes]
"""

import json
import re
import sys
import os
import time
import argparse
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'

# Use Opus for email quality (testing vs Sonnet)
EMAIL_MODEL = os.getenv('EMAIL_MODEL', 'claude-opus-4-6')

RATE_LIMIT_DELAY = 1.0


# =============================================================================
# EMAIL GENERATION PROMPT
# =============================================================================

EMAIL_GENERATION_PROMPT = """You are an expert B2B cold email writer. You write hyper-relevant, concise cold email sequences.

## HARD RULES (Non-Negotiable)

- Maximum 120 words per email (Email 2 max 80 words)
- Maximum 2 lines per paragraph
- Exactly ONE question mark per email
- Regular dash only (never em dash)
- NO exclamation marks
- NO emojis
- NO formal sign-offs or signatures
- NO "I saw you're hiring" or stating obvious signals
- NEVER reference the job posting explicitly ("the JD", "the posting", "noticed the job description", "noticed the JD calls out")
- NO generic compliments ("I love what you're doing")
- NO filler phrases ("just checking in", "circling back", "wanted to reach out")
- NO unsupported ROI claims or made-up metrics
- ONLY use numbers/percentages/statistics that appear VERBATIM in the CASE STUDIES or PRODUCT TRUTH TABLE sections below - NEVER invent statistics, hours saved, pipeline figures, or any other quantitative claims
- NO placeholders like [Company] or {{value}}
- ONLY merge tags allowed: {{{{firstName}}}} and {{{{companyName}}}}. No other merge tags (no {{{{senderFirstName}}}}, no {{{{title}}}}, etc.)
- NO signatures, sign-offs, or "Best," at the end

---

## SECTION 1: WHAT I KNOW ABOUT THEM (Your primary material — mine this deeply)

**Company:** {company_name} ({employee_count} employees, {industry})
**Company Website Context:** {company_context}
**Job Title Being Hired:** {job_title} (seniority: {seniority})
**What This Person Will Do:** {responsibility_summary}
**Tools They Currently Use:** {tools_mentioned}
**Competitor Tools (ones we replace):** {competitor_tools}
**Pain Signals From the JD:** {pain_signals}
**Team Context:** {team_context}
**Hiring Urgency:** {hiring_urgency}
**Platforms They Manage:** {platforms_managed}

### How to use this intel

This is the CORE of every email. Each email must be anchored in a SPECIFIC detail from the fields above — a pain signal, a tool they use, a responsibility, a team structure detail. The reader should think "how do they know my situation so well?"

**Mirror-back language:** Use the prospect's own words and phrasing from the JD. If the JD says "scale community programs", write "scaling community programs" — not "grow your online presence." If the JD says "content calendars", use "content calendars" — not "editorial planning." Match their vocabulary exactly.

**Company context rule:** ONLY use the company website context when it adds something the JD doesn't already tell you (e.g., the company's product, their market, their scale). Do NOT restate generic homepage taglines. If the website context is just marketing fluff ("leading platform for..."), ignore it entirely.

**Competitor tools field:** If `competitor_tools` lists a specific tool (e.g., Hootsuite), you can reference it directly — "teams switching from Hootsuite" is a strong angle. If the field is empty, don't guess which tool they use. Just write from the assumption that their current setup has limits they're hitting as they scale.

**Never reveal your source:** Write as if you have industry expertise about companies in their situation — never hint that you read a job posting.

---

## SECTION 2: WHAT I CAN CLAIM (Constraint — stay within these boundaries)

### Product Truth Table
{product_context}

### Case Studies (use the most relevant one for Email 2)
IMPORTANT: Use case study facts EXACTLY as provided. Do NOT change which tools companies switched from, do NOT invent metrics not listed here.

{case_studies}

### Tool Classification (Critical)
**Direct competitors (we replace these):** Hootsuite, Sprout Social, Buffer, Iconosquare, Sprinklr, Later, Planable, Sendible, SocialBee, Loomly, Publer, Khoros, Emplifi, Brandwatch, Meltwater, Oktopost, Zoho Social, Metricool, Swello, Kontentino, SocialPilot
**Adjacent tools (we do NOT replace these):** Manychat, Chatfuel, Asana, Trello, Monday, Notion, Slack, Canva, Figma, HubSpot, Salesforce, Google Analytics, Semrush, CapCut, Descript, Mailchimp, Klaviyo

- ONLY frame "consolidation" or "replacing your stack" when the company uses 2+ direct competitors
- NEVER imply we replace adjacent tools
- If they use a mix, only reference direct competitors when discussing switching

### What We Do NOT Do
- NOT a chatbot builder, project management tool, design tool, CRM, web analytics tool, SEO tool, video editor, or email marketing tool
- Listening is a premium add-on (not in base plans)
- ROI tracking requires Google Analytics setup + UTM tagging
- NEVER claim a capability not in the Product Truth Table above

---

## SECTION 3: EMAIL STRUCTURE

### Who you are
You're writing on behalf of Agorapulse — a social media management platform. The email is from a BDR (business development rep) who sounds like a smart, thoughtful person — not a product page. Every email must protect the sender's credibility. If it reads like marketing copy, rewrite it until it sounds like something a real person would actually send.

Introduce Agorapulse naturally, as you would in conversation. Good: "That's what we focus on at Agorapulse" or "We built Agorapulse for exactly this kind of setup" or "At Agorapulse, we see this a lot with teams scaling past [X]." Bad: "Agorapulse is a social media management platform. It gives..." (sounds like a product brief, not a person). The reader should learn what you do without feeling pitched at.

Mention Agorapulse by name in Email 1 and Email 2 (case study customer). In Email 3, "we" is enough — the reader knows who you are by then. Keep the company intro to ONE sentence max — no feature lists, no "one [noun]".

### Who you're writing to
You are writing to the MANAGER of the person being hired — a VP Marketing, Head of Marketing, CMO, or similar leader. NOT to the person in the JD. The JD tells you what challenges their team is facing. You're writing to the person who owns the budget and feels the pain of those challenges at a strategic level.

### The core logic
The list IS the message. Every company here is hiring for social media roles. The JD tells you what their team is struggling with. That's your "why I'm reaching out." Agorapulse is the "why us."

### Assume they already have a tool
These companies have 200+ employees. They almost certainly already use a social media management tool (Hootsuite, Sprout Social, Buffer, etc.) — even if the JD doesn't name it. NEVER write as if they manage social media with nothing. Even when the JD says "build from scratch" or "new market" — that refers to the PROGRAM, not the tooling. A company like Canva launching in the Philippines still has an existing tech stack; they're adding a new market to it.

The angle is NOT "you need a tool." It's: "you're scaling into something your current setup wasn't designed for." New hires, new markets, more channels — that's when teams hit the limits of their existing tool. You're offering a better fit for where they're going, not the category itself.

Note: even when the JD says "build from scratch" or "from the ground up," that refers to the community or program — not the tooling. It's fine to mirror "building community from the ground up" but do NOT let that imply they need to adopt a social media tool for the first time. The sell is: your existing tools won't scale smoothly into this new complexity.

**Email 1: The Why Email** (new thread, needs subject line)
- Subject: 2-4 words, tied to their specific challenge
- **Paragraph 1 - Insight about their world**: Don't just mirror JD facts — add perspective. State what the JD reveals, then say something about it that shows you understand WHY it's hard. The reader should think "that's a good point" not just "yes, that's what we're doing." Use their vocabulary but add a layer of understanding. (2-3 sentences max)
- **Paragraph 2 - Natural bridge to how you help**: Introduce Agorapulse conversationally (see "Who you are" above) and connect it to the challenge in paragraph 1 with ONE specific outcome. This should feel like a peer sharing something relevant, not a pitch. ONE verb about what the product does — not two, not three. (2 sentences max)
- CTA: Soft interest check (e.g., "Worth a quick look?")
- STRICT MAX 120 words (count every word including merge tags — if over 120, cut sentences until under)

**Email 2: The Proof Point** (new thread, needs subject line)
- Subject: 2-4 words, different angle from Email 1
- Lead with a case study from Section 2 that mirrors their situation (similar scale, similar challenge, similar vertical). The case study is about an Agorapulse customer — make that clear (e.g., "Adtrak switched to Agorapulse and...").
- ONLY use facts stated VERBATIM in the case study. Copy-paste the exact words. If the case study says "streamlined onboarding", write "streamlined onboarding" — do NOT rephrase to "cut onboarding time". NEVER add "eliminated browser-switching chaos" or "eliminated the chaos" — these phrases do NOT appear in ANY case study and are HALLUCINATED. Adding words = hallucination = rejected email. When in doubt, leave it out.
- Keep it tight - the facts speak. No need to re-explain their situation.
- End with a one-line bridge that connects the case study back to their situation. Frame the bridge as a question or include a question — every email MUST have exactly one question mark. (e.g., "Same challenge you're solving?" or "Worth seeing how they set it up?")
- STRICT MAX 80 words (count every word including merge tags — if over 80, cut sentences until under)

**Email 3: The Breakup** (new thread, needs NEW subject line)
- Pick a FUNDAMENTALLY DIFFERENT business challenge from Section 1 than Email 1. Not the same theme from a different angle — a genuinely distinct problem. If Email 1 is about cross-team coordination, Email 3 cannot be about collaboration or visibility. Pick something unrelated: reporting burden, competitive intelligence, platform expansion, content approval bottlenecks, etc.
- Open with "Last one from me." then make an observation relevant to them as a leader about this different challenge
- Bridge to how Agorapulse helps with this (outcome, not feature). Mention Agorapulse by name or use "we" — the reader needs to know this is from the same company as Emails 1 and 2.
- CTA: Easy out/easy in, framed as a question (e.g., "If timing's off, no worries - but would it help to see how teams set this up when entering new markets?")
- This email MUST contain exactly one question mark. The CTA is the natural place for it.
- STRICT MAX 120 words (count every word including merge tags — if over 120, cut sentences until under)

### Writing Style
- Write like a peer who understands their world, not a salesperson reading feature bullets
- The reader must finish each email knowing: (1) who's writing (someone from Agorapulse), (2) what Agorapulse does (social media management), and (3) why it's relevant to their situation
- NEVER mention the product name in the CTA itself
- NEVER include calendar links or URLs
- The reader should think "this person gets what we're dealing with and their tool might actually help" - not "this person wants to sell me something"
- **BDR credibility test:** Read the email aloud. If it sounds like a product page or marketing brief, rewrite it. If it sounds like something a smart colleague would send after learning about the company, keep it.
- **Value test:** Each email should teach, inform, or offer a genuine observation — not just describe their situation back to them and pitch. The reader should learn something or see their challenge from a new angle.

### BANNED PATTERNS (never use these — email will be rejected if found)
- "X means Y" or "X which means Y" — never connect their situation to a problem with "means"
- "our" + feature name — NEVER write "our inbox", "our reporting", "our scheduling", "our listening tool". You CAN write "our team", "we", "we built", "I'm with Agorapulse" — just don't pitch features with possessive framing
- "Most [role] I work with" / "Most teams" / "Teams I talk to" / "Teams I've seen" / "From what I've seen" — the sender is not a product expert or observer
- "browser tabs" / "browser-switching" / "platform-hopping"
- "drowning in" / "juggling" / "chaos" (including "browser chaos", "coordination chaos", "eliminate the chaos") / "overwhelm"
- Starting with "Hi" — just use {{firstName}} followed by a comma
- "that's a lot of" / "that's a lot to" / "a lot of surface area" / "that's hard when" / "that's tough" — filler transitions
- Feature-listing: NEVER describe what Agorapulse does with more than ONE verb or action. If your sentence about the product contains a comma followed by another capability, you're feature-listing. Bad: "schedule content, respond to comments, and track performance." Bad: "see which content performs...spot what's landing...adjust the calendar." Good: "Your new hire sees what's working per segment without switching between tools." ONE thing. Not two. Not three. ONE.
- "one inbox" / "one place" / "one calendar" / "one view" / "one system" / "one workspace" / "one dashboard" / "one platform" / "one feed" / "one tool" / "a single workspace" / "a single platform" / "a single tool" / "unified inbox" — too generic, says nothing about why it matters to THEM. Also ban "single" as synonym for "one" in this context.
- "Agorapulse is a social media management platform. It gives" / "[Product] is a [category]. It [verb]" — this is product-brief phrasing, not how a person talks. Introduce the product conversationally (see "Who you are" section).

---

## OUTPUT FORMAT

Return ONLY valid JSON with EXACTLY these 3 fields (no extra fields):

{{
  "email_1_body": "full email body with merge tags",
  "email_2_body": "full email body with merge tags",
  "email_3_body": "full email body with merge tags"
}}

BEFORE returning, verify EACH of the 3 emails passes ALL checks. If ANY check fails, REWRITE the email before returning:

1. Has EXACTLY one question mark — count them per email. If an email has 0 or 2+, rewrite.
2. Has no paragraph longer than 2 lines.
3. Contains ZERO numbers/percentages/statistics not found verbatim in CASE STUDIES or PRODUCT TRUTH TABLE.
4. Is anchored in a SPECIFIC detail from Section 1 (not a generic pain point).
5. Only claims capabilities listed in Section 2.
6. Scan each email word by word for banned patterns: "means", "chaos", "our [feature]", "one place/inbox/view/system/feed/workspace/dashboard/platform", "most teams", "that's a lot", "the JD", "Hi ", "[Product] is a [category]. It [verb]". If found, REWRITE.
7. Email 2: every fact matches the case study VERBATIM. If you added any phrase not in the case study, REMOVE it.
8. Count the verbs in sentences about Agorapulse. If a sentence about the product contains 2+ verbs (e.g., "publish, engage, and track" or "see X, spot Y, and adjust Z"), REWRITE to keep only ONE verb.
9. BDR credibility: read each email aloud. Does it sound like a real person wrote it, or like a product page? If the latter, REWRITE.
10. Value check: does Email 1 paragraph 1 contain an insight or observation (not just a restatement of their situation)? If it only mirrors facts without adding perspective, REWRITE.
11. WORD COUNT: Count every word in each email body (including merge tags like {{firstName}}). Email 1: max 120. Email 2: max 80. Email 3: max 120. If ANY email exceeds its limit, CUT sentences until it fits. Do not just trim — remove the least essential sentence.
12. Email 3 DIFFERENT CHALLENGE: Identify the core theme of Email 1. Then identify the core theme of Email 3. If they address the same underlying business problem (even from different angles), REWRITE Email 3 around a completely different pain signal from Section 1."""


# =============================================================================
# HELPERS
# =============================================================================

def load_playbook(playbook_path):
    """Load GTM playbook content"""
    with open(playbook_path, 'r', encoding='utf-8') as f:
        return f.read()


def _score_intel(intel):
    """Score an intel object based on completeness"""
    score = 0
    if intel.get('pain_signals'):
        score += len(intel['pain_signals']) * 2
    if intel.get('tools_mentioned'):
        score += len(intel['tools_mentioned'])
    if intel.get('competitor_tools'):
        score += len(intel['competitor_tools']) * 3
    if intel.get('team_context'):
        score += 2
    if intel.get('responsibility_summary'):
        score += 1
    return score


def merge_company_intel(company):
    """Merge intel from all job postings for a company.

    For single-posting companies, returns intel as-is (same as old get_best_intel).
    For multi-posting companies, merges lists (deduped) and uses best scalars.
    """
    jobs_with_intel = []
    for job in company.get('jobs', []):
        intel = job.get('intel')
        if intel:
            jobs_with_intel.append({
                **intel,
                'url': job.get('url', ''),
                'original_title': job.get('title', ''),
                '_score': _score_intel(intel),
            })

    if not jobs_with_intel:
        return None

    # Single posting - return as-is
    if len(jobs_with_intel) == 1:
        result = jobs_with_intel[0]
        del result['_score']
        return result

    # Multiple postings - merge
    best = max(jobs_with_intel, key=lambda x: x['_score'])

    # Merge list fields with dedup
    list_fields = ['pain_signals', 'tools_mentioned', 'competitor_tools',
                   'platforms_managed', 'key_metrics']
    merged_lists = {}
    for field in list_fields:
        seen = set()
        merged = []
        for job_intel in jobs_with_intel:
            for item in job_intel.get(field) or []:
                item_lower = str(item).lower()
                if item_lower not in seen:
                    seen.add(item_lower)
                    merged.append(item)
        merged_lists[field] = merged

    # Use best scalar fields from highest-scored intel
    seniority_rank = {'c-level': 7, 'vp': 6, 'director': 5, 'lead': 4,
                      'senior': 3, 'mid': 2, 'junior': 1}
    urgency_rank = {'high': 3, 'medium': 2, 'low': 1}

    highest_seniority = best.get('seniority', 'unknown')
    highest_urgency = best.get('hiring_urgency', 'unknown')
    for job_intel in jobs_with_intel:
        s = job_intel.get('seniority', '')
        if seniority_rank.get(s, 0) > seniority_rank.get(highest_seniority, 0):
            highest_seniority = s
        u = job_intel.get('hiring_urgency', '')
        if urgency_rank.get(u, 0) > urgency_rank.get(highest_urgency, 0):
            highest_urgency = u

    # Build team context with job count signal
    base_team_context = best.get('team_context', 'not available')
    team_context = f"hiring {len(jobs_with_intel)} social media roles; {base_team_context}"

    result = {
        'job_title': best.get('job_title', best.get('original_title', '')),
        'seniority': highest_seniority,
        'responsibility_summary': best.get('responsibility_summary', 'not available'),
        'team_context': team_context,
        'hiring_urgency': highest_urgency,
        'url': best.get('url', ''),
        'original_title': best.get('original_title', ''),
    }
    result.update(merged_lists)
    return result


def format_list(items):
    """Format a list for prompt injection"""
    if not items:
        return 'none mentioned'
    if isinstance(items, list):
        return ', '.join(str(i) for i in items)
    return str(items)


# =============================================================================
# BANNED PHRASE VALIDATOR
# =============================================================================

# Each entry: (compiled regex, human-readable label)
BANNED_PATTERNS = [
    # "X means Y" / "which means"
    (re.compile(r'\bwhich means\b', re.IGNORECASE), '"which means"'),
    (re.compile(r'\bthat means\b', re.IGNORECASE), '"that means"'),
    # "our" + feature name
    (re.compile(r'\bour\s+(inbox|reporting|scheduling|listening|dashboard|calendar|analytics|tool|platform)\b', re.IGNORECASE), '"our [feature]"'),
    # Fake authority patterns
    (re.compile(r'\bmost\s+(teams|managers|marketers|agencies|companies|brands|leaders)\b', re.IGNORECASE), '"most [teams/etc]"'),
    (re.compile(r'\bteams\s+I\s+(talk|work|speak|see)\b', re.IGNORECASE), '"teams I talk/work with"'),
    (re.compile(r'\bfrom what I\'ve seen\b', re.IGNORECASE), '"from what I\'ve seen"'),
    # Browser/switching clichés
    (re.compile(r'\bbrowser[\s-]*(tabs?|switching)\b', re.IGNORECASE), '"browser tabs/switching"'),
    (re.compile(r'\bplatform[\s-]*hopping\b', re.IGNORECASE), '"platform-hopping"'),
    # Dramatic language
    (re.compile(r'\bdrowning\s+in\b', re.IGNORECASE), '"drowning in"'),
    (re.compile(r'\bjuggling\b', re.IGNORECASE), '"juggling"'),
    (re.compile(r'\bchaos\b', re.IGNORECASE), '"chaos"'),
    (re.compile(r'\boverwhelm', re.IGNORECASE), '"overwhelm"'),
    # "Hi " at start
    (re.compile(r'^Hi\s', re.MULTILINE), '"Hi " at start'),
    # Filler transitions
    (re.compile(r'\bthat\'s\s+a\s+lot\b', re.IGNORECASE), '"that\'s a lot"'),
    (re.compile(r'\ba\s+lot\s+of\s+surface\s+area\b', re.IGNORECASE), '"a lot of surface area"'),
    (re.compile(r'\bthat\'s\s+(hard|tough)\s+when\b', re.IGNORECASE), '"that\'s hard/tough when"'),
    # "one [noun]" consolidation clichés
    (re.compile(r'\b(one|single|unified)\s+(inbox|place|calendar|view|system|workspace|dashboard|platform|feed|tool)\b', re.IGNORECASE), '"one/single/unified [noun]"'),
    # Product-brief phrasing
    (re.compile(r'Agorapulse\s+is\s+a\s+', re.IGNORECASE), '"Agorapulse is a..."'),
    # "most [people] underestimate" / "most [people] end up"
    (re.compile(r'\bmost\s+\w+\s+(underestimate|overestimate|end\s+up|don\'t\s+realize|overlook)\b', re.IGNORECASE), '"most [X] underestimate/end up"'),
]

MAX_RETRIES = 2


def check_banned_phrases(emails):
    """Check all 3 email bodies for banned phrases.

    Returns list of (email_key, matched_pattern_label, matched_text) tuples.
    Empty list = all clean.
    """
    violations = []
    body_keys = ['email_1_body', 'email_2_body', 'email_3_body']
    for key in body_keys:
        body = emails.get(key, '')
        for pattern, label in BANNED_PATTERNS:
            match = pattern.search(body)
            if match:
                violations.append((key, label, match.group()))
    return violations


# =============================================================================
# CASE STUDIES
# =============================================================================

CASE_STUDIES = {
    'adtrak_scaling': (
        'Adtrak (UK agency, 51-200 employees): switched from Hootsuite, doubled social team '
        'from 3 to 7, now managing 100+ profiles for 400+ SME clients. '
        'Streamlined onboarding for new social media managers.'
    ),
    'homefield_ecommerce': (
        'Homefield Apparel (US e-commerce, 2-10 employees, college sports apparel): '
        'was tracking social media conversions manually with Excel spreadsheets. '
        'Switched to Agorapulse for automated social media ROI reporting. '
        'Replaced manual spreadsheet tracking, now proves ROI of organic social media efforts with data. '
        'Quote: "Now I have more time to do my creative stuff and think about what\'s next, '
        'instead of being like, Oh man, I haven\'t done my reporting for the week."'
    ),
    'nexford_time': (
        'Nexford University (US, 51-200 employees, higher education, 8-person social team): '
        'switched from Hootsuite after it failed to capture all messages. '
        'Reduced social media reporting time by 75% with Agorapulse. '
        'Was using Excel spreadsheets for manual reporting that took hours. '
        'Quote: "Agorapulse essentially quarters the amount of time that I need to get those reports."'
    ),
    'digital_butter_roi': (
        'Digital Butter (South Africa agency, 2-10 employees): '
        'switched from Buffer after outgrowing its reporting capabilities. '
        'Clients increased sales by 300%. Grew one client\'s audience by 700% in one year. '
        'Cut reporting time in half. Uses label reports to analyze which content types drive more sales. '
        'Quote: "We don\'t just post for the sake of posting. There needs to be a strategy, '
        'and we need to be able to show a client a detailed report on how content has done."'
    ),
}


def select_case_studies(industry):
    """Select relevant case studies based on company industry"""
    industry_lower = (industry or '').lower()

    # Agency verticals — Adtrak (scaling) + Digital Butter (ROI)
    if any(kw in industry_lower for kw in ['agency', 'marketing & advertising',
                                            'advertising', 'media', 'pr ',
                                            'public relations', 'communications']):
        return '\n'.join([
            f'- {CASE_STUDIES["adtrak_scaling"]}',
            f'- {CASE_STUDIES["digital_butter_roi"]}',
        ])

    # E-commerce / Retail — Homefield Apparel is closest match
    if any(kw in industry_lower for kw in ['ecommerce', 'e-commerce', 'retail',
                                            'consumer goods', 'food', 'beverage',
                                            'fashion', 'apparel']):
        return '\n'.join([
            f'- {CASE_STUDIES["homefield_ecommerce"]}',
            f'- {CASE_STUDIES["digital_butter_roi"]}',
        ])

    # Education — Nexford University is closest match
    if any(kw in industry_lower for kw in ['education', 'university', 'school',
                                            'higher ed', 'academic']):
        return '\n'.join([
            f'- {CASE_STUDIES["nexford_time"]}',
            f'- {CASE_STUDIES["homefield_ecommerce"]}',
        ])

    # B2B SaaS / Tech — Nexford (time savings) + Digital Butter (ROI proof)
    if any(kw in industry_lower for kw in ['saas', 'software', 'technology',
                                            'information technology', 'computer',
                                            'internet', 'fintech']):
        return '\n'.join([
            f'- {CASE_STUDIES["nexford_time"]}',
            f'- {CASE_STUDIES["digital_butter_roi"]}',
        ])

    # Enterprise / Large orgs — Nexford (time savings at scale)
    if any(kw in industry_lower for kw in ['enterprise', 'financial', 'banking',
                                            'insurance', 'healthcare', 'hospital',
                                            'pharmaceutical', 'automotive']):
        return '\n'.join([
            f'- {CASE_STUDIES["nexford_time"]}',
            f'- {CASE_STUDIES["digital_butter_roi"]}',
        ])

    # Unknown vertical - provide all three
    return '\n'.join([
        f'- {CASE_STUDIES["homefield_ecommerce"]}',
        f'- {CASE_STUDIES["nexford_time"]}',
        f'- {CASE_STUDIES["digital_butter_roi"]}',
    ])


# =============================================================================
# PLAYBOOK CONTEXT
# =============================================================================

TRUTH_TABLE_PATH = SKILL_DIR / 'references' / 'product_truth_table.md'

_truth_table_cache = None


def load_product_truth_table():
    """Load the product truth table from references/product_truth_table.md.

    Returns condensed product context for the email prompt.
    Caches after first read.
    """
    global _truth_table_cache
    if _truth_table_cache is not None:
        return _truth_table_cache

    if not TRUTH_TABLE_PATH.exists():
        print(f"Warning: Truth table not found at {TRUTH_TABLE_PATH}")
        _truth_table_cache = 'Product truth table not available.'
        return _truth_table_cache

    with open(TRUTH_TABLE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Build condensed context from truth table sections.
    # Priority order: Identity, Plans, Features (H3 headers + top 3 bullets each),
    # What We Do NOT Do, Competitive Positioning, Key Metrics.
    # Case studies and integrations/security are handled elsewhere or less critical.

    extracted = []
    lines = content.split('\n')
    i = 0

    # Sections to include verbatim (not trimmed)
    verbatim_sections = [
        '## Identity',
        '## Plans & Pricing',
        '## What We Do NOT Do',
        '## Competitive Positioning',
        '## Key Metrics',
    ]

    # Sections to skip entirely
    skip_sections = [
        '## Verified Case Studies',  # handled by select_case_studies()
        '## Integrations',
        '## Security & Compliance',
    ]

    while i < len(lines):
        line = lines[i]

        # H2 section detection
        if line.startswith('## '):
            # Skip header/source note
            if line.startswith('# Agorapulse') or line.startswith('> Source'):
                i += 1
                continue

            # Verbatim sections: include everything until next H2
            if any(line.startswith(s) for s in verbatim_sections):
                extracted.append(line)
                i += 1
                while i < len(lines) and not lines[i].startswith('## '):
                    extracted.append(lines[i])
                    i += 1
                continue

            # Core Features: include H3 headers + first 3 bullets per subsection
            if line.startswith('## Core Features'):
                extracted.append(line)
                extracted.append('')
                i += 1
                bullet_count = 0
                while i < len(lines) and not lines[i].startswith('## '):
                    if lines[i].startswith('### '):
                        extracted.append(lines[i])
                        bullet_count = 0
                    elif lines[i].startswith('- ') and bullet_count < 3:
                        extracted.append(lines[i])
                        bullet_count += 1
                    elif lines[i].strip() == '':
                        extracted.append('')
                    i += 1
                continue

            # Skip sections
            if any(line.startswith(s) for s in skip_sections):
                i += 1
                while i < len(lines) and not lines[i].startswith('## '):
                    i += 1
                continue

            # Any other section: skip
            i += 1
            while i < len(lines) and not lines[i].startswith('## '):
                i += 1
            continue

        i += 1

    result = '\n'.join(extracted).strip()

    # Remove excessive blank lines
    while '\n\n\n' in result:
        result = result.replace('\n\n\n', '\n\n')

    _truth_table_cache = result
    return _truth_table_cache


# =============================================================================
# CLAUDE API
# =============================================================================

def _call_email_api(prompt):
    """Make a single API call for email generation. Returns (emails_dict, status)."""
    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': EMAIL_MODEL,
                'max_tokens': 2048,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        content = data.get('content', [])
        if not content:
            return None, 'empty_response'

        text = content[0].get('text', '').strip()

        # Handle markdown code block wrapping
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

        # Extract JSON object even if model adds surrounding text
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]

        # Fix trailing commas before closing braces (common LLM JSON issue)
        text = re.sub(r',\s*}', '}', text)

        emails = json.loads(text)

        # Validate required fields and strip extras
        required = ['email_1_body', 'email_2_body', 'email_3_body']
        for field in required:
            if field not in emails:
                return None, f'missing_field_{field}'

        emails = {k: v for k, v in emails.items() if k in required}
        return emails, 'success'

    except json.JSONDecodeError:
        return None, 'json_parse_error'
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 429:
            print("    Rate limited. Waiting 30s...")
            time.sleep(30)
            return _call_email_api(prompt)
        return None, f'api_error_{status}'
    except Exception as e:
        return None, f'error: {str(e)}'


def generate_emails_for_company(company, intel, playbook_content):
    """Generate 3 emails for a company using Claude, with banned-phrase retry."""
    if not ANTHROPIC_API_KEY:
        return None, 'no_api_key'

    industry = company.get('industry', 'unknown')
    product_context = load_product_truth_table()

    prompt = EMAIL_GENERATION_PROMPT.format(
        product_context=product_context,
        case_studies=select_case_studies(industry),
        company_name=company.get('company_name', ''),
        employee_count=company.get('employee_count', 'unknown'),
        industry=company.get('industry', 'unknown'),
        company_context=company.get('company_context') or 'not available',
        job_title=intel.get('job_title', intel.get('original_title', '')),
        seniority=intel.get('seniority', 'unknown'),
        responsibility_summary=intel.get('responsibility_summary', 'not available'),
        tools_mentioned=format_list(intel.get('tools_mentioned')),
        competitor_tools=format_list(intel.get('competitor_tools')),
        pain_signals=format_list(intel.get('pain_signals')),
        team_context=intel.get('team_context', 'not available'),
        hiring_urgency=intel.get('hiring_urgency', 'unknown'),
        platforms_managed=format_list(intel.get('platforms_managed')),
    )

    RETRYABLE_STATUSES = {'json_parse_error', 'missing_field'}

    for attempt in range(1 + MAX_RETRIES):
        emails, status = _call_email_api(prompt)

        if not emails:
            # Retry transient parse failures; bail on hard errors (API, auth, etc.)
            is_retryable = any(status.startswith(s) for s in RETRYABLE_STATUSES)
            if is_retryable and attempt < MAX_RETRIES:
                print(f"    {status} (attempt {attempt + 1}), retrying...")
                time.sleep(RATE_LIMIT_DELAY)
                continue
            return emails, status

        # Check for banned phrases
        violations = check_banned_phrases(emails)
        if not violations:
            return emails, 'success'

        # Log violations
        violation_summary = '; '.join(f'{key}: {label} ("{text}")'
                                       for key, label, text in violations)
        if attempt < MAX_RETRIES:
            print(f"    Banned phrase found (attempt {attempt + 1}): {violation_summary}")
            print(f"    Retrying...")
            time.sleep(RATE_LIMIT_DELAY)
        else:
            print(f"    Banned phrase after {MAX_RETRIES + 1} attempts: {violation_summary}")
            # Return the emails anyway with a warning status — user confirmed
            # they're OK with occasional violations since emails are still relevant
            return emails, f'success_with_warnings: {violation_summary}'


# =============================================================================
# ORCHESTRATION
# =============================================================================

def generate_all_emails(companies, playbook_content):
    """Generate emails for all companies with intel"""
    results = []
    total = sum(1 for c in companies if merge_company_intel(c))
    processed = 0
    success = 0
    failed = 0

    print(f"\nGenerating emails for {total} companies...")

    for company in companies:
        intel = merge_company_intel(company)
        if not intel:
            continue

        processed += 1
        name = company['company_name']
        print(f"  [{processed}/{total}] {name}")

        emails, status = generate_emails_for_company(company, intel, playbook_content)

        if emails:
            success += 1
            print(f"    -> generated")
        else:
            failed += 1
            print(f"    -> {status}")

        results.append({
            'company_name': company['company_name'],
            'domain': company['domain'],
            'organization_id': company.get('organization_id', ''),
            'employee_count': company.get('employee_count'),
            'industry': company.get('industry', ''),
            'country': company.get('country', ''),
            'contacts': company.get('contacts', []),
            'intel': intel,
            'emails': emails,
            'email_status': status,
        })

        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n  Generation complete: {success} success, {failed} failed")
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate 3 complete emails per company from extracted intel'
    )
    parser.add_argument('intel_json', help='Path to intel_extracted.json')
    parser.add_argument('--playbook', required=True,
                        help='Path to GTM playbook markdown file')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("HIRING INTEL - STEP 4: GENERATE EMAILS")
    print("=" * 70)

    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    # Load intel
    input_path = Path(args.intel_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    # Load playbook
    playbook_path = Path(args.playbook)
    if not playbook_path.exists():
        print(f"Error: Playbook not found: {playbook_path}")
        sys.exit(1)

    playbook_content = load_playbook(playbook_path)

    # Stats
    companies_with_intel = [c for c in companies if merge_company_intel(c)]
    total = len(companies_with_intel)
    est_cost = total * 0.005  # ~$0.005 per company (Sonnet)

    print(f"\nCompanies with intel: {total}")
    print(f"Playbook: {playbook_path.name} ({len(playbook_content)} chars)")
    print(f"Model: {EMAIL_MODEL}")
    print(f"Estimated cost: ~${est_cost:.2f}")

    if not args.yes:
        print()
        response = input("Proceed with email generation? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Generate
    results = generate_all_emails(companies, playbook_content)

    # Save output alongside input
    output_path = input_path.parent / 'emails_generated.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    success_count = sum(1 for r in results if r.get('emails'))

    print(f"\n{'=' * 70}")
    print("EMAIL GENERATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Emails generated: {success_count}/{total} companies")
    print(f"Output: {output_path}")

    # Show sample
    for r in results[:2]:
        if r.get('emails'):
            print(f"\n--- Sample: {r['company_name']} ---")
            body1 = r['emails']['email_1_body']
            preview = body1[:150] + '...' if len(body1) > 150 else body1
            print(f"Preview: {preview}")
            break


if __name__ == '__main__':
    main()
