#!/usr/bin/env python3
"""One-off script: compare Haiku vs Sonnet intel extraction on same JD."""

import json
import os
import requests
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

API_KEY = os.getenv('ANTHROPIC_API_KEY')
API_URL = 'https://api.anthropic.com/v1/messages'

# Load the updated Bitstack JD
with open(Path(__file__).parent.parent / 'generated-outputs/test_wttj/job_descriptions.json') as f:
    companies = json.load(f)

bitstack = companies[0]
jd_text = bitstack['jobs'][0]['description']
company_context = bitstack.get('company_context', '')

# Same prompt as extract_intel.py
PROMPT_TEMPLATE = """You are an expert at analyzing job descriptions to extract actionable sales intelligence.

Analyze the following job description and extract structured intel. Return ONLY valid JSON with these fields:

{{
  "job_title": "exact title from the posting",
  "seniority": "junior | mid | senior | lead | director | vp | c-level",
  "responsibility_summary": "1-2 sentence summary of key responsibilities",
  "tools_mentioned": ["list", "of", "tools", "platforms", "software"],
  "competitor_tools": ["only tools that compete with social media management platforms like Hootsuite, Sprout Social, etc."],
  "pain_signals": ["inferred pain points from the job description - what problems is this hire meant to solve?"],
  "team_context": "team size, reporting structure, first hire vs expanding team",
  "hiring_urgency": "low | medium | high",
  "key_metrics": ["any KPIs or metrics mentioned"],
  "platforms_managed": ["social platforms they manage - Instagram, LinkedIn, TikTok, etc."]
}}

Rules:
- For tools_mentioned and competitor_tools: ONLY include tools that are EXPLICITLY NAMED in the text. If the JD says "social media management tools" generically, do NOT guess specific tool names. Only list a tool if its exact name appears in the job description.
- For competitor_tools, only include tools that are social media management/scheduling/analytics platforms
- For pain_signals, INFER from context (e.g., "first dedicated hire" = they had no process before; "manage 5 platforms" = struggling with scale). Use the company website context below (if provided) to enrich your understanding of the company and refine pain signals.
- For hiring_urgency: high = ASAP/immediate/urgent language; medium = standard posting; low = pipeline/future role
- If a field cannot be determined, use null for strings or empty array [] for lists
- Return ONLY the JSON object, no other text

Company Website Context: {company_context}

Job Description:
{jd_text}"""

prompt = PROMPT_TEMPLATE.format(company_context=company_context, jd_text=jd_text)

models = {
    'haiku': 'claude-haiku-4-5-20251001',
    'sonnet': 'claude-sonnet-4-5-20250929',
}

results = {}
for label, model_id in models.items():
    print(f'Running {label} ({model_id})...')
    resp = requests.post(API_URL, headers={
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'anthropic-version': '2023-06-01',
    }, json={
        'model': model_id,
        'max_tokens': 2048,
        'messages': [{'role': 'user', 'content': prompt}],
    }, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    text = data['content'][0]['text'].strip()
    # Parse JSON
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end + 1]
    results[label] = json.loads(text)
    usage = data['usage']
    print(f'  Done. Input: {usage["input_tokens"]} tokens, Output: {usage["output_tokens"]} tokens')
    time.sleep(1)

# Save comparison
out_path = Path(__file__).parent.parent / 'generated-outputs/test_wttj/_model_comparison.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f'\nSaved to {out_path}')
