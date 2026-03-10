#!/usr/bin/env python3
"""
Load Contacts - Parse input CSV of LinkedIn profile URLs.

Auto-detects common column names for linkedin_url, first_name, last_name,
email, company, and apollo_id. Supports custom column mapping via --col-* flags.
Deduplicates against master file to avoid reprocessing.

Input: CSV file (Apollo export, manual list, etc.)
Output: contacts_to_process.json

Usage:
    python load_contacts.py <csv_path> --source NAME [--col-linkedin COL] [--col-name COL] ...
"""

import csv
import json
import sys
import os
import re
import argparse
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
MASTER_DIR = SKILL_DIR / 'master'

COLUMN_PATTERNS = {
    'linkedin_url': [
        'linkedin_url', 'linkedin', 'linkedin url', 'linkedin_profile',
        'linkedin profile', 'profile_url', 'profile url', 'li_url',
    ],
    'first_name': [
        'first_name', 'firstname', 'first name', 'given_name', 'prenom',
    ],
    'last_name': [
        'last_name', 'lastname', 'last name', 'family_name', 'nom',
    ],
    'email': [
        'email', 'email_address', 'work_email', 'contact_email',
        'email address', 'work email',
    ],
    'company': [
        'company', 'company_name', 'account_name', 'account', 'organization',
        'companyname', 'company name', 'account name', 'current_company',
    ],
    'apollo_id': [
        'apollo_id', 'contact_id', 'id', 'apollo id', 'contact id',
    ],
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


def normalize_linkedin_url(url):
    if not url:
        return ''
    url = url.strip().rstrip('/')
    if '?' in url:
        url = url.split('?')[0]
    return url.lower()


def load_master_urls(source_name):
    """Load already-processed LinkedIn URLs from master file"""
    normalized = normalize_source_name(source_name)
    master_path = MASTER_DIR / f'{normalized}_profiles_master.csv'
    urls = set()
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = normalize_linkedin_url(row.get('linkedin_url', ''))
                if url:
                    urls.add(url)
    return urls


def auto_detect_columns(headers):
    mapping = {}
    headers_lower = {h: h.lower().strip() for h in headers}
    for field, patterns in COLUMN_PATTERNS.items():
        for header, header_low in headers_lower.items():
            if header_low in patterns:
                mapping[field] = header
                break
    return mapping


# =============================================================================
# CSV PARSING
# =============================================================================

def parse_csv(csv_path, col_overrides=None):
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        if not headers:
            print("Error: CSV has no headers")
            return None, None

        mapping = auto_detect_columns(headers)

        if col_overrides:
            for field, col_name in col_overrides.items():
                if col_name:
                    if col_name in headers:
                        mapping[field] = col_name
                    else:
                        print(f"Warning: Column '{col_name}' not found. Available: {', '.join(headers)}")

        if 'linkedin_url' not in mapping:
            print(f"\nError: Could not detect LinkedIn URL column.")
            print(f"Available columns: {', '.join(headers)}")
            print(f"Use --col-linkedin to specify manually.")
            return None, None

        print(f"\nColumn mapping:")
        for field, col in mapping.items():
            print(f"  {field} -> '{col}'")

        f.seek(0)
        reader = csv.DictReader(f)
        contacts = []
        seen_urls = set()

        for row in reader:
            linkedin_url = normalize_linkedin_url(row.get(mapping['linkedin_url'], '') or '')
            if not linkedin_url:
                continue

            if linkedin_url in seen_urls:
                continue
            seen_urls.add(linkedin_url)

            first_name = (row.get(mapping.get('first_name', ''), '') or '').strip()
            last_name = (row.get(mapping.get('last_name', ''), '') or '').strip()
            email = (row.get(mapping.get('email', ''), '') or '').strip().lower()
            company = (row.get(mapping.get('company', ''), '') or '').strip()
            apollo_id = (row.get(mapping.get('apollo_id', ''), '') or '').strip()

            contacts.append({
                'linkedin_url': linkedin_url,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'company': company,
                'apollo_id': apollo_id or None,
            })

        return contacts, mapping


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Parse input CSV of LinkedIn profile URLs'
    )
    parser.add_argument('csv_path', help='Path to input CSV')
    parser.add_argument('--source', required=True, help='Source name for master tracking')
    parser.add_argument('--col-linkedin', default=None, help='Column name for LinkedIn URL')
    parser.add_argument('--col-first-name', default=None, help='Column name for first name')
    parser.add_argument('--col-last-name', default=None, help='Column name for last name')
    parser.add_argument('--col-email', default=None, help='Column name for email')
    parser.add_argument('--col-company', default=None, help='Column name for company')
    parser.add_argument('--col-apollo-id', default=None, help='Column name for Apollo contact ID')
    parser.add_argument('--output-dir', default=None, help='Output directory')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("LINKEDIN PROFILE PERSONALIZER - STEP 1: LOAD CONTACTS")
    print("=" * 70)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    col_overrides = {
        'linkedin_url': args.col_linkedin,
        'first_name': args.col_first_name,
        'last_name': args.col_last_name,
        'email': args.col_email,
        'company': args.col_company,
        'apollo_id': args.col_apollo_id,
    }
    col_overrides = {k: v for k, v in col_overrides.items() if v}

    contacts, mapping = parse_csv(str(csv_path), col_overrides)

    if contacts is None:
        sys.exit(1)

    # Dedup vs master
    existing_urls = load_master_urls(args.source)
    new_contacts = [c for c in contacts if c['linkedin_url'] not in existing_urls]
    skipped = len(contacts) - len(new_contacts)

    with_email = sum(1 for c in new_contacts if c.get('email'))
    with_apollo_id = sum(1 for c in new_contacts if c.get('apollo_id'))

    print(f"\nParsed from CSV: {len(contacts)} contacts")
    if skipped:
        print(f"Already in master: {skipped} (skipped)")
    print(f"New contacts: {len(new_contacts)}")
    print(f"  With email: {with_email}")
    print(f"  With Apollo ID: {with_apollo_id}")

    if not new_contacts:
        print("\nNo new contacts to process. Exiting.")
        sys.exit(0)

    print(f"\nPreview (first 5):")
    for c in new_contacts[:5]:
        name = f"{c['first_name']} {c['last_name']}".strip() or "(no name)"
        co = c['company'] or "(no company)"
        print(f"  - {name} @ {co} — {c['linkedin_url']}")
    if len(new_contacts) > 5:
        print(f"  ... and {len(new_contacts) - 5} more")

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    output_dir = Path(args.output_dir) if args.output_dir else csv_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'contacts_to_process.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_contacts, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print("LOAD COMPLETE")
    print(f"{'=' * 70}")
    print(f"Contacts to process: {len(new_contacts)}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
