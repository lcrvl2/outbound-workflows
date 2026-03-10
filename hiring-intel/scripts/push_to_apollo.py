#!/usr/bin/env python3
"""
Push to Apollo - Update contact custom fields with generated emails and add to sequence.

1. For each company, find contacts in Apollo (People Search by domain + title)
2. Update each contact's custom fields with generated email bodies
3. Optionally add contacts to a hiring-intel sequence
4. Update master file with processed companies

Input: emails_generated.json (from generate_emails.py)
Output: [source]_hiring_master.csv (updated master)

Usage:
    python push_to_apollo.py <emails_json> --source NAME [--sequence-id ID] [--yes]
"""

import json
import csv
import sys
import os
import re
import time
import argparse
import requests
from pathlib import Path
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
MASTER_DIR = SKILL_DIR / 'master'

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

RATE_LIMIT_DELAY = 1.0

# Social media persona titles for people search
PERSONA_TITLES = [
    'social media manager',
    'social media coordinator',
    'community manager',
    'content manager',
    'social media strategist',
    'head of social',
    'social media specialist',
    'social media director',
    'social media lead',
    'director of social media',
    'vp of marketing',
    'head of marketing',
    'marketing director',
    'cmo',
]

# Custom field IDs in Apollo (PATCH requires field IDs, not names)
CUSTOM_FIELD_IDS = {
    'email_1_body': '698da90737e1ef000d656492',    # outbound_email_1_body
    'email_2_body': '698da91367e36600151d3167',    # outbound_email_2_body
    'email_3_body': '698da91df035d70015a9a380',    # outbound_email_3_body
}


# =============================================================================
# HELPERS
# =============================================================================

def normalize_source_name(source_name):
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_master_path(source_name):
    normalized = normalize_source_name(source_name)
    return MASTER_DIR / f'{normalized}_hiring_master.csv'


