#!/usr/bin/env python3
"""
Push Output - Export CSV and optionally patch Apollo contacts with personalized hooks.

Two output modes:
1. CSV export: first_name, last_name, email, company, linkedin_url, hook, confidence
2. Apollo PATCH: update contacts with hook in a custom field

Input: hooks_generated.json
Output: personalized_hooks.csv + master file update

Usage:
    python push_output.py <hooks_json> --source NAME [--apollo-field-id ID] [--sequence-id ID] [--yes]
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


def normalize_linkedin_url(url):
    if not url:
        return ''
    url = url.strip().rstrip('/')
    if '?' in url:
        url = url.split('?')[0]
    return url.lower()


# =============================================================================
# MASTER FILE
# =============================================================================

def get_master_path(source_name):
    normalized = normalize_source_name(source_name)
    return MASTER_DIR / f'{normalized}_profiles_master.csv'


def update_master(source_name, processed_contacts):
    """Append processed LinkedIn URLs to master file"""
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    master_path = get_master_path(source_name)

    fieldnames = [
        'linkedin_url', 'first_name', 'last_name', 'email', 'company',
        'confidence', 'hook_generated', 'apollo_updated', 'date_processed',
    ]

    existing_rows = []
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    new_urls = {r['linkedin_url'] for r in processed_contacts}
    filtered_existing = [r for r in existing_rows if r.get('linkedin_url') not in new_urls]
    all_rows = filtered_existing + processed_contacts

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    return master_path


# =============================================================================
# APOLLO
# =============================================================================

def apollo_patch_contact(contact_id, field_id, hook_text):
    """Patch a contact's custom field with the hook text"""
    if not APOLLO_API_KEY:
        return False, 'no_api_key'

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': APOLLO_API_KEY,
    }

    try:
        response = requests.patch(
            f'{APOLLO_API_BASE}/contacts/{contact_id}',
            headers=headers,
            json={'typed_custom_fields': {field_id: hook_text}},
            timeout=30,
        )
        response.raise_for_status()
        return True, 'success'
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 429:
            print("  Rate limited. Waiting 60s...")
            time.sleep(60)
            return apollo_patch_contact(contact_id, field_id, hook_text)
        return False, f'http_{status}: {e.response.text[:200]}'
    except Exception as e:
        return False, f'error: {str(e)}'


