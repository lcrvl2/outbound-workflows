#!/usr/bin/env python3
"""
Generate Emails - Create champion-angle cold email sequences with hybrid personalization.

Two-part generation:
  Part A (per company): Email bodies based on champion context + industry
  Part B (per contact): Subject lines + opening sentences based on contact's role

Input: personas_found.json (from find_personas.py) + GTM playbook file
Output: emails_generated.json

Usage:
    python generate_emails.py <personas_json> --playbook <playbook_path> [--yes]
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

EMAIL_MODEL = 'claude-sonnet-4-5-20250929'

RATE_LIMIT_DELAY = 1.0


# =============================================================================
# CASE STUDIES
# =============================================================================

CASE_STUDIES = {
    'agency_scaling': (
        'Adtrak (UK agency, 51-200 employees): switched from Hootsuite, doubled social team '
        'from 3 to 7, now managing 100+ profiles for 400+ SME clients. Eliminated browser-switching '
        'chaos, streamlined onboarding for new social media managers.'
    ),
    'agency_cost': (
        'ClickMedia (Australian agency): switched from Sprout Social, achieved 25% cost reduction '
        'while improving ROI tracking across client accounts.'
    ),
    'agency_migration': (
        'Quimby Digital (US agency): migrated from Sprout Social to a better cost structure '
        'for multi-client management without losing workflow efficiency.'
    ),
    'ecommerce': (
        'E-commerce teams track which social posts drive revenue directly in Shopify/WooCommerce - '
        'teams report 30% savings vs previous tools while finally proving organic social ROI.'
    ),
    'b2b_saas': (
        'B2B marketing teams connect LinkedIn content to demo requests and pipeline in Salesforce - '
        'proving social\'s contribution to revenue for the first time.'
    ),
    'enterprise': (
        'Global brands govern 20+ social profiles across regions with centralized approval workflows '
        'and dedicated support, eliminating brand inconsistency.'
    ),
}


def select_case_studies(industry):
    """Select relevant case studies based on company industry"""
    industry_lower = (industry or '').lower()

    if any(kw in industry_lower for kw in ['agency', 'marketing & advertising',
                                            'advertising', 'media', 'pr ',
                                            'public relations', 'communications']):
        return '\n'.join([
            f'- {CASE_STUDIES["agency_scaling"]}',
            f'- {CASE_STUDIES["agency_cost"]}',
            f'- {CASE_STUDIES["agency_migration"]}',
        ])

    if any(kw in industry_lower for kw in ['ecommerce', 'e-commerce', 'retail',
                                            'consumer goods', 'food', 'beverage',
                                            'fashion', 'apparel']):
        return '\n'.join([
            f'- {CASE_STUDIES["ecommerce"]}',
            f'- {CASE_STUDIES["agency_cost"]}',
        ])

    if any(kw in industry_lower for kw in ['saas', 'software', 'technology',
                                            'information technology', 'computer',
                                            'internet', 'fintech']):
        return '\n'.join([
            f'- {CASE_STUDIES["b2b_saas"]}',
            f'- {CASE_STUDIES["agency_cost"]}',
        ])

    if any(kw in industry_lower for kw in ['enterprise', 'financial', 'banking',
                                            'insurance', 'healthcare', 'hospital',
                                            'pharmaceutical', 'automotive']):
        return '\n'.join([
            f'- {CASE_STUDIES["enterprise"]}',
            f'- {CASE_STUDIES["b2b_saas"]}',
        ])

    # Default
    return '\n'.join([
        f'- {CASE_STUDIES["agency_scaling"]}',
        f'- {CASE_STUDIES["ecommerce"]}',
        f'- {CASE_STUDIES["b2b_saas"]}',
    ])


# =============================================================================
# PLAYBOOK CONTEXT
# =============================================================================

def extract_playbook_context(industry=''):
    """Build condensed Agorapulse context for the email generation prompt."""
    case_studies = select_case_studies(industry)

    return f"""AGORAPULSE CONTEXT:

PRODUCT: Social media management platform. Only tool that tracks sales, leads,
and traffic directly attributed to organic social posts. 31,000+ users, 3,000+ agencies.

KEY DIFFERENTIATORS:
- ROI Attribution: only platform tracking revenue from organic social
- 30% avg cost savings vs Sprout Social/Hootsuite
- 96% support satisfaction, <30min response time
- Agency-optimized: unlimited profiles on Custom plan

COMPETITIVE POSITIONING:
vs Sprout Social: 30% lower cost, ROI attribution built-in (Sprout charges extra), better agency scaling
vs Hootsuite: simpler pricing, 9.0/10 ease of use (vs 7.9), built-in ROI tracking
vs Buffer: full suite (publish+engage+listen+report) vs scheduling only, enterprise features

