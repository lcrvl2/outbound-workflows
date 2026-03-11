#!/usr/bin/env python3
"""
Push to Apollo - Save contacts and add to sequence.

Contacts are already found (from find_personas.py). This script:
1. Saves each contact to Apollo (POST /contacts) to get a saved contact ID
2. Optionally adds contacts to an Apollo sequence
3. Updates master file with processed companies

Input: personas_found.json (from find_personas.py)
Output: [source]_champions_master.csv (updated master)

Usage:
    python push_to_apollo.py <personas_json> --source NAME [--sequence-id ID] [--yes]
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
    return MASTER_DIR / f'{normalized}_champions_master.csv'


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
# CONTACT SAVE
# =============================================================================

def save_contact(contact, company_name):
    """Save a contact to Apollo's saved contacts (required before adding to sequence).
    Returns (saved_contact_id, status)."""
    try:
        data = apollo_request('POST', 'contacts', {
            'first_name': contact.get('first_name', ''),
            'last_name': contact.get('last_name', ''),
            'email': contact.get('email', ''),
            'organization_name': company_name,
            'title': contact.get('title', ''),
        })
        saved_id = data.get('contact', {}).get('id')
        if saved_id:
            return saved_id, 'success'
        return None, 'no_id_returned'
    except Exception as e:
        return None, f'error: {str(e)}'


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
        'domain', 'company_name', 'contacts_found', 'contacts_updated',
        'date_processed',
    ]

    existing_rows = []
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    all_rows = existing_rows + companies_processed

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    return master_path


# =============================================================================
# ORCHESTRATION
# =============================================================================

def push_all_to_apollo(companies, source_name, sequence_id=None):
    """Save contacts to Apollo and add to sequence."""
    master_rows = []
    total = len(companies)
    total_contacts = 0
    total_saved = 0
    sequence_contacts = []

    print(f"\nProcessing {total} companies...")

    for i, company in enumerate(companies, 1):
        name = company['company_name']
        domain = company['domain']
        contacts = company.get('contacts', [])

        if not contacts:
            print(f"  [{i}/{total}] {name}: no contacts, skipping")
            continue

        print(f"  [{i}/{total}] {name} ({len(contacts)} contacts)")

        saved = 0
        for contact in contacts:
            total_contacts += 1
            contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

            saved_id, status = save_contact(contact, name)

            if saved_id:
                saved += 1
                sequence_contacts.append(saved_id)
                print(f"    -> saved: {contact_name} ({contact.get('title', '')})")
            else:
                # If save fails, try using existing contact_id from find_personas
                existing_id = contact.get('contact_id')
                if existing_id:
                    sequence_contacts.append(existing_id)
                    saved += 1
                    print(f"    -> using existing id: {contact_name} ({status})")
                else:
                    print(f"    -> failed: {contact_name} ({status})")

            time.sleep(RATE_LIMIT_DELAY)

        total_saved += saved

        master_rows.append({
            'domain': domain,
            'company_name': name,
            'contacts_found': len(contacts),
            'contacts_updated': saved,
            'date_processed': date.today().isoformat(),
        })

    # Add to sequence
    sequence_added = 0
    if sequence_id and sequence_contacts:
        print(f"\n  Adding {len(sequence_contacts)} contacts to sequence {sequence_id}...")
        sequence_added = add_contacts_to_sequence(sequence_contacts, sequence_id)
        print(f"  -> {sequence_added} added to sequence")

    # Update master
    master_path = update_master(source_name, master_rows)

    return {
        'total_companies': total,
        'contacts_total': total_contacts,
        'contacts_updated': total_saved,
        'sequence_added': sequence_added,
        'master_path': str(master_path),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Push champion-angle emails to Apollo contacts'
    )
    parser.add_argument('personas_json', help='Path to personas_found.json (or emails_generated.json)')
    parser.add_argument('--source', required=True, help='Source name for master file')
    parser.add_argument('--sequence-id', default=None,
                        help='Apollo sequence ID to add contacts to')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 6: PUSH TO APOLLO")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    # Load personas
    input_path = Path(args.personas_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    # Filter to companies with contacts
    companies_with_contacts = [
        c for c in companies
        if c.get('contacts')
    ]

    # Check master for already-processed
    existing_domains = load_master_domains(args.source)
    new_companies = [
        c for c in companies_with_contacts
        if c['domain'].lower() not in existing_domains
    ]

    total_contacts = sum(
        len(c.get('contacts', []))
        for c in new_companies
    )

    print(f"\nSource: {args.source}")
    print(f"Companies with contacts: {len(companies_with_contacts)}")
    print(f"Already processed (in master): {len(companies_with_contacts) - len(new_companies)}")
    print(f"New companies to push: {len(new_companies)}")
    print(f"Contacts to save + enqueue: {total_contacts}")
    if args.sequence_id:
        print(f"Sequence ID: {args.sequence_id}")

    if not new_companies:
        print("\nNo new companies to process. Exiting.")
        sys.exit(0)

    # Preview
    print(f"\nTop 10 companies:")
    for i, c in enumerate(new_companies[:10], 1):
        contact_count = len(c.get('contacts', []))
        print(f"  {i}. {c['company_name']} ({c['domain']}) - {contact_count} contacts")
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
    print(f"Contacts updated: {stats['contacts_updated']}/{stats['contacts_total']}")
    if args.sequence_id:
        print(f"Added to sequence: {stats['sequence_added']}")
    print(f"Master updated: {stats['master_path']}")


if __name__ == '__main__':
    main()
