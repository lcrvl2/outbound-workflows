#!/usr/bin/env python3
"""
Find Personas - Search Apollo for decision-makers at ICP-qualified companies.

For each qualified company, find 2-3 decision-makers using target persona titles.
Prioritizes by seniority (CMO > VP > Director > Manager).

Input: companies_qualified.json (from qualify_companies.py)
Output: personas_found.json

Usage:
    python find_personas.py <input_json> <output_json> \
        [--contacts-per-company N] \
        [--persona-titles "title1,title2,title3"]
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

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

RATE_LIMIT_DELAY = 1.0

DEFAULT_CONTACTS_PER_COMPANY = 3

# Persona titles (prioritized by seniority)
DEFAULT_PERSONA_TITLES = [
    # C-level
    'CMO',
    'Chief Marketing Officer',

    # VP level
    'VP Marketing',
    'VP of Marketing',
    'Vice President Marketing',
    'Vice President of Marketing',

    # Director level
    'Director Marketing',
    'Director of Marketing',
    'Marketing Director',
    'Head of Social',
    'Head of Social Media',
    'Director Social Media',
    'Director of Social Media',
    'Social Media Director',

    # Manager level
    'Social Media Manager',
    'Content Manager',
    'Community Manager',
    'Social Media Lead',
    'Social Media Strategist',
]

# Seniority priority mapping (lower = higher priority)
SENIORITY_PRIORITY = {
    'cmo': 1,
    'chief marketing officer': 1,
    'vp': 2,
    'vice president': 2,
    'head of': 3,
    'director': 4,
    'manager': 5,
    'lead': 6,
    'strategist': 6,
    'coordinator': 7,
    'specialist': 8,
}


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
# PERSONA SEARCH
# =============================================================================

def get_seniority_priority(title):
    """Get seniority priority score for a title (lower = higher seniority)"""
    if not title:
        return 999

    title_lower = title.lower()

    for keyword, priority in SENIORITY_PRIORITY.items():
        if keyword in title_lower:
            return priority

    return 999  # Unknown seniority


def find_personas_for_company(domain, persona_titles, max_results):
    """
    Find decision-makers at a company by domain + persona titles.

    Returns list of contacts sorted by seniority (highest first).
    """
    search_params = {
        'page': 1,
        'per_page': max_results * 2,  # Request extra to account for filtering
        'q_organization_domains': domain,
        'person_titles': persona_titles,
    }

    try:
        data = apollo_request('POST', 'mixed_people/search', search_params)
        people = data.get('people', [])

        if not people:
            return []

        # Extract contact data
        contacts = []
        for person in people:
            contact = {
                'contact_id': person.get('id'),
                'first_name': person.get('first_name', ''),
                'last_name': person.get('last_name', ''),
                'name': person.get('name', ''),
                'title': person.get('title', ''),
                'email': person.get('email'),
                'phone': person.get('phone_numbers', [{}])[0].get('raw_number') if person.get('phone_numbers') else None,
                'linkedin_url': person.get('linkedin_url', ''),
                'seniority': person.get('seniority', ''),
                'seniority_priority': get_seniority_priority(person.get('title', '')),
            }
            contacts.append(contact)

        # Sort by seniority (lower priority number = higher seniority)
        contacts.sort(key=lambda c: c['seniority_priority'])

        # Return top N contacts
        return contacts[:max_results]

    except Exception as e:
        print(f"    Persona search error: {e}")
        return []


# =============================================================================
# ORCHESTRATION
# =============================================================================

def find_all_personas(companies, persona_titles, contacts_per_company):
    """Find personas for all qualified companies"""
    results = []
    stats = {
        'total_companies': len(companies),
        'contacts_found': 0,
        'companies_with_contacts': 0,
        'companies_without_contacts': 0,
    }

    print(f"\n  Finding {contacts_per_company} contact(s) per company...")
    print(f"  Target titles: {', '.join(persona_titles[:5])}{'...' if len(persona_titles) > 5 else ''}")

    for i, company in enumerate(companies, 1):
        company_name = company['company_name']
        domain = company['domain']

        if i % 10 == 0:
            print(f"    Progress: {i}/{stats['total_companies']}")

        # Find personas
        contacts = find_personas_for_company(domain, persona_titles, contacts_per_company)

        if contacts:
            stats['contacts_found'] += len(contacts)
            stats['companies_with_contacts'] += 1
        else:
            stats['companies_without_contacts'] += 1

        # Store company + contacts
        results.append({
            'company_name': company_name,
            'domain': domain,
            'organization_id': company.get('organization_id'),
            'employee_count': company.get('employee_count'),
            'industry': company.get('industry'),
            'country': company.get('country'),
            'follower_count': company.get('follower_count'),
            'source_competitors': company.get('source_competitors', []),
            'contacts': contacts,
        })

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    return results, stats


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Find decision-makers at ICP-qualified companies via Apollo'
    )
    parser.add_argument('input_json', help='Input JSON file (companies_qualified.json)')
    parser.add_argument('output_json', help='Output JSON file (personas_found.json)')
    parser.add_argument(
        '--contacts-per-company',
        type=int,
        default=DEFAULT_CONTACTS_PER_COMPANY,
        help=f'Max contacts per company (default: {DEFAULT_CONTACTS_PER_COMPANY})',
    )
    parser.add_argument(
        '--persona-titles',
        default=None,
        help='Comma-separated list of target titles (overrides defaults)',
    )

    args = parser.parse_args()

    print("=" * 70)
    print("FIND DECISION-MAKERS (PERSONAS)")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    # Load input
    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    # Parse persona titles
    if args.persona_titles:
        persona_titles = [t.strip() for t in args.persona_titles.split(',') if t.strip()]
    else:
        persona_titles = DEFAULT_PERSONA_TITLES

    print(f"\nQualified companies: {len(companies)}")
    print(f"Contacts per company: {args.contacts_per_company}")
    print(f"Target persona titles: {len(persona_titles)}")

    # Find personas
    results, stats = find_all_personas(companies, persona_titles, args.contacts_per_company)

    # Summary
    print(f"\n{'=' * 70}")
    print("PERSONA SEARCH RESULTS")
    print(f"{'=' * 70}")
    print(f"Companies processed: {stats['total_companies']}")
    print(f"Companies with contacts: {stats['companies_with_contacts']}")
    print(f"Companies without contacts: {stats['companies_without_contacts']}")
    print(f"Total contacts found: {stats['contacts_found']}")

    if stats['companies_with_contacts'] > 0:
        avg_contacts = stats['contacts_found'] / stats['companies_with_contacts']
        print(f"Average contacts per company: {avg_contacts:.1f}")

    if stats['companies_with_contacts'] > 0:
        coverage = (stats['companies_with_contacts'] / stats['total_companies']) * 100
        print(f"\nContact coverage: {coverage:.1f}%")

    # Save output
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(results)} companies (with contacts) to: {output_path}")


if __name__ == '__main__':
    main()
