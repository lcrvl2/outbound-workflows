#!/usr/bin/env python3
"""
Filter Roles - Classify previous employer roles as relevant or excluded.

Two-pass approach:
1. Regex: instant, free classification of obvious includes/excludes
2. Claude Haiku: only for ambiguous titles that regex couldn't classify

Also removes: roles at the same company as CW company, duplicates.

Input: work_history_scraped.json (from scrape_work_history.py)
Output: roles_filtered.json

Usage:
    python filter_roles.py <work_history_json> [--yes]
"""

import json
import sys
import os
import re
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
CLASSIFICATION_MODEL = 'claude-haiku-4-5-20251001'

RATE_LIMIT_DELAY = 0.5


# =============================================================================
# REGEX RULES (Pass 1 - instant, free)
# =============================================================================

# Titles that are definitely relevant (marketing/social/content roles)
INCLUDE_PATTERNS = [
    r'social\s*media', r'community\s*manag', r'content\s*(manag|strateg|market|creat|direct)',
    r'marketing\s*(manag|direct|coord|special|strateg|lead|head|vp|chief)',
    r'digital\s*(market|strateg|manag|direct)',
    r'communications?\s*(manag|direct|special|lead)',
    r'brand\s*(manag|direct|strateg)',
    r'growth\s*(manag|market|lead|head)',
    r'\bcmo\b', r'chief\s*marketing',
    r'head\s*of\s*(market|social|content|digital|communications|brand|growth)',
    r'vp\s*(of\s*)?(market|social|content|digital|communications)',
    r'pr\s*manag', r'public\s*relations',
    r'creative\s*direct',
]

# Titles that are definitely excluded (non-marketing roles)
EXCLUDE_PATTERNS = [
    r'\bintern\b', r'\bstagiaire\b', r'\bstage\b',
    r'\bcfo\b', r'\bcto\b', r'\bcio\b', r'\bcoo\b',
    r'financ', r'\blegal\b', r'counsel', r'attorney', r'lawyer',
    r'engineer', r'developer', r'programmer', r'software',
    r'\bhr\b', r'human\s*resource', r'recruiter', r'talent\s*acqui',
    r'accountant', r'accounting', r'bookkeep',
    r'advisory\s*board', r'board\s*member', r'\binvestor\b', r'\badvisor\b',
    r'customer\s*success', r'customer\s*support', r'customer\s*service',
    r'sales\s*(rep|exec|associate|develop|manag|direct)',
    r'account\s*(manag|exec)', r'business\s*develop',
    r'product\s*(manag|owner|design)', r'project\s*manag',
    r'operations?\s*(manag|direct|lead)',
    r'supply\s*chain', r'logistics', r'warehouse',
    r'data\s*(scien|analy|engineer)',
    r'\bqa\b', r'quality\s*assur',
]

INCLUDE_RE = re.compile('|'.join(INCLUDE_PATTERNS), re.IGNORECASE)
EXCLUDE_RE = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)


def classify_regex(title):
    """Classify a title using regex rules. Returns 'RELEVANT', 'EXCLUDED', or 'AMBIGUOUS'."""
    if not title:
        return 'EXCLUDED'

    if EXCLUDE_RE.search(title):
        return 'EXCLUDED'
    if INCLUDE_RE.search(title):
        return 'RELEVANT'
    return 'AMBIGUOUS'


# =============================================================================
# CLAUDE HAIKU (Pass 2 - only for ambiguous titles)
# =============================================================================

CLASSIFICATION_PROMPT = """You are classifying job titles to determine if they are relevant to social media management or marketing.

A title is RELEVANT if the person likely managed or influenced social media, content, or digital marketing activities. A title is EXCLUDED if it's clearly unrelated (sales, operations, admin, etc.) or too generic to indicate marketing involvement.

Classify each title below as RELEVANT or EXCLUDED. Return ONLY valid JSON.

{
  "classifications": [
    {"title": "...", "verdict": "RELEVANT" or "EXCLUDED", "reason": "brief reason"}
  ]
}

Rules:
- RELEVANT: marketing, social media, content, communications, PR, brand, digital, community management, growth roles
- RELEVANT: C-level/VP only if marketing-adjacent (CMO, VP Marketing, Chief Communications Officer)
- EXCLUDED: pure sales, operations, admin, customer success, product, engineering, finance, HR, legal
- EXCLUDED: generic titles like "Manager", "Director", "Consultant" without marketing context
- EXCLUDED: "Account Manager", "Project Manager", "Business Development" (these are sales/ops)

Titles to classify:
"""


