#!/usr/bin/env python3
"""
Extract Intel - Use Claude Sonnet to extract structured hiring intel from job descriptions.

Extracts: job title, seniority, responsibilities, tools mentioned, competitor tools,
pain signals, team context, hiring urgency.

Input: job_descriptions.json (from scrape_descriptions.py)
Output: intel_extracted.json (structured intel per company)

Usage:
    python extract_intel.py <job_descriptions_json> [--yes]
"""

import json
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

# Model for extraction (Sonnet for accuracy — Haiku drops critical details)
EXTRACTION_MODEL = os.getenv('EXTRACTION_MODEL', 'claude-sonnet-4-5-20250929')

RATE_LIMIT_DELAY = 0.5
MAX_JD_LENGTH = 8000  # Truncate very long JDs


# =============================================================================
# EXTRACTION PROMPT
# =============================================================================

EXTRACTION_PROMPT = """You are an expert at analyzing job descriptions to extract actionable sales intelligence.

Analyze the following job description and extract structured intel. Return ONLY valid JSON with these fields:

{
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
}

Rules:
- For tools_mentioned and competitor_tools: ONLY include tools that are EXPLICITLY NAMED in the text. If the JD says "social media management tools" generically, do NOT guess specific tool names. Only list a tool if its exact name appears in the job description.
- For competitor_tools, only include tools that are social media management/scheduling/analytics platforms
- For pain_signals, INFER from context (e.g., "first dedicated hire" = they had no process before; "manage 5 platforms" = struggling with scale). Use the company website context below (if provided) to enrich your understanding of the company and refine pain signals.
- For hiring_urgency: high = ASAP/immediate/urgent language; medium = standard posting; low = pipeline/future role
- If a field cannot be determined, use null for strings or empty array [] for lists
- Return ONLY the JSON object, no other text

{company_context_section}Job Description:
{jd_text}"""


# =============================================================================
# POST-PROCESSING
# =============================================================================

# Never list our own product as a competitor tool
OUR_PRODUCTS = {'agorapulse'}

# Direct competitors = tools Agorapulse replaces (social media management/scheduling/analytics)
DIRECT_COMPETITORS = {
    'hootsuite', 'sprout social', 'buffer', 'iconosquare', 'sprinklr',
    'later', 'planable', 'sendible', 'socialbee', 'loomly', 'publer',
    'socialflow', 'khoros', 'emplifi', 'brandwatch', 'meltwater',
    'falcon.io', 'facelift', 'oktopost', 'zoho social', 'eclincher',
    'social pilot', 'socialpilot', 'crowdfire', 'coschedule',
    'statusbrew', 'vista social', 'metricool', 'swello', 'kontentino',
}

# Adjacent tools = tools Agorapulse does NOT replace (different category)
ADJACENT_TOOLS = {
    'manychat', 'chatfuel',                         # chatbots / DM automation
    'asana', 'trello', 'monday', 'notion', 'slack', # project management / comms
    'canva', 'figma', 'adobe',                      # design
    'hubspot', 'salesforce', 'pipedrive',            # CRM
    'mailchimp', 'klaviyo', 'brevo',                 # email marketing
    'google analytics', 'semrush', 'ahrefs',         # SEO / web analytics
    'capcut', 'descript',                            # video editing
}


def filter_hallucinated_tools(intel, jd_text):
    """Remove tools from intel that don't appear in the actual JD text.

    LLMs sometimes hallucinate specific tool names from generic mentions
    like 'social media management tools'. This filter only keeps tools
    whose name actually appears in the JD.
    """
    jd_lower = jd_text.lower()

    for field in ('competitor_tools', 'tools_mentioned'):
        original = intel.get(field) or []
        filtered = [
            tool for tool in original
            if tool.lower() in jd_lower and tool.lower() not in OUR_PRODUCTS
        ]
        if len(filtered) != len(original):
            removed = set(t.lower() for t in original) - set(t.lower() for t in filtered)
            if removed:
                print(f"    [filter] removed hallucinated {field}: {', '.join(sorted(removed))}")
        intel[field] = filtered

    # Reclassify competitor_tools: only keep direct competitors
    original_competitors = intel.get('competitor_tools') or []
    real_competitors = [
        tool for tool in original_competitors
        if tool.lower() in DIRECT_COMPETITORS
    ]
    demoted = [t for t in original_competitors if t.lower() not in DIRECT_COMPETITORS]
    if demoted:
        print(f"    [classify] dropped non-competitors from competitor_tools: {', '.join(demoted)}")
    intel['competitor_tools'] = real_competitors

    return intel


# =============================================================================
# CLAUDE API
# =============================================================================