CASE STUDIES:
{case_studies}

PERSONA PAIN POINTS (by vertical):
- Agencies: software costs eating margins, can't show client ROI, manual reporting stealing billable hours
- E-commerce: board asking "what's ROI of social?", attribution gaps, proving organic deserves budget
- B2B SaaS: board wants pipeline attribution, social treated as "brand" with no pipeline credit
- Enterprise: brand inconsistency across regions, approval bottlenecks, compliance requirements"""


# =============================================================================
# PROMPTS
# =============================================================================

COMPANY_BODY_PROMPT = """You are an expert B2B cold email writer. You write hyper-relevant, concise cold email sequences using the "champion" angle.

## CHAMPION CONTEXT

A "champion" is someone who previously worked at the target company and is now a closed-won customer using Agorapulse. Their success lends credibility, but we NEVER reveal who they are.

{champion_phrasing}

## CHAMPION PRIVACY RULES (Non-Negotiable)

- NEVER name any champion
- NEVER mention the champion's current role or title
- NEVER mention the champion's current company
- NEVER offer an introduction to the champion
- ONLY allowed phrasings: "someone who used to work at {{{{companyName}}}}", "a former {{{{companyName}}}} team member", or plural equivalents
- The champion angle is a door opener - the product value must stand on its own

## HARD RULES (Non-Negotiable)

- Email 1: Max 120 words
- Email 2: Max 80 words
- Email 3: Max 120 words
- Max 2 lines per paragraph
- Exactly ONE question mark per email
- Regular dash only (never em dash)
- NO exclamation marks
- NO emojis
- NO formal sign-offs or signatures
- NO generic compliments
- NO filler phrases ("just checking in", "circling back", "wanted to reach out")
- NO unsupported ROI claims or made-up metrics
- ONLY use numbers/percentages that appear VERBATIM in the CASE STUDIES or PLAYBOOK CONTEXT below
- NO placeholders like [Company] - use {{{{companyName}}}} merge tag
- NO references to job postings or hiring

## THREE-EMAIL STRUCTURE

**Email 1 body: "The Insider"**
- Reference that {champion_ref} now uses Agorapulse
- Frame the value their team gets from it
- Connect to the target company's likely situation (based on industry/size)
- Ends with soft interest check CTA

**Email 2 body: "The Proof Point"** (same thread, NO subject line)
- Short case study aligned with their industry/size
- Shows concrete outcomes, not features
- Implicitly connects to their situation
- No explicit CTA - ends with a single question

**Email 3 body: "Social Proof + FOMO"** (new thread)
- Frame: "Companies like [type] are already doing X"
- Create urgency through industry momentum, not artificial pressure
- Easy out or easy in CTA
- Do NOT offer a champion introduction

## PLAYBOOK CONTEXT

{playbook_context}

## TARGET COMPANY

- Company: {{{{companyName}}}} ({employee_count} employees, {industry})
- Country: {country}
- Champions: {champion_count} former employee(s) now using Agorapulse

## OUTPUT FORMAT

Return ONLY valid JSON with EXACTLY these 3 fields:

{{
  "email_1_body": "Body of email 1 (after the opening sentence). Use {{{{companyName}}}} merge tag.",
  "email_2_body": "Full email 2 body.",
  "email_3_body": "Body of email 3 (after the opening sentence). Use {{{{companyName}}}} merge tag."
}}

BEFORE returning, verify each email:
- Has exactly ONE question mark (count them)
- Has no paragraph longer than 2 lines
- Contains ZERO numbers/percentages not found verbatim in CASE STUDIES or PLAYBOOK CONTEXT above
- NEVER names any champion or hints at their identity"""


CONTACT_OPENER_PROMPT = """You are an expert B2B cold email writer creating personalized subject lines and opening sentences.

## CONTEXT

You are personalizing emails for a contact at {{{{companyName}}}}. The email bodies are already written - you just need subject lines and opening sentences tailored to this specific person.

## HARD RULES

- Subject lines: 2-4 words, segment-relevant, NOT about champions or former colleagues
- Opening sentences: 1 sentence max, references their role/situation naturally
- Use {{{{firstName}}}} and {{{{companyName}}}} merge tags
- NO exclamation marks
- NO emojis
- NO generic compliments
- NO questions in subject lines

## CONTACT

- Name: {{{{firstName}}}} (merge tag)
- Title: {contact_title}
- Company: {{{{companyName}}}} ({industry})

## EMAIL ANGLES

- Email 1 "The Insider": Subject about their role/industry reality. Opener about their situation.
- Email 3 "Social Proof + FOMO": Different angle from Email 1. Subject about industry momentum. Opener about what similar teams are doing.

