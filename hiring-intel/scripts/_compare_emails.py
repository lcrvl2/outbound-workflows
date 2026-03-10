#!/usr/bin/env python3
"""Compare Opus-generated emails using Haiku intel vs Sonnet intel for both companies."""

import json
import os
import re
import sys
import time
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

API_KEY = os.getenv('ANTHROPIC_API_KEY')
API_URL = 'https://api.anthropic.com/v1/messages'
EMAIL_MODEL = 'claude-opus-4-6'

# Import shared components from generate_emails.py
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from generate_emails import (
    EMAIL_GENERATION_PROMPT,
    CASE_STUDIES,
    select_case_studies,
    format_list,
    load_product_truth_table,
)

# ── Load comparison intel ─────────────────────────────────────────────────────

COMPARISON_PATH = SKILL_DIR / 'generated-outputs/test_wttj/_model_comparison_v2.json'
with open(COMPARISON_PATH) as f:
    comparison_data = json.load(f)

# Company metadata (not in the intel itself)
COMPANY_META = {
    "sharkninja": {
        "company_name": "SharkNinja",
        "domain": "sharkninja.com",
        "employee_count": 3600,
        "industry": "E-commerce / Consumer Electronics",
        "country": "France",
        "company_context": "SharkNinja: Global product design and technology company. Diversified portfolio of 5-star rated lifestyle solutions across Home, Kitchen, and Beauty. Powered by Shark and Ninja brands. 3,600+ associates globally. Headquartered in Needham, Massachusetts. Revenue: $5.5 Billion. Founded 1994. Expanding in France/EMEA.",
    },
    "socialy": {
        "company_name": "Socialy",
        "domain": "socialy.fr",
        "employee_count": 42,
        "industry": "Marketing & Advertising (Agency)",
        "country": "France",
        "company_context": "Socialy: Social media agency ('Socialy crée des Social Brands'). 40+ collaborateurs, ~40 clients in France including Pizza Hut, Gîtes de France, Floa, JCDecaux. Services: conseil, stratégie, création, production, social media. Founded 2011. Great Place to Work certified. EcoVadis Silver. Based at 11 Rue Milton, 75009 Paris. Average age: 29. Turnover: 10%.",
    },
}

# ── Generate emails ───────────────────────────────────────────────────────────

def generate_emails(company_meta, intel):
    """Call Opus to generate emails given company metadata + intel."""
    industry = company_meta.get('industry', 'unknown')
    product_context = load_product_truth_table()

    prompt = EMAIL_GENERATION_PROMPT.format(
        product_context=product_context,
        case_studies=select_case_studies(industry),
        company_name=company_meta.get('company_name', ''),
        employee_count=company_meta.get('employee_count', 'unknown'),
        industry=company_meta.get('industry', 'unknown'),
        company_context=company_meta.get('company_context', 'not available'),
        job_title=intel.get('job_title', ''),
        seniority=intel.get('seniority', 'unknown'),
        responsibility_summary=intel.get('responsibility_summary', 'not available'),
        tools_mentioned=format_list(intel.get('tools_mentioned')),
        competitor_tools=format_list(intel.get('competitor_tools')),
        pain_signals=format_list(intel.get('pain_signals')),
        team_context=intel.get('team_context', 'not available'),
        hiring_urgency=intel.get('hiring_urgency', 'unknown'),
        platforms_managed=format_list(intel.get('platforms_managed')),
    )

    resp = requests.post(API_URL, headers={
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'anthropic-version': '2023-06-01',
    }, json={
        'model': EMAIL_MODEL,
        'max_tokens': 2048,
        'messages': [{'role': 'user', 'content': prompt}],
    }, timeout=90)
    resp.raise_for_status()
    data = resp.json()

    text = data['content'][0]['text'].strip()

    # Parse JSON from response
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end + 1]

    text = re.sub(r',\s*}', '}', text)
    emails = json.loads(text)

    usage = data['usage']
    return emails, usage


# ── Run all 4 combinations ───────────────────────────────────────────────────

results = {}

for company_key in ['sharkninja', 'socialy']:
    company = COMPANY_META[company_key]
    company_data = comparison_data[company_key]
    results[company_key] = {'company_name': company['company_name']}

    for model_label in ['haiku', 'sonnet']:
        intel = company_data[model_label]
        combo = f"{company['company_name']} + {model_label} intel"
        print(f"\n{'='*60}")
        print(f"  Generating: {combo}")
        print(f"{'='*60}")

        emails, usage = generate_emails(company, intel)
        results[company_key][model_label] = emails

        print(f"  Done. Input: {usage['input_tokens']}t, Output: {usage['output_tokens']}t")
        print(f"  Subject 1: {emails.get('email_1_subject', '?')}")
        time.sleep(2)  # rate limit buffer for Opus

# ── Save ──────────────────────────────────────────────────────────────────────

out_path = SKILL_DIR / 'generated-outputs/test_wttj/_email_comparison.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nSaved to {out_path}")
