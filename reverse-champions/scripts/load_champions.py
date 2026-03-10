#!/usr/bin/env python3
"""
Load Champions - Parse input CSV of closed-won contacts.

Auto-detects common column names for name, email, company, and LinkedIn URL.
Supports custom column mapping via --col-* flags.
Deduplicates against master file to avoid reprocessing.

Input: CSV file (Salesforce export, product data, or manual)
Output: champions_to_scrape.json

Usage:
    python load_champions.py <csv_path> --source NAME [--col-name COL] [--col-email COL] [--col-company COL] [--col-linkedin COL] [--yes]
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

# Auto-detection patterns (lowercase matching)
COLUMN_PATTERNS = {
    'name': [
        'contact_name', 'name', 'full_name', 'fullname', 'contact name',
        'nom', 'nom_complet', 'nom complet',
    ],
    'email': [
        'email', 'contact_email', 'email_address', 'work_email',
        'contact email', 'email address', 'work email',
    ],
    'company': [
        'company', 'company_name', 'account_name', 'account', 'organization',
        'companyname', 'company name', 'account name',
    ],
    'linkedin': [
        'linkedin_url', 'linkedin', 'linkedin url', 'linkedin_profile',
        'linkedin profile', 'profile_url', 'profile url',
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


def auto_detect_columns(headers):
    """Auto-detect column mapping from CSV headers"""
    mapping = {}
    headers_lower = {h: h.lower().strip() for h in headers}

    for field, patterns in COLUMN_PATTERNS.items():
        for header, header_low in headers_lower.items():
            if header_low in patterns:
                mapping[field] = header
                break

    return mapping


def validate_mapping(mapping, required_fields=('name', 'email', 'company')):
    """Check that all required fields are mapped"""
    missing = [f for f in required_fields if f not in mapping]
    return missing


# =============================================================================
# CSV PARSING
# =============================================================================

def parse_csv(csv_path, col_overrides=None):
    """Parse CSV and return list of champion dicts"""
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        if not headers:
            print("Error: CSV has no headers")
            return None, None

        # Auto-detect + apply overrides
        mapping = auto_detect_columns(headers)

        if col_overrides:
            for field, col_name in col_overrides.items():
                if col_name:
                    if col_name in headers:
                        mapping[field] = col_name
                    else:
                        print(f"Warning: Column '{col_name}' not found in CSV. Available: {', '.join(headers)}")

        # Validate
        missing = validate_mapping(mapping)
        if missing:
            print(f"\nError: Could not detect columns for: {', '.join(missing)}")
            print(f"Available columns: {', '.join(headers)}")
            print(f"Detected mapping: {mapping}")
            print(f"\nUse --col-name, --col-email, --col-company to specify manually.")
            return None, None

        print(f"\nColumn mapping:")
        for field, col in mapping.items():
            print(f"  {field} -> '{col}'")

        # Parse rows
        f.seek(0)
        reader = csv.DictReader(f)
        champions = []
        seen_emails = set()

        for i, row in enumerate(reader, 1):
            name = (row.get(mapping['name']) or '').strip()
            email = (row.get(mapping['email']) or '').strip().lower()
            company = (row.get(mapping['company']) or '').strip()
            linkedin = (row.get(mapping.get('linkedin', ''), '') or '').strip() if 'linkedin' in mapping else ''

            if not email:
                continue

            if email in seen_emails:
                continue
            seen_emails.add(email)

            champions.append({
                'name': name,
                'email': email,
                'company': company,
                'linkedin_url': linkedin or None,
            })

        return champions, mapping


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Parse input CSV of closed-won contacts'
    )
    parser.add_argument('csv_path', help='Path to input CSV')
    parser.add_argument('--source', required=True, help='Source name for master tracking')
    parser.add_argument('--col-name', default=None, help='Column name for contact name')
    parser.add_argument('--col-email', default=None, help='Column name for email')
    parser.add_argument('--col-company', default=None, help='Column name for company')
    parser.add_argument('--col-linkedin', default=None, help='Column name for LinkedIn URL')
    parser.add_argument('--output-dir', default=None, help='Output directory (default: same as CSV)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 1: LOAD CHAMPIONS")
    print("=" * 70)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    # Parse CSV
    col_overrides = {
        'name': args.col_name,
        'email': args.col_email,
        'company': args.col_company,
        'linkedin': args.col_linkedin,
    }
    col_overrides = {k: v for k, v in col_overrides.items() if v}

    champions, mapping = parse_csv(str(csv_path), col_overrides)

    if champions is None:
        sys.exit(1)

    # Dedup vs master
    existing_emails = load_master_emails(args.source)
    new_champions = [c for c in champions if c['email'] not in existing_emails]
    skipped = len(champions) - len(new_champions)

    # Stats
    with_linkedin = sum(1 for c in new_champions if c.get('linkedin_url'))
    without_linkedin = len(new_champions) - with_linkedin

    print(f"\nParsed from CSV: {len(champions)} champions")
    if skipped:
        print(f"Already in master: {skipped} (skipped)")
    print(f"New champions: {len(new_champions)}")
    print(f"  With LinkedIn URL: {with_linkedin}")
    print(f"  Without LinkedIn URL: {without_linkedin} (will need enrichment)")

    if not new_champions:
        print("\nNo new champions to process. Exiting.")
        sys.exit(0)

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
    output_dir = Path(args.output_dir) if args.output_dir else Path(args.csv_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'champions_to_scrape.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_champions, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print("LOAD COMPLETE")
    print(f"{'=' * 70}")
    print(f"Champions to process: {len(new_champions)}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
