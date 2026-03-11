#!/usr/bin/env python3
"""
Find Personas - Find target contacts at validated companies.

For each company, finds up to 3 contacts via Apollo People Search:
  Priority 1: Head of Marketing / CMO / VP Marketing (1 leadership)
  Priority 2: Social Media Manager / Lead / Community Manager (2 social-level)

Contact-level dedup: skip contacts already in active Apollo sequences.
Attaches champion context to each contact.

Input: companies_validated.json (from validate_companies.py)
Output: personas_found.json

Usage:
    python find_personas.py <companies_json> [--yes]
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

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

RATE_LIMIT_DELAY = 1.0
MAX_CONTACTS_PER_COMPANY = 3

# Priority 1: Leadership titles (max 1)
LEADERSHIP_TITLES = [
    'head of marketing',
    'vp of marketing',
    'vp marketing',
    'marketing director',
    'director of marketing',
    'cmo',
    'chief marketing officer',
    'head of digital',
    'head of digital marketing',
]

# Priority 2: Social-level titles (max 2)
SOCIAL_TITLES = [
    'social media manager',
    'social media lead',
    'social media director',
    'social media strategist',
    'social media coordinator',
    'community manager',
    'content manager',
    'content marketing manager',
    'head of social',
    'head of social media',
    'director of social media',
    'social media specialist',
]


# =============================================================================
# APOLLO API
# =============================================================================

def apollo_headers():
    return {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
    }


def apollo_request(method, endpoint, json_data=None, params=None):
    url = f'{APOLLO_API_BASE}/{endpoint}'

    if json_data is not None:
        json_data['api_key'] = APOLLO_API_KEY
    if params is not None:
        params['api_key'] = APOLLO_API_KEY

    try:
        if method == 'GET':
            response = requests.get(
                url, headers=apollo_headers(),
                params=params or {'api_key': APOLLO_API_KEY},
                timeout=30,
            )
        else:
            response = requests.post(
                url, headers=apollo_headers(),
                json=json_data, timeout=60,
            )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        body = e.response.text[:300]
        print(f"  Apollo API error ({status}): {body}")
        if status == 429:
            print("  Rate limited. Waiting 60s...")
            time.sleep(60)
            return apollo_request(method, endpoint, json_data, params)
        raise
    except Exception as e:
        print(f"  Apollo request error: {e}")
        raise


# =============================================================================
# PEOPLE SEARCH
# =============================================================================

def search_people(domain, titles, max_results=5):
    """Search Apollo for people at a domain with specific titles"""
    try:
        data = apollo_request('POST', 'mixed_people/api_search', {
            'q_organization_domains': domain,
            'person_titles': titles,
            'page': 1,
            'per_page': max_results,
        })
        return data.get('people', [])
    except Exception as e:
        print(f"    People search error: {e}")
        return []


def check_contact_in_sequence(contact_id):
    """Check if a contact is already in an active sequence"""
    try:
        data = apollo_request('GET', f'contacts/{contact_id}', params={
            'api_key': APOLLO_API_KEY,
        })
        contact = data.get('contact', {})

        # Check for active sequence membership
        emailer_campaigns = contact.get('emailer_campaigns', []) or []
        for campaign in emailer_campaigns:
            status = (campaign.get('status') or '').lower()
            if status in ('active', 'running', 'in_progress'):
                return True

        return False

    except Exception:
        return False


# =============================================================================
# PERSONA FINDING
# =============================================================================

def find_contacts_for_company(domain):
    """Find up to 3 contacts at a company with priority ordering"""
    selected = []
    seen_ids = set()

    # Priority 1: Leadership (max 1)
    leadership = search_people(domain, LEADERSHIP_TITLES, max_results=3)
    time.sleep(RATE_LIMIT_DELAY)

    for person in leadership:
        pid = person.get('id')
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            selected.append(person)
            break  # Only 1 leadership contact

    # Priority 2: Social-level (fill remaining slots)
    remaining = MAX_CONTACTS_PER_COMPANY - len(selected)
    if remaining > 0:
        social = search_people(domain, SOCIAL_TITLES, max_results=5)
        time.sleep(RATE_LIMIT_DELAY)

        for person in social:
            pid = person.get('id')
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                selected.append(person)
                if len(selected) >= MAX_CONTACTS_PER_COMPANY:
                    break

    return selected


def find_all_personas(companies):
    """Find personas for all validated companies"""
    results = []
    total = len(companies)
    total_contacts = 0
    skipped_sequence = 0

    print(f"\nFinding personas for {total} companies...")

    for i, company in enumerate(companies, 1):
        name = company['company_name']
        domain = company['domain']

        print(f"  [{i}/{total}] {name} ({domain})")

        if not domain:
            print(f"    -> no domain, skipping")
            continue

        contacts = find_contacts_for_company(domain)

        if not contacts:
            print(f"    -> no contacts found")
            continue

        # Contact-level dedup: skip contacts in active sequences
        valid_contacts = []
        for contact in contacts:
            contact_id = contact.get('id')
            if not contact_id:
                continue

            in_sequence = check_contact_in_sequence(contact_id)
            time.sleep(RATE_LIMIT_DELAY)

            if in_sequence:
                contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                print(f"    -> skipped (in active sequence): {contact_name}")
                skipped_sequence += 1
                continue

            valid_contacts.append({
                'contact_id': contact_id,
                'first_name': contact.get('first_name', ''),
                'last_name': contact.get('last_name', ''),
                'email': contact.get('email', ''),
                'title': contact.get('title', ''),
                'linkedin_url': contact.get('linkedin_url', ''),
            })

        if valid_contacts:
            results.append({
                'company_name': name,
                'domain': domain,
                'organization_id': company.get('organization_id', ''),
                'employee_count': company.get('employee_count'),
                'industry': company.get('industry', ''),
                'country': company.get('country', ''),
                'champions': company['champions'],
                'contacts': valid_contacts,
            })
            total_contacts += len(valid_contacts)
            print(f"    -> {len(valid_contacts)} contact(s)")
        else:
            print(f"    -> all contacts in active sequences")

    print(f"\n  Persona search complete:")
    print(f"    Companies with contacts: {len(results)}/{total}")
    print(f"    Total contacts: {total_contacts}")
    print(f"    Skipped (in sequence): {skipped_sequence}")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Find target contacts at validated companies'
    )
    parser.add_argument('companies_json', help='Path to companies_validated.json')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 5: FIND PERSONAS")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    input_path = Path(args.companies_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    print(f"\nTarget companies: {len(companies)}")
    print(f"Max contacts per company: {MAX_CONTACTS_PER_COMPANY}")
    print(f"Priority: 1 leadership + 2 social-level")

    if not args.yes:
        print()
        response = input("Proceed with persona search? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Find personas
    results = find_all_personas(companies)

    # Save output
    output_path = input_path.parent / 'personas_found.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    total_contacts = sum(len(c['contacts']) for c in results)
    multi_champion = sum(1 for c in results if len(c['champions']) > 1)

    print(f"\n{'=' * 70}")
    print("PERSONA SEARCH COMPLETE")
    print(f"{'=' * 70}")
    print(f"Companies with contacts: {len(results)}/{len(companies)}")
    print(f"Total contacts found: {total_contacts}")
    print(f"Companies with multiple champions: {multi_champion}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