def load_master_domains(source_name):
    master_path = get_master_path(source_name)
    domains = set()
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get('domain', '').strip().lower()
                if domain:
                    domains.add(domain)
    return domains


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
        elif method == 'PATCH':
            headers = apollo_headers()
            headers['x-api-key'] = APOLLO_API_KEY
            response = requests.patch(
                url, headers=headers,
                json=json_data, timeout=60,
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

def find_contacts_by_domain(domain, max_results=5):
    """Find contacts at a company by domain + social media titles"""
    search_params = {
        'page': 1,
        'per_page': max_results,
        'q_organization_domains': domain,
        'person_titles': PERSONA_TITLES,
    }

    try:
        data = apollo_request('POST', 'mixed_people/api_search', search_params)
        people = data.get('people', [])
        return people
    except Exception as e:
        print(f"    People search error: {e}")
        return []


# =============================================================================
# CONTACT UPDATE
# =============================================================================

def update_contact_custom_fields(contact_id, emails):
    """Update a contact's custom fields with generated emails.
    Uses PATCH with typed_custom_fields dict {field_id: value}.
    """
    typed_fields = {
        CUSTOM_FIELD_IDS['email_1_body']: emails.get('email_1_body', ''),
        CUSTOM_FIELD_IDS['email_2_body']: emails.get('email_2_body', ''),
        CUSTOM_FIELD_IDS['email_3_body']: emails.get('email_3_body', ''),
    }
    typed_fields = {k: v for k, v in typed_fields.items() if v}

    if not typed_fields:
        return False, 'no_fields_to_update'

    try:
        apollo_request('PATCH', f'contacts/{contact_id}', {
            'typed_custom_fields': typed_fields,
        })
        return True, 'success'
    except Exception as e:
        return False, f'error: {str(e)}'


# =============================================================================
# SEQUENCE
# =============================================================================

def add_contacts_to_sequence(contact_ids, sequence_id):
    """Add contacts to an Apollo sequence"""
    if not sequence_id or not contact_ids:
        return 0

    try:
        data = apollo_request('POST', 'emailer_campaigns/add_contact_ids', {
            'contact_ids': contact_ids,
            'emailer_campaign_id': sequence_id,
        })
        added = len(data.get('contacts', []))
        return added
    except Exception as e:
        print(f"  Sequence add error: {e}")
        return 0


# =============================================================================
# MASTER FILE
# =============================================================================

def update_master(source_name, companies_processed):
    """Append processed companies to master file"""
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    master_path = get_master_path(source_name)

    fieldnames = [
        'domain', 'company_name', 'organization_id', 'employee_count',
        'industry', 'country', 'contacts_found', 'contacts_updated',
        'date_processed',
    ]

    # Load existing
    existing_rows = []
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    # Deduplicate: new rows override existing ones with the same domain
    existing_domains = {row['domain'] for row in companies_processed}
    filtered_existing = [r for r in existing_rows if r.get('domain') not in existing_domains]
    all_rows = filtered_existing + companies_processed

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    return master_path


# =============================================================================
# ORCHESTRATION
# =============================================================================

def push_all_to_apollo(companies, source_name, sequence_id=None):
    """Push generated emails to Apollo contacts"""
    results = []
    master_rows = []
    total = len(companies)
    total_contacts_found = 0
    total_contacts_updated = 0
    sequence_contacts = []

    print(f"\nProcessing {total} companies...")

    for i, company in enumerate(companies, 1):
        name = company['company_name']
        domain = company['domain']
        emails = company.get('emails')

        if not emails:
            print(f"  [{i}/{total}] {name}: no emails, skipping")
            continue

        print(f"  [{i}/{total}] {name} ({domain})")

        # Use pre-loaded contacts from list-based flow, or search by domain
        preloaded = company.get('contacts', [])
        if preloaded:
            contacts = [{'id': c['contact_id'], 'first_name': c.get('first_name', ''),
                         'last_name': c.get('last_name', ''), 'title': c.get('title', '')}
                        for c in preloaded if c.get('contact_id')]
            print(f"    Using {len(contacts)} pre-loaded contact(s)")
        else:
            contacts = find_contacts_by_domain(domain)
        total_contacts_found += len(contacts)

        if not contacts:
            print(f"    -> no contacts found")
            master_rows.append({
                'domain': domain,
                'company_name': name,
                'organization_id': company.get('organization_id', ''),
                'employee_count': company.get('employee_count', ''),
                'industry': company.get('industry', ''),
                'country': company.get('country', ''),
                'contacts_found': 0,
                'contacts_updated': 0,
                'date_processed': date.today().isoformat(),
            })
            continue

        # Update each contact
        updated = 0
        for contact in contacts:
            contact_id = contact.get('id')
            contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

            if not contact_id:
                continue

            success, status = update_contact_custom_fields(
                contact_id, emails
            )

            if success:
                updated += 1
                sequence_contacts.append(contact_id)
                print(f"    -> updated: {contact_name} ({contact.get('title', '')})")
            else:
                print(f"    -> failed: {contact_name} ({status})")

            time.sleep(RATE_LIMIT_DELAY)

        total_contacts_updated += updated

        master_rows.append({
            'domain': domain,
            'company_name': name,
            'organization_id': company.get('organization_id', ''),
            'employee_count': company.get('employee_count', ''),
            'industry': company.get('industry', ''),
            'country': company.get('country', ''),
            'contacts_found': len(contacts),
            'contacts_updated': updated,
            'date_processed': date.today().isoformat(),
        })

    # Add to sequence if specified
    sequence_added = 0
    if sequence_id and sequence_contacts:
        print(f"\n  Adding {len(sequence_contacts)} contacts to sequence {sequence_id}...")
        sequence_added = add_contacts_to_sequence(sequence_contacts, sequence_id)
        print(f"  -> {sequence_added} added to sequence")

    # Update master
    master_path = update_master(source_name, master_rows)

    return {
        'total_companies': total,
        'contacts_found': total_contacts_found,
        'contacts_updated': total_contacts_updated,
        'sequence_added': sequence_added,
        'master_path': str(master_path),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Push generated emails to Apollo contacts and optionally add to sequence'
    )
    parser.add_argument('emails_json', help='Path to emails_generated.json')
    parser.add_argument('--source', required=True, help='Source name for master file')
    parser.add_argument('--sequence-id', default=None,
                        help='Apollo sequence ID to add contacts to')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("HIRING INTEL - STEP 5: PUSH TO APOLLO")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    # Load emails
    input_path = Path(args.emails_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    # Filter to companies with generated emails
    companies_with_emails = [c for c in companies if c.get('emails')]

    # Check master for already-processed
    existing_domains = load_master_domains(args.source)
    new_companies = [
        c for c in companies_with_emails
        if c['domain'].lower() not in existing_domains
    ]

    print(f"\nSource: {args.source}")
    print(f"Companies with emails: {len(companies_with_emails)}")
    print(f"Already processed (in master): {len(companies_with_emails) - len(new_companies)}")
    print(f"New companies to push: {len(new_companies)}")
    if args.sequence_id:
        print(f"Sequence ID: {args.sequence_id}")

    if not new_companies:
        print("\nNo new companies to process. Exiting.")
        sys.exit(0)

    # Preview
    print(f"\nTop 10 companies:")
    for i, c in enumerate(new_companies[:10], 1):
        print(f"  {i}. {c['company_name']} ({c['domain']})")
    if len(new_companies) > 10:
        print(f"  ... and {len(new_companies) - 10} more")

    if not args.yes:
        print()
        response = input("Proceed with Apollo push? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Push
    stats = push_all_to_apollo(new_companies, args.source, args.sequence_id)

    # Summary
    print(f"\n{'=' * 70}")
    print("PUSH COMPLETE")
    print(f"{'=' * 70}")
    print(f"Companies processed: {stats['total_companies']}")
    print(f"Contacts found: {stats['contacts_found']}")
    print(f"Contacts updated: {stats['contacts_updated']}")
    if args.sequence_id:
        print(f"Added to sequence: {stats['sequence_added']}")
    print(f"Master updated: {stats['master_path']}")


if __name__ == '__main__':
    main()