## OUTPUT FORMAT

Return ONLY valid JSON:

{{
  "email_1_subject": "2-4 word subject",
  "email_1_opener": "Personalized opening sentence.",
  "email_3_subject": "2-4 word subject (different angle)",
  "email_3_opener": "Personalized opening sentence."
}}"""


# =============================================================================
# HELPERS
# =============================================================================

def load_playbook(playbook_path):
    """Load GTM playbook content"""
    with open(playbook_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_champion_addendum():
    """Load champion addendum and append to playbook"""
    addendum_path = SKILL_DIR / 'references' / 'champion_addendum.md'
    if addendum_path.exists():
        with open(addendum_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


def parse_json_response(text):
    """Parse JSON from Claude response, handling markdown blocks and trailing commas"""
    text = text.strip()

    # Handle markdown code block wrapping
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

    # Extract JSON object
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    # Fix trailing commas
    text = re.sub(r',\s*}', '}', text)

    return json.loads(text)


def build_champion_context(champions):
    """Build champion phrasing based on count"""
    count = len(champions)
    if count > 1:
        return {
            'phrasing': (
                f'There are {count} former employees of the target company now using Agorapulse.\n'
                'Use PLURAL phrasing:\n'
                '- "multiple people who\'ve worked at {{companyName}} before"\n'
                '- "several former {{companyName}} team members"\n'
                '- "it\'s not a coincidence that several former {{companyName}} team members ended up choosing us"'
            ),
            'ref': f'multiple people who used to work at {{{{companyName}}}}',
        }
    else:
        return {
            'phrasing': (
                'There is 1 former employee of the target company now using Agorapulse.\n'
                'Use SINGULAR phrasing:\n'
                '- "someone who used to work at {{companyName}}"\n'
                '- "a former {{companyName}} team member"'
            ),
            'ref': f'someone who used to work at {{{{companyName}}}}',
        }


# =============================================================================
# CLAUDE API
# =============================================================================

def call_claude(prompt, max_tokens=1500):
    """Make a Claude API call and return parsed JSON"""
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
                'max_tokens': max_tokens,
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
        result = parse_json_response(text)
        return result, 'success'

    except json.JSONDecodeError:
        return None, 'json_parse_error'
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 429:
            print("    Rate limited. Waiting 30s...")
            time.sleep(30)
            return call_claude(prompt, max_tokens)
        return None, f'api_error_{status}'
    except Exception as e:
        return None, f'error: {str(e)}'


def generate_company_bodies(company, playbook_content):
    """Part A: Generate email bodies for a target company (shared across all contacts)"""
    champions = company.get('champions', [])
    champion_ctx = build_champion_context(champions)
    industry = company.get('industry', 'unknown')

    prompt = COMPANY_BODY_PROMPT.format(
        champion_phrasing=champion_ctx['phrasing'],
        champion_ref=champion_ctx['ref'],
        playbook_context=extract_playbook_context(industry),
        employee_count=company.get('employee_count', 'unknown'),
        industry=industry,
        country=company.get('country', 'unknown'),
        champion_count=len(champions),
    )

    result, status = call_claude(prompt, max_tokens=1500)

    if result:
        required = ['email_1_body', 'email_2_body', 'email_3_body']
        for field in required:
            if field not in result:
                return None, f'missing_field_{field}'

    return result, status


def generate_contact_openers(contact, company):
    """Part B: Generate personalized subject lines + openers for a contact"""
    industry = company.get('industry', 'unknown')

    prompt = CONTACT_OPENER_PROMPT.format(
        contact_title=contact.get('title', 'unknown'),
        industry=industry,
    )

    result, status = call_claude(prompt, max_tokens=500)

    if result:
        required = ['email_1_subject', 'email_1_opener', 'email_3_subject', 'email_3_opener']
        for field in required:
            if field not in result:
                return None, f'missing_field_{field}'

    return result, status


# =============================================================================
# ORCHESTRATION
# =============================================================================

def generate_all_emails(companies, playbook_content):
    """Generate emails for all companies with hybrid personalization"""
    results = []
    total = len(companies)
    total_contacts = 0
    success_contacts = 0
    failed_bodies = 0
    failed_openers = 0

    print(f"\nGenerating champion-angle emails for {total} companies...")

    for i, company in enumerate(companies, 1):
        name = company['company_name']
        contacts = company.get('contacts', [])
        champion_count = len(company.get('champions', []))

        print(f"  [{i}/{total}] {name} ({len(contacts)} contacts, {champion_count} champion{'s' if champion_count > 1 else ''})")

        if not contacts:
            print(f"    -> no contacts, skipping")
            continue

        # Part A: Generate company-level bodies
        bodies, body_status = generate_company_bodies(company, playbook_content)
        time.sleep(RATE_LIMIT_DELAY)

        if not bodies:
            failed_bodies += 1
            print(f"    -> body generation failed: {body_status}")
            continue

        print(f"    -> bodies generated")

        # Part B: Generate per-contact openers
        company_result = {
            'company_name': name,
            'domain': company['domain'],
            'organization_id': company.get('organization_id', ''),
            'employee_count': company.get('employee_count'),
            'industry': company.get('industry', ''),
            'country': company.get('country', ''),
            'champions': company['champions'],
            'contacts': [],
        }

        for contact in contacts:
            total_contacts += 1
            contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

            openers, opener_status = generate_contact_openers(contact, company)
            time.sleep(RATE_LIMIT_DELAY)

            if not openers:
                failed_openers += 1
                print(f"    -> opener failed for {contact_name}: {opener_status}")
                company_result['contacts'].append({
                    **contact,
                    'emails': None,
                    'email_status': opener_status,
                })
                continue

            # Merge bodies + openers into final email set
            emails = {
                'email_1_subject': openers['email_1_subject'],
                'email_1_opener': openers['email_1_opener'],
                'email_1_body': bodies['email_1_body'],
                'email_2_body': bodies['email_2_body'],
                'email_3_subject': openers['email_3_subject'],
                'email_3_opener': openers['email_3_opener'],
                'email_3_body': bodies['email_3_body'],
            }

            success_contacts += 1
            company_result['contacts'].append({
                **contact,
                'emails': emails,
                'email_status': 'success',
            })
            print(f"    -> {contact_name}: \"{openers['email_1_subject']}\"")

        results.append(company_result)

    print(f"\n  Generation complete:")
    print(f"    Companies processed: {total}")
    print(f"    Body generation failures: {failed_bodies}")
    print(f"    Contacts with emails: {success_contacts}/{total_contacts}")
    print(f"    Opener failures: {failed_openers}")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate champion-angle cold email sequences'
    )
    parser.add_argument('personas_json', help='Path to personas_found.json')
    parser.add_argument('--playbook', required=True,
                        help='Path to GTM playbook markdown file')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 6: GENERATE EMAILS")
    print("=" * 70)

    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    # Load personas
    input_path = Path(args.personas_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    # Load playbook + champion addendum
    playbook_path = Path(args.playbook)
    if not playbook_path.exists():
        print(f"Error: Playbook not found: {playbook_path}")
        sys.exit(1)

    playbook_content = load_playbook(playbook_path)
    addendum = load_champion_addendum()
    if addendum:
        playbook_content += f"\n\n---\n\n{addendum}"

    # Stats
    total_companies = len(companies)
    total_contacts = sum(len(c.get('contacts', [])) for c in companies)
    multi_champion = sum(1 for c in companies if len(c.get('champions', [])) > 1)

    # Cost estimate: ~$0.003/company (body) + ~$0.001/contact (opener)
    est_cost = total_companies * 0.003 + total_contacts * 0.001

    print(f"\nCompanies: {total_companies}")
    print(f"Total contacts: {total_contacts}")
    print(f"Multi-champion companies: {multi_champion}")
    print(f"Playbook: {playbook_path.name} ({len(playbook_content)} chars)")
    print(f"Model: {EMAIL_MODEL}")
    print(f"Estimated cost: ~${est_cost:.2f}")
    print(f"API calls: {total_companies} (bodies) + {total_contacts} (openers)")

    if not args.yes:
        print()
        response = input("Proceed with email generation? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Generate
    results = generate_all_emails(companies, playbook_content)

    # Save output
    output_path = input_path.parent / 'emails_generated.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    success_contacts = sum(
        1 for c in results
        for contact in c.get('contacts', [])
        if contact.get('emails')
    )

    print(f"\n{'=' * 70}")
    print("EMAIL GENERATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Companies: {len(results)}/{total_companies}")
    print(f"Contacts with emails: {success_contacts}/{total_contacts}")
    print(f"Output: {output_path}")

    # Show sample
    for company in results:
        for contact in company.get('contacts', []):
            if contact.get('emails'):
                name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                print(f"\n--- Sample: {name} at {company['company_name']} ---")
                print(f"Subject 1: {contact['emails']['email_1_subject']}")
                print(f"Opener 1: {contact['emails']['email_1_opener']}")
                body1 = contact['emails']['email_1_body']
                preview = body1[:150] + '...' if len(body1) > 150 else body1
                print(f"Body 1: {preview}")
                break
        else:
            continue
        break


if __name__ == '__main__':
    main()
