#!/usr/bin/env python3
"""
Push to Apollo - Update job changers with new company/title and add to enriched list.

1. Read job_changers.csv
2. For each contact:
   a. If found in Apollo CRM by email → update organization_name + title + add to list
   b. If NOT found → create new contact with LinkedIn-detected data + add to list
3. Both paths land in the same enriched list (apollo-job-changer-processor picks up)

The enriched list is then picked up by the existing apollo-job-changer-processor
Phase 2 workflow (filter verified → push to Salesforce → add to campaign).

Input: job_changers.csv (from detect_job_changes.py)
Output: push summary + master tracking

Usage:
    python push_to_apollo.py <csv_path> --source NAME [--list-id ID] [--yes]
"""

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

# Default enriched list — same destination as apollo-job-changer-processor
DEFAULT_LIST_ID = '698217a1703af3002135f177'

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
    return MASTER_DIR / f'{normalized}_apollo_push_master.csv'


def load_master_emails(source_name):
    master_path = get_master_path(source_name)
    emails = set()
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get('email', '').strip().lower()
                if email:
                    emails.add(email)
    return emails


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
        elif method == 'PUT':
            response = requests.put(
                url, headers=apollo_headers(),
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
# CONTACT OPERATIONS
# =============================================================================

def find_contact_by_email(email):
    """Find an Apollo CRM contact by email using contacts/search"""
    try:
        data = apollo_request('POST', 'contacts/search', {
            'q_keywords': email,
            'page': 1,
            'per_page': 1,
        })
        contacts = data.get('contacts', [])
        if not contacts:
            return None
        contact = contacts[0]
        # Verify email matches (search is keyword-based, not exact)
        contact_emails = [
            (contact.get('email') or '').lower(),
        ] + [
            (e.get('email') or '').lower()
            for e in (contact.get('contact_emails') or [])
        ]
        if email.lower() not in contact_emails:
            return None
        # Capture existing label_ids for merge
        raw_labels = contact.get('label_ids') or []
        existing_label_ids = [l for l in raw_labels if isinstance(l, str)]
        return {
            'id': contact['id'],
            'first_name': contact.get('first_name', ''),
            'last_name': contact.get('last_name', ''),
            'title': contact.get('title', ''),
            'organization_name': (contact.get('account', {}) or {}).get('name', '') or contact.get('organization_name', ''),
            'label_ids': existing_label_ids,
        }
    except Exception as e:
        print(f"    Search error: {e}")
        return None


def update_and_add_to_list(contact_id, new_company, new_title, existing_label_ids, list_id):
    """Update company/title AND add to list in a single PUT call"""
    merged_labels = list(set(existing_label_ids + [list_id]))
    try:
        apollo_request('PUT', f'contacts/{contact_id}', {
            'organization_name': new_company,
            'title': new_title,
            'label_ids': merged_labels,
        })
        return True, 'updated'
    except Exception as e:
        return False, f'update_error: {str(e)[:100]}'


def parse_name(full_name):
    """Split 'First Last' into (first_name, last_name). Handles single names."""
    parts = full_name.strip().split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0] if parts else '', ''


def create_contact(name, email, new_company, new_title, list_id):
    """Create a new Apollo CRM contact with LinkedIn-detected data + add to list"""
    first_name, last_name = parse_name(name)
    try:
        data = apollo_request('POST', 'contacts', {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'organization_name': new_company,
            'title': new_title,
            'label_ids': [list_id],
        })
        contact = data.get('contact', {})
        contact_id = contact.get('id', '')
        return True, 'created', contact_id
    except Exception as e:
        return False, f'create_error: {str(e)[:100]}', ''


# =============================================================================
# CSV LOADING
# =============================================================================

def load_job_changers(csv_path):
    """Load job changers from CSV"""
    contacts = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            contacts.append({
                'name': row.get('name', '').strip(),
                'email': row.get('email', '').strip().lower(),
                'old_company': row.get('old_company', '').strip(),
                'new_company': row.get('new_company', '').strip(),
                'new_title': row.get('new_title', '').strip(),
                'linkedin_url': row.get('linkedin_url', '').strip(),
                'mrr': row.get('mrr', '').strip(),
                'country': row.get('country', '').strip(),
                'plan': row.get('plan', '').strip(),
            })
    return contacts


# =============================================================================
# MASTER FILE
# =============================================================================

def update_master(source_name, rows):
    """Append processed contacts to master file"""
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    master_path = get_master_path(source_name)

    fieldnames = [
        'email', 'name', 'old_company', 'new_company', 'new_title',
        'contact_id', 'status', 'date_processed',
    ]

    existing_rows = []
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    all_rows = existing_rows + rows

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    return master_path


# =============================================================================
# MAIN PUSH LOGIC
# =============================================================================

