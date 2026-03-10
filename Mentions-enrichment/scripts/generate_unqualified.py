#!/usr/bin/env python3
"""
Generate Unqualified - Companies that had reach but didn't pass Apollo filters.

Compares master file (all enriched companies) against apollo-accounts file
(companies that passed filters) and generates an unqualified file containing
companies that were enriched but didn't meet criteria (e.g. <200 employees).
Useful for manual review or future re-qualification.

Formula: unqualified = master - apollo-accounts (by normalized name OR domain)

Usage:
    python generate_unqualified.py --source NAME --data-dir PATH [--yes]
"""

import csv
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent


# =============================================================================
# HELPERS
# =============================================================================

def normalize_name(name):
    """Normalize company name for matching: lowercase, no spaces"""
    if not name:
        return ''
    return re.sub(r'\s+', '', name.lower())


def normalize_domain(website):
    """Normalize website/domain for matching: lowercase, no www/protocol/trailing slash"""
    if not website:
        return ''
    d = website.lower().strip()
    d = re.sub(r'^https?://', '', d)
    d = d.removeprefix('www.')
    d = d.rstrip('/')
    return d


def normalize_source_name(source_name):
    """Normalize source name for filename: lowercase, underscores"""
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


# =============================================================================
# FILE LOADING
# =============================================================================

def load_master_file(data_dir, source_name):
    """Load master file (all enriched companies)"""
    normalized = normalize_source_name(source_name)
    master_path = data_dir / 'master' / f'{normalized}_master.csv'

    if not master_path.exists():
        print(f"Error: Master file not found: {master_path}")
        return None, None

    companies = []
    with open(master_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append(row)

    return companies, master_path


def load_apollo_file(data_dir, source_name):
    """Load apollo-accounts file (companies that passed filters). Returns (names set, domains set, path)."""
    normalized = normalize_source_name(source_name)
    apollo_path = data_dir / 'apollo-accounts' / f'{normalized}_apollo.csv'

    if not apollo_path.exists():
        print(f"Warning: Apollo file not found: {apollo_path}")
        print(f"  Assuming no companies have passed filters yet.")
        return set(), set(), apollo_path

    # Build sets of normalized company names AND domains
    apollo_names = set()
    apollo_domains = set()
    with open(apollo_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Company Name', '') or row.get('company_name', '')
            norm = normalize_name(name)
            if norm:
                apollo_names.add(norm)

            website = row.get('Website', '') or row.get('website', '')
            domain = normalize_domain(website)
            if domain:
                apollo_domains.add(domain)

    return apollo_names, apollo_domains, apollo_path


# =============================================================================
# FILTER LOGIC
# =============================================================================

def generate_unqualified(master_companies, apollo_names, apollo_domains):
    """
    Generate unqualified list: companies in master but NOT in apollo-accounts.
    Matches by normalized name OR normalized domain.
    Only includes successfully enriched companies (status=success, has website).
    """
    unqualified = []
    skipped_no_website = 0
    skipped_status = 0
    matched_by_name = 0
    matched_by_domain = 0

    for row in master_companies:
        # Skip if no website or enrichment failed
        website = row.get('Website', '').strip()
        status = row.get('Status', '').strip().lower()

        if not website:
            skipped_no_website += 1
            continue

        if status != 'success':
            skipped_status += 1
            continue

        # Check if already qualified (in apollo-accounts) — by name OR domain
        name = row.get('Company Name', '')
        norm = normalize_name(name)
        domain = normalize_domain(website)

        if norm in apollo_names:
            matched_by_name += 1
            continue

        if domain in apollo_domains:
            matched_by_domain += 1
            continue

        # Didn't pass Apollo filters
        unqualified.append(row)

    qualified = matched_by_name + matched_by_domain
    print(f"\n  Skipped (no website): {skipped_no_website}")
    print(f"  Skipped (enrichment failed): {skipped_status}")
    print(f"  Qualified (in apollo-accounts): {qualified} ({matched_by_name} by name, {matched_by_domain} by domain)")

    return unqualified


# =============================================================================
# OUTPUT
# =============================================================================

def save_unqualified_file(unqualified, data_dir, source_name):
    """Save unqualified file to unqualified/[source]_unqualified_[date].csv"""
    today = date.today().isoformat()
    normalized = normalize_source_name(source_name)

    unqualified_dir = data_dir / 'unqualified'
    unqualified_dir.mkdir(parents=True, exist_ok=True)

    unqualified_path = unqualified_dir / f'{normalized}_unqualified_{today}.csv'

    fieldnames = ['Company Name', 'Website', 'Country', 'Cumulative Reach']

    with open(unqualified_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(unqualified)

    return unqualified_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Generate unqualified companies file (had reach, didn\'t pass Apollo filters)')
    parser.add_argument('--source', required=True, help='Source name (e.g., hootsuite)')
    parser.add_argument('--data-dir', required=True, help='Data directory for this competitor (e.g., data/hootsuite/)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    print("=" * 70)
    print("Generate Unqualified Companies File")
    print("=" * 70)

    # Load master file
    print(f"\nLoading master file for {args.source}...")
    master_companies, master_path = load_master_file(data_dir, args.source)

    if master_companies is None:
        sys.exit(1)

    print(f"  Loaded {len(master_companies)} companies from master")

    # Load apollo-accounts file
    print(f"\nLoading Apollo accounts file (qualified companies)...")
    apollo_names, apollo_domains, apollo_path = load_apollo_file(data_dir, args.source)
    print(f"  Found {len(apollo_names)} qualified companies ({len(apollo_domains)} unique domains)")

    # Generate unqualified list
    print(f"\nGenerating unqualified list...")
    unqualified = generate_unqualified(master_companies, apollo_names, apollo_domains)

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Master file: {len(master_companies)} companies")
    print(f"Qualified (apollo-accounts): {len(apollo_names)} companies")
    print(f"Unqualified: {len(unqualified)}")

    if not unqualified:
        print("\nAll enriched companies passed Apollo filters.")
        sys.exit(0)

    # Preview
    if not args.yes:
        print(f"\nPreview (first 10):")
        for i, company in enumerate(unqualified[:10]):
            print(f"  {i+1}. {company.get('Company Name')} - {company.get('Website')}")
        if len(unqualified) > 10:
            print(f"  ... and {len(unqualified) - 10} more")

        print()
        response = input("Save unqualified file? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Save file
    print(f"\nSaving unqualified file...")
    unqualified_path = save_unqualified_file(unqualified, data_dir, args.source)

    print(f"\n{'=' * 70}")
    print("UNQUALIFIED FILE CREATED")
    print(f"{'=' * 70}")
    print(f"Unqualified companies: {len(unqualified)}")
    print(f"Output: {unqualified_path}")
    print(f"{'=' * 70}")

    return str(unqualified_path)


if __name__ == '__main__':
    main()
