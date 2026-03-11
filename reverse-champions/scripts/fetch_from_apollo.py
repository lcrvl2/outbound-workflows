#!/usr/bin/env python3
"""
Fetch from Apollo - Pull new closed-won contacts directly from Apollo.

Queries contacts where [Org] Became Paid Date is within the last N days
(default 7). Replaces the CSV load step for the weekly production run.

Deduplicates against the master file so already-processed champions are skipped.

Output: champions_to_scrape.json (same format as load_champions.py)

Usage:
    python fetch_from_apollo.py --source NAME [--days 7] [--output-dir DIR] [--yes]
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
from datetime import date, timedelta

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
MAX_PER_PAGE = 25  # Apollo free/standard tier limit


# =============================================================================
# HELPERS
# =============================================================================

def normalize_source_name(source_name):
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def load_master_emails(source_name):
    """Load already-processed champion emails from master file"""
    normalized = normalize_source_name(source_name)
    master_path = MASTER_DIR / f'{normalized}_champions_master.csv'
    emails = set()
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get('champion_email', '').strip().lower()
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
# FETCH
# =============================================================================

def fetch_new_paid_contacts(days=7):
    """
    Fetch contacts from Apollo where [Org] Became Paid Date is within the last N days.

    Uses contacts/search with a custom field date filter.
    Paginates until all results are retrieved.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    print(f"\nFetching contacts with [Org] Became Paid Date >= {cutoff} (last {days} days)...")

    all_contacts = []
    page = 1

    while True:
        try:
            data = apollo_request('POST', 'contacts/search', {
                'page': page,
                'per_page': MAX_PER_PAGE,
                'include_total_results': True,
                'custom_fields': [
                    {
                        'field_name': '[Org] Became Paid Date',
                        'value': cutoff,
                        'operator': 'gte',
                    }
                ],
            })
        except Exception as e:
            print(f"  Error fetching page {page}: {e}")
            break

        contacts = data.get('contacts', [])
        total = data.get('metadata', {}).get('total_results', len(contacts))

        if not contacts:
            break

        all_contacts.extend(contacts)
        print(f"  Page {page}: {len(contacts)} contacts (total: {total})")

        if len(all_contacts) >= total:
            break

        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_contacts


def normalize_contact(contact):
    """Convert Apollo contact dict to the champion format used by the pipeline"""
    first = contact.get('first_name', '') or ''
    last = contact.get('last_name', '') or ''
    name = f"{first} {last}".strip()

    org = contact.get('organization', {}) or {}
    company = (
        contact.get('organization_name')
        or org.get('name')
        or ''
    ).strip()

    return {
        'name': name,
        'email': (contact.get('email') or '').strip().lower(),
        'company': company,
        'linkedin_url': contact.get('linkedin_url') or None,
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Fetch new closed-won contacts from Apollo by Became Paid Date'
    )
    parser.add_argument('--source', required=True,
                        help='Source name for master file tracking (e.g., cw_weekly)')
    parser.add_argument('--days', type=int, default=7,
                        help='Number of days lookback for Became Paid Date (default: 7)')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: generated-outputs/{source}-{date}/)')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 1: FETCH FROM APOLLO")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    print(f"\nSource: {args.source}")
    print(f"Lookback: last {args.days} days")

    # Fetch from Apollo
    raw_contacts = fetch_new_paid_contacts(days=args.days)

    if not raw_contacts:
        print("\nNo contacts found. Exiting.")
        sys.exit(0)

    # Normalize to pipeline format
    champions = []
    seen_emails = set()
    for contact in raw_contacts:
        c = normalize_contact(contact)
        if not c['email'] or c['email'] in seen_emails:
            continue
        seen_emails.add(c['email'])
        champions.append(c)

    print(f"\nNormalized: {len(champions)} unique contacts")

    # Dedup against master
    existing_emails = load_master_emails(args.source)
    new_champions = [c for c in champions if c['email'] not in existing_emails]
    skipped = len(champions) - len(new_champions)

    if skipped:
        print(f"Already in master: {skipped} (skipped)")
    print(f"New champions to process: {len(new_champions)}")

    if not new_champions:
        print("\nNo new champions to process. Exiting.")
        sys.exit(0)

    with_linkedin = sum(1 for c in new_champions if c.get('linkedin_url'))
    without_linkedin = len(new_champions) - with_linkedin
    print(f"  With LinkedIn URL: {with_linkedin}")
    print(f"  Without LinkedIn URL: {without_linkedin} (will need enrichment)")

    # Preview
    print(f"\nPreview (first 5):")
    for c in new_champions[:5]:
        li = "has LinkedIn" if c.get('linkedin_url') else "no LinkedIn"
        print(f"  - {c['name']} ({c['company']}) [{li}]")
    if len(new_champions) > 5:
        print(f"  ... and {len(new_champions) - 5} more")

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Save output
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        source_slug = normalize_source_name(args.source)
        today = date.today().isoformat()
        output_dir = SKILL_DIR / 'generated-outputs' / f'{source_slug}-{today}'

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'champions_to_scrape.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_champions, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print("FETCH COMPLETE")
    print(f"{'=' * 70}")
    print(f"Champions to process: {len(new_champions)}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