def push_contacts(contacts, list_id):
    """Process each job changer: find → update → add to list (or create if not found)"""
    results = {
        'updated': [],
        'created': [],
        'update_failed': [],
        'create_failed': [],
    }
    master_rows = []
    total = len(contacts)

    for i, contact in enumerate(contacts, 1):
        name = contact['name']
        email = contact['email']
        new_company = contact['new_company']
        new_title = contact['new_title']

        print(f"  [{i}/{total}] {name} ({email})")

        # Step 1: Find contact in Apollo CRM
        apollo_contact = find_contact_by_email(email)
        time.sleep(RATE_LIMIT_DELAY)

        if not apollo_contact:
            # Not in CRM → create new contact with LinkedIn-detected data
            print(f"    -> not found in Apollo, creating...")
            success, status, contact_id = create_contact(
                name, email, new_company, new_title, list_id
            )
            time.sleep(RATE_LIMIT_DELAY)

            if not success:
                print(f"    -> create failed: {status}")
                results['create_failed'].append(contact)
                master_rows.append({
                    'email': email, 'name': name,
                    'old_company': contact['old_company'],
                    'new_company': new_company, 'new_title': new_title,
                    'contact_id': '', 'status': f'create_failed:{status}',
                    'date_processed': date.today().isoformat(),
                })
            else:
                print(f"    -> created + added to list: {new_company} / {new_title}")
                results['created'].append(contact)
                master_rows.append({
                    'email': email, 'name': name,
                    'old_company': contact['old_company'],
                    'new_company': new_company, 'new_title': new_title,
                    'contact_id': contact_id, 'status': 'created',
                    'date_processed': date.today().isoformat(),
                })
            continue

        contact_id = apollo_contact['id']
        apollo_company = apollo_contact['organization_name']
        apollo_title = apollo_contact['title']
        existing_label_ids = apollo_contact['label_ids']

        # Step 2+3: Update company/title + add to list in a single PUT
        success, status = update_and_add_to_list(
            contact_id, new_company, new_title, existing_label_ids, list_id
        )
        time.sleep(RATE_LIMIT_DELAY)

        if not success:
            print(f"    -> update failed: {status}")
            results['update_failed'].append(contact)
            master_rows.append({
                'email': email, 'name': name,
                'old_company': contact['old_company'],
                'new_company': new_company, 'new_title': new_title,
                'contact_id': contact_id, 'status': f'update_failed:{status}',
                'date_processed': date.today().isoformat(),
            })
            continue

        change_note = ''
        if apollo_company and apollo_company != new_company:
            change_note = f' (was: {apollo_company} / {apollo_title})'
        print(f"    -> updated + added to list: {new_company} / {new_title}{change_note}")
        results['updated'].append(contact)
        master_rows.append({
            'email': email, 'name': name,
            'old_company': contact['old_company'],
            'new_company': new_company, 'new_title': new_title,
            'contact_id': contact_id, 'status': 'pushed',
            'date_processed': date.today().isoformat(),
        })

    return results, master_rows


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Push job changers to Apollo: update company/title + add to enriched list'
    )
    parser.add_argument('csv_path', help='Path to job_changers.csv')
    parser.add_argument('--source', required=True, help='Source name for master file')
    parser.add_argument('--list-id', default=DEFAULT_LIST_ID,
                        help=f'Apollo list ID (default: {DEFAULT_LIST_ID})')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("CHURNED USER DETECTOR - PUSH TO APOLLO")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    # Load job changers
    contacts = load_job_changers(str(csv_path))
    if not contacts:
        print("No contacts found in CSV.")
        sys.exit(0)

    # Dedup against master
    existing_emails = load_master_emails(args.source)
    new_contacts = [c for c in contacts if c['email'] not in existing_emails]
    skipped = len(contacts) - len(new_contacts)

    print(f"\nSource: {args.source}")
    print(f"List ID: {args.list_id}")
    print(f"Contacts in CSV: {len(contacts)}")
    if skipped:
        print(f"Already pushed (in master): {skipped}")
    print(f"New contacts to push: {len(new_contacts)}")

    if not new_contacts:
        print("\nAll contacts already pushed. Exiting.")
        sys.exit(0)

    # Preview
    print(f"\nPreview:")
    for c in new_contacts[:10]:
        print(f"  - {c['name']}: {c['old_company']} → {c['new_company']} ({c['new_title']})")
    if len(new_contacts) > 10:
        print(f"  ... and {len(new_contacts) - 10} more")

    print(f"\nFor each contact:")
    print(f"  1. Find in Apollo by email")
    print(f"  2. Update organization + title with LinkedIn data")
    print(f"  3. Add to enriched list")

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Push
    results, master_rows = push_contacts(new_contacts, args.list_id)

    # Update master
    master_path = update_master(args.source, master_rows)

    # Summary
    print(f"\n{'=' * 70}")
    print("PUSH COMPLETE")
    print(f"{'=' * 70}")
    print(f"Updated (existing):      {len(results['updated'])}")
    print(f"Created (new):           {len(results['created'])}")
    print(f"Update failed:           {len(results['update_failed'])}")
    print(f"Create failed:           {len(results['create_failed'])}")
    print(f"Master updated: {master_path}")


if __name__ == '__main__':
    main()