def add_to_sequence(contact_ids, sequence_id):
    """Add contacts to an Apollo sequence"""
    if not APOLLO_API_KEY or not contact_ids or not sequence_id:
        return 0

    try:
        response = requests.post(
            f'{APOLLO_API_BASE}/emailer_campaigns/add_contact_ids',
            json={
                'api_key': APOLLO_API_KEY,
                'contact_ids': contact_ids,
                'emailer_campaign_id': sequence_id,
            },
            timeout=30,
        )
        response.raise_for_status()
        return len(response.json().get('contacts', []))
    except Exception as e:
        print(f"  Sequence add error: {e}")
        return 0


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Export CSV and optionally push hooks to Apollo'
    )
    parser.add_argument('hooks_json', help='Path to hooks_generated.json')
    parser.add_argument('--source', required=True, help='Source name for master tracking')
    parser.add_argument('--apollo-field-id', default=None,
                        help='Apollo custom field ID to write the hook to')
    parser.add_argument('--sequence-id', default=None,
                        help='Apollo sequence ID to enroll contacts into')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("LINKEDIN PROFILE PERSONALIZER - STEP 5: PUSH OUTPUT")
    print("=" * 70)

    input_path = Path(args.hooks_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        contacts = json.load(f)

    with_hook = [c for c in contacts if c.get('hook')]
    without_hook = [c for c in contacts if not c.get('hook')]

    print(f"\nSource: {args.source}")
    print(f"Total contacts: {len(contacts)}")
    print(f"  With hook: {len(with_hook)}")
    print(f"  Without hook (skipped/failed): {len(without_hook)}")

    if args.apollo_field_id:
        print(f"Apollo field ID: {args.apollo_field_id}")
        contacts_with_apollo_id = [c for c in with_hook if c.get('apollo_id')]
        print(f"  Contacts with Apollo ID (will patch): {len(contacts_with_apollo_id)}")
        contacts_without_apollo_id = len(with_hook) - len(contacts_with_apollo_id)
        if contacts_without_apollo_id:
            print(f"  Contacts without Apollo ID (CSV only): {contacts_without_apollo_id}")
    else:
        print("Apollo push: disabled (no --apollo-field-id)")

    if args.sequence_id:
        print(f"Sequence ID: {args.sequence_id}")

    if not args.yes:
        print()
        response = input("Proceed with output push? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    output_dir = input_path.parent

    # --- CSV Export (always) ---
    csv_path = output_dir / 'personalized_hooks.csv'
    csv_rows = []
    for c in contacts:
        intel = c.get('intel') or {}
        csv_rows.append({
            'first_name': c.get('first_name', ''),
            'last_name': c.get('last_name', ''),
            'email': c.get('email', ''),
            'company': c.get('company', ''),
            'linkedin_url': c.get('linkedin_url', ''),
            'hook': c.get('hook', ''),
            'confidence': intel.get('confidence', ''),
            'pain_signal': intel.get('pain_signal', ''),
            'hook_warnings': '; '.join(c.get('hook_warnings', [])),
            'hook_error': c.get('hook_error', ''),
        })

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['first_name', 'last_name', 'email', 'company', 'linkedin_url',
                      'hook', 'confidence', 'pain_signal', 'hook_warnings', 'hook_error']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\nCSV exported: {csv_path}")

    # --- Apollo PATCH (optional) ---
    apollo_updated = 0
    sequence_added = 0
    sequence_contact_ids = []

    if args.apollo_field_id:
        contacts_to_patch = [c for c in with_hook if c.get('apollo_id')]
        print(f"\nPatching {len(contacts_to_patch)} Apollo contacts...")

        for i, c in enumerate(contacts_to_patch, 1):
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            contact_id = c['apollo_id']

            success, status = apollo_patch_contact(contact_id, args.apollo_field_id, c['hook'])
            if success:
                apollo_updated += 1
                sequence_contact_ids.append(contact_id)
                print(f"  [{i}/{len(contacts_to_patch)}] {name}: updated")
            else:
                print(f"  [{i}/{len(contacts_to_patch)}] {name}: failed ({status})")

            time.sleep(RATE_LIMIT_DELAY)

        if args.sequence_id and sequence_contact_ids:
            print(f"\nAdding {len(sequence_contact_ids)} contacts to sequence {args.sequence_id}...")
            sequence_added = add_to_sequence(sequence_contact_ids, args.sequence_id)
            print(f"  -> {sequence_added} added")

    # --- Master File Update ---
    master_rows = []
    for c in contacts:
        intel = c.get('intel') or {}
        master_rows.append({
            'linkedin_url': normalize_linkedin_url(c.get('linkedin_url', '')),
            'first_name': c.get('first_name', ''),
            'last_name': c.get('last_name', ''),
            'email': c.get('email', ''),
            'company': c.get('company', ''),
            'confidence': intel.get('confidence', ''),
            'hook_generated': '1' if c.get('hook') else '0',
            'apollo_updated': '1' if (c.get('apollo_id') and apollo_updated > 0 and args.apollo_field_id) else '0',
            'date_processed': date.today().isoformat(),
        })

    master_path = update_master(args.source, master_rows)

    print(f"\n{'=' * 70}")
    print("OUTPUT COMPLETE")
    print(f"{'=' * 70}")
    print(f"CSV: {csv_path} ({len(csv_rows)} rows)")
    if args.apollo_field_id:
        print(f"Apollo updated: {apollo_updated}")
    if args.sequence_id:
        print(f"Sequence enrolled: {sequence_added}")
    print(f"Master updated: {master_path}")


if __name__ == '__main__':
    main()