def extract_intel_from_jd(jd_text, job_title='', company_name='', company_context=''):
    """Call Claude Haiku to extract structured intel from a job description"""
    if not ANTHROPIC_API_KEY:
        return None, 'no_api_key'

    # Truncate very long JDs
    if len(jd_text) > MAX_JD_LENGTH:
        jd_text = jd_text[:MAX_JD_LENGTH] + '\n\n[...truncated]'

    # Build company context section if available
    if company_context:
        ctx_section = f"Company Website Context:\n{company_context}\n\n"
    else:
        ctx_section = ''

    prompt = EXTRACTION_PROMPT.replace('{jd_text}', jd_text).replace('{company_context_section}', ctx_section)

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': EXTRACTION_MODEL,
                'max_tokens': 1024,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # Extract text from response
        content = data.get('content', [])
        if not content:
            return None, 'empty_response'

        text = content[0].get('text', '')

        # Parse JSON from response
        # Handle possible markdown code block wrapping
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

        intel = json.loads(text)
        intel = filter_hallucinated_tools(intel, jd_text)
        return intel, 'success'

    except json.JSONDecodeError:
        return None, 'json_parse_error'
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 429:
            time.sleep(10)
            return extract_intel_from_jd(jd_text, job_title, company_name)
        return None, f'api_error_{status}'
    except Exception as e:
        return None, f'error: {str(e)}'


# =============================================================================
# ORCHESTRATION
# =============================================================================

def extract_all_intel(companies):
    """Extract intel from all scraped job descriptions"""
    results = []
    total_jobs = sum(
        1 for c in companies
        for j in c.get('jobs', [])
        if j.get('description')
    )
    processed = 0
    success = 0
    failed = 0

    print(f"\nExtracting intel from {total_jobs} job descriptions...")

    for company in companies:
        company_context = company.get('company_context', '')
        company_result = {
            'company_name': company['company_name'],
            'domain': company['domain'],
            'organization_id': company.get('organization_id', ''),
            'employee_count': company.get('employee_count'),
            'industry': company.get('industry', ''),
            'country': company.get('country', ''),
            'contacts': company.get('contacts', []),
            'company_context': company_context or None,
            'jobs': [],
        }

        for job in company.get('jobs', []):
            description = job.get('description')
            if not description:
                company_result['jobs'].append({
                    'title': job.get('title', ''),
                    'url': job.get('url', ''),
                    'intel': None,
                    'extract_status': 'no_description',
                })
                continue

            processed += 1
            title = job.get('title', '')
            print(f"  [{processed}/{total_jobs}] {company['company_name']} - {title}")

            intel, status = extract_intel_from_jd(
                description,
                job_title=title,
                company_name=company['company_name'],
                company_context=company_context,
            )

            if intel:
                # Override job_title with the one from the posting if extraction missed it
                if not intel.get('job_title') and title:
                    intel['job_title'] = title
                success += 1
                print(f"    -> extracted ({len(intel.get('pain_signals', []))} pain signals)")
            else:
                failed += 1
                print(f"    -> {status}")

            company_result['jobs'].append({
                'title': title,
                'url': job.get('url', ''),
                'intel': intel,
                'extract_status': status,
            })

            time.sleep(RATE_LIMIT_DELAY)

        if company_result['jobs']:
            results.append(company_result)

    print(f"\n  Extraction complete: {success} success, {failed} failed")
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Extract structured intel from job descriptions using Claude'
    )
    parser.add_argument('job_descriptions_json', help='Path to job_descriptions.json')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("HIRING INTEL - STEP 3: EXTRACT INTEL")
    print("=" * 70)

    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    input_path = Path(args.job_descriptions_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    total_companies = len(companies)
    total_jobs_with_desc = sum(
        1 for c in companies
        for j in c.get('jobs', [])
        if j.get('description')
    )
    total_jobs_without = sum(
        1 for c in companies
        for j in c.get('jobs', [])
        if not j.get('description')
    )

    est_cost = total_jobs_with_desc * 0.001  # ~$0.001 per extraction

    print(f"\nCompanies: {total_companies}")
    print(f"Jobs with descriptions: {total_jobs_with_desc}")
    print(f"Jobs without descriptions: {total_jobs_without} (skipped)")
    print(f"Model: {EXTRACTION_MODEL}")
    print(f"Estimated cost: ~${est_cost:.2f}")

    if not args.yes:
        print()
        response = input("Proceed with intel extraction? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Extract
    results = extract_all_intel(companies)

    # Save output alongside input
    output_path = input_path.parent / 'intel_extracted.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    companies_with_intel = sum(
        1 for c in results
        if any(j.get('intel') for j in c['jobs'])
    )
    total_intel = sum(
        1 for c in results
        for j in c['jobs']
        if j.get('intel')
    )

    print(f"\n{'=' * 70}")
    print("EXTRACTION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Companies with intel: {companies_with_intel}/{total_companies}")
    print(f"Jobs with intel: {total_intel}/{total_jobs_with_desc}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