def classify_with_haiku(titles):
    """Classify ambiguous titles using Claude Haiku. Returns dict of title -> verdict."""
    if not ANTHROPIC_API_KEY or not titles:
        return {t: 'EXCLUDED' for t in titles}

    titles_json = json.dumps(titles, indent=2)
    prompt = CLASSIFICATION_PROMPT + titles_json

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': CLASSIFICATION_MODEL,
                'max_tokens': 1024,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        text = data.get('content', [{}])[0].get('text', '')

        # Parse JSON
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        classifications = result.get('classifications', [])

        return {
            c['title']: c['verdict']
            for c in classifications
            if 'title' in c and 'verdict' in c
        }

    except json.JSONDecodeError:
        print("    [haiku] JSON parse error, defaulting to EXCLUDED")
        return {t: 'EXCLUDED' for t in titles}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            time.sleep(10)
            return classify_with_haiku(titles)
        print(f"    [haiku] API error: {e.response.status_code}")
        return {t: 'EXCLUDED' for t in titles}
    except Exception as e:
        print(f"    [haiku] Error: {e}")
        return {t: 'EXCLUDED' for t in titles}


# =============================================================================
# ORCHESTRATION
# =============================================================================

def filter_all_roles(champions_history):
    """Filter roles for all champions using regex + Haiku"""
    results = []
    stats = {'regex_include': 0, 'regex_exclude': 0, 'haiku_include': 0, 'haiku_exclude': 0}

    print(f"\nFiltering roles for {len(champions_history)} champions...")

    all_ambiguous = []  # Collect all ambiguous titles for batch Haiku call

    # Pass 1: Regex classification
    for champion in champions_history:
        champion_name = champion['champion_name']
        cw_company = champion['champion_company'].lower()

        for employer in champion.get('previous_employers', []):
            company_name = employer['company_name']
            title = employer['title']

            # Skip if same as CW company
            if company_name.lower() in cw_company or cw_company in company_name.lower():
                continue

            verdict = classify_regex(title)

            if verdict == 'RELEVANT':
                stats['regex_include'] += 1
            elif verdict == 'EXCLUDED':
                stats['regex_exclude'] += 1
            else:
                all_ambiguous.append({
                    'champion': champion,
                    'employer': employer,
                    'title': title,
                })

    # Pass 2: Haiku for ambiguous titles
    haiku_verdicts = {}
    if all_ambiguous:
        unique_titles = list(set(a['title'] for a in all_ambiguous))
        print(f"\n  Regex classified {stats['regex_include'] + stats['regex_exclude']} titles")
        print(f"  Sending {len(unique_titles)} ambiguous titles to Haiku...")

        # Batch in groups of 20
        for batch_start in range(0, len(unique_titles), 20):
            batch = unique_titles[batch_start:batch_start + 20]
            batch_verdicts = classify_with_haiku(batch)
            haiku_verdicts.update(batch_verdicts)
            time.sleep(RATE_LIMIT_DELAY)

        for title, verdict in haiku_verdicts.items():
            if verdict == 'RELEVANT':
                stats['haiku_include'] += 1
            else:
                stats['haiku_exclude'] += 1

    # Build final results
    seen_pairs = set()  # (champion_email, company_name) to dedupe

    for champion in champions_history:
        champion_name = champion['champion_name']
        champion_email = champion['champion_email']
        cw_company = champion['champion_company'].lower()

        relevant_employers = []

        for employer in champion.get('previous_employers', []):
            company_name = employer['company_name']
            title = employer['title']

            # Skip if same as CW company
            if company_name.lower() in cw_company or cw_company in company_name.lower():
                continue

            # Dedupe
            pair_key = (champion_email, company_name.lower())
            if pair_key in seen_pairs:
                continue

            verdict = classify_regex(title)
            if verdict == 'AMBIGUOUS':
                verdict = haiku_verdicts.get(title, 'EXCLUDED')

            if verdict == 'RELEVANT':
                seen_pairs.add(pair_key)
                relevant_employers.append(employer)

        if relevant_employers:
            results.append({
                'champion_name': champion_name,
                'champion_email': champion_email,
                'champion_company': champion['champion_company'],
                'linkedin_url': champion.get('linkedin_url', ''),
                'relevant_employers': relevant_employers,
            })

    print(f"\n  Regex: {stats['regex_include']} included, {stats['regex_exclude']} excluded")
    print(f"  Haiku: {stats['haiku_include']} included, {stats['haiku_exclude']} excluded")
    print(f"  Champions with relevant employers: {len(results)}")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Filter roles using regex + Claude Haiku'
    )
    parser.add_argument('work_history_json', help='Path to work_history_scraped.json')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 3: FILTER ROLES")
    print("=" * 70)

    input_path = Path(args.work_history_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        champions_history = json.load(f)

    total_roles = sum(len(c.get('previous_employers', [])) for c in champions_history)

    print(f"\nChampions: {len(champions_history)}")
    print(f"Total previous roles: {total_roles}")
    print(f"Classification: Regex (pass 1) + Haiku (pass 2 for ambiguous)")

    if not args.yes:
        print()
        response = input("Proceed with role filtering? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Filter
    results = filter_all_roles(champions_history)

    # Save output
    output_path = input_path.parent / 'roles_filtered.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    total_relevant = sum(len(c['relevant_employers']) for c in results)

    print(f"\n{'=' * 70}")
    print("FILTER COMPLETE")
    print(f"{'=' * 70}")
    print(f"Champions with relevant history: {len(results)}/{len(champions_history)}")
    print(f"Relevant employer roles: {total_relevant}/{total_roles}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
