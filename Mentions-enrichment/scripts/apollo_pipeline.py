#!/usr/bin/env python3
"""
Apollo Pipeline - Import enriched companies, filter by employee count, exclude current clients.

Replaces the manual Apollo import/filter/export cycle:
1. Bulk create accounts in Apollo
2. Search with employee filter (>200) and exclude "Current Client" stage
3. Save filtered results to apollo-accounts/

Usage:
    python apollo_pipeline.py <enriched_csv> --source NAME [--min-employees 200] [--yes]
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
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
# APOLLO_ACCOUNTS_DIR is now set per-competitor via --data-dir parameter

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

# Bulk create limit per request
BULK_CREATE_LIMIT = 100

# Employee count ranges for >200 employees
EMPLOYEE_RANGES_200_PLUS = [
    '201-500', '501-1000', '1001-2000',
    '2001-5000', '5001-10000', '10001+',
]

# Rate limiting
RATE_LIMIT_DELAY = 1.0  # seconds between API calls


# =============================================================================
# HELPERS
# =============================================================================

def normalize_name(name):
    """Normalize company name for matching: lowercase, no spaces"""
    if not name:
        return ''
    return re.sub(r'\s+', '', name.lower())


def normalize_source_name(source_name):
    """Normalize source name for filename: lowercase, underscores"""
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_apollo_accounts_path(source_name, data_dir):
    """Get path to Apollo accounts file for a source"""
    normalized = normalize_source_name(source_name)
    apollo_accounts_dir = data_dir / 'apollo-accounts'
    return apollo_accounts_dir / f'{normalized}_apollo.csv'


def load_existing_apollo_accounts(apollo_path):
    """Load existing Apollo accounts for dedup"""
    accounts = {}
    if apollo_path.exists():
        with open(apollo_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Company Name', '') or row.get('company_name', '')
                domain = row.get('Website', '') or row.get('website_url', '') or row.get('Domain', '')
                norm = normalize_name(name)
                if norm:
                    accounts[norm] = row
                if domain:
                    accounts[domain.lower()] = row
    return accounts


# =============================================================================
# APOLLO API FUNCTIONS
# =============================================================================

def apollo_headers():
    """Headers for Apollo API"""
    return {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
    }


def apollo_request(method, endpoint, json_data=None, params=None):
    """Make an Apollo API request with API key"""
    url = f'{APOLLO_API_BASE}/{endpoint}'

    # Add API key to request body or params
    if json_data is not None:
        json_data['api_key'] = APOLLO_API_KEY
    if params is not None:
        params['api_key'] = APOLLO_API_KEY

    try:
        if method == 'GET':
            response = requests.get(url, headers=apollo_headers(), params=params or {'api_key': APOLLO_API_KEY}, timeout=30)
        else:
            response = requests.post(url, headers=apollo_headers(), json=json_data, timeout=60)

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
# ACCOUNT STAGES
# =============================================================================

def get_account_stages():
    """Fetch all account stages from Apollo"""
    print("\nFetching account stages...")
    data = apollo_request('GET', 'account_stages')

    stages = data.get('account_stages', [])
    print(f"  Found {len(stages)} stages:")
    for stage in stages:
        print(f"    - {stage.get('name')} (id: {stage.get('id')})")

    return stages


def get_non_client_stage_ids(stages):
    """Get all stage IDs except 'Current Client' (case-insensitive)"""
    client_keywords = ['current client', 'current_client', 'client']
    non_client = []
    excluded = []

    for stage in stages:
        name = stage.get('name', '').lower().strip()
        if any(kw in name for kw in client_keywords):
            excluded.append(stage.get('name'))
        else:
            non_client.append(stage.get('id'))

    if excluded:
        print(f"\n  Excluding stages: {', '.join(excluded)}")
    else:
        print("\n  Warning: No 'Current Client' stage found. All stages will be included.")

    return non_client


# =============================================================================
# BULK CREATE
# =============================================================================

def bulk_create_accounts(companies):
    """
    Create accounts in Apollo via bulk_create endpoint.
    companies: list of dicts with 'Company Name' and 'Website' keys.
    Returns: list of created account records.
    """
    total = len(companies)
    num_batches = (total + BULK_CREATE_LIMIT - 1) // BULK_CREATE_LIMIT
    created = []
    errors = 0

    print(f"\nCreating {total} accounts in Apollo ({num_batches} batches)...")

    for batch_num in range(num_batches):
        start = batch_num * BULK_CREATE_LIMIT
        end = min(start + BULK_CREATE_LIMIT, total)
        batch = companies[start:end]

        accounts_data = []
        for company in batch:
            account = {
                'name': company.get('Company Name', ''),
                'domain': company.get('Website', ''),
            }
            accounts_data.append(account)

        try:
            data = apollo_request('POST', 'accounts/bulk_create', {
                'accounts': accounts_data,
            })

            batch_created = data.get('created_accounts', []) or data.get('accounts', [])
            created.extend(batch_created)
            print(f"  Batch {batch_num + 1}/{num_batches}: Created {len(batch_created)} accounts")

        except Exception as e:
            errors += 1
            print(f"  Batch {batch_num + 1}/{num_batches}: Error - {e}")

        if batch_num < num_batches - 1:
            time.sleep(RATE_LIMIT_DELAY)

    print(f"\nBulk create complete: {len(created)} created, {errors} batch errors")
    return created


# =============================================================================
# SEARCH & FILTER
# =============================================================================

def search_accounts_filtered(stage_ids, employee_ranges, domain_list=None):
    """
    Search Apollo accounts with employee and stage filters.
    Paginates through all results.
    Returns list of matching account records.
    """
    all_accounts = []
    page = 1
    per_page = 100

    print(f"\nSearching accounts (>200 employees, excluding current clients)...")

    while True:
        search_params = {
            'page': page,
            'per_page': per_page,
            'organization_num_employees_ranges': employee_ranges,
        }

        # Add stage filter if we have stage IDs
        if stage_ids:
            search_params['account_stage_ids'] = stage_ids

        # Optionally filter by specific domains
        if domain_list:
            search_params['q_organization_domains'] = '\n'.join(domain_list)

        try:
            data = apollo_request('POST', 'accounts/search', search_params)

            accounts = data.get('accounts', [])
            pagination = data.get('pagination', {})
            total_entries = pagination.get('total_entries', 0)

            all_accounts.extend(accounts)
            print(f"  Page {page}: {len(accounts)} accounts (total found: {total_entries})")

            if not accounts or len(all_accounts) >= total_entries:
                break

            page += 1
            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            print(f"  Search error on page {page}: {e}")
            break

    print(f"\nSearch complete: {len(all_accounts)} accounts match filters")
    return all_accounts


# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_apollo_accounts(accounts, source_name, existing_accounts, data_dir):
    """
    Save filtered accounts to apollo-accounts/[source]_apollo.csv.
    Deduplicates against existing file.
    """
    apollo_path = get_apollo_accounts_path(source_name, data_dir)
    apollo_path.parent.mkdir(parents=True, exist_ok=True)

    # Standardize field extraction from Apollo API response
    new_rows = []
    dupes = 0

    for account in accounts:
        name = account.get('name', '')
        domain = account.get('domain', '')
        norm = normalize_name(name)

        # Skip if already in existing file
        if norm in existing_accounts or (domain and domain.lower() in existing_accounts):
            dupes += 1
            continue

        new_rows.append({
            'Company Name': name,
            'Website': domain,
            'Industry': account.get('industry', ''),
            'Employee Count': account.get('organization_raw_address', {}).get('estimated_num_employees', '')
                if isinstance(account.get('organization_raw_address'), dict) else '',
            'Apollo ID': account.get('id', ''),
            'Added Date': date.today().isoformat(),
        })

    print(f"\n  New accounts to add: {len(new_rows)}")
    print(f"  Duplicates skipped: {dupes}")

    if not new_rows:
        print("  No new accounts to save.")
        return apollo_path, 0

    # Load existing rows and append
    existing_rows = []
    if apollo_path.exists():
        with open(apollo_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    all_rows = existing_rows + new_rows

    fieldnames = ['Company Name', 'Website', 'Industry', 'Employee Count', 'Apollo ID', 'Added Date']
    with open(apollo_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    return apollo_path, len(new_rows)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Apollo pipeline: import, filter, save')
    parser.add_argument('enriched_csv', help='Path to enriched CSV from enrich_mentions.py')
    parser.add_argument('--source', required=True, help='Source name (must match enrichment source)')
    parser.add_argument('--data-dir', help='Data directory for this competitor (e.g., data/hootsuite/)')
    parser.add_argument('--min-employees', type=int, default=200,
                        help='Minimum employee count filter (default: 200)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    # Set data_dir: use provided value or fall back to old structure for backward compatibility
    if args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        # Backward compatibility: use old master/apollo-accounts structure
        data_dir = SKILL_DIR

    print("=" * 70)
    print("Apollo Pipeline - Import, Filter & Save")
    print("=" * 70)

    # Check credentials
    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in environment.")
        sys.exit(1)

    # Read enriched CSV
    input_path = Path(args.enriched_csv)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    companies = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Company Name', '').strip()
            website = row.get('Website', '').strip()
            if name and website:
                companies.append(row)

    print(f"\nLoaded {len(companies)} companies from {input_path.name}")

    if not companies:
        print("No companies with both name and website. Exiting.")
        sys.exit(0)

    # Load existing Apollo accounts for dedup
    apollo_path = get_apollo_accounts_path(args.source, data_dir)
    existing_accounts = load_existing_apollo_accounts(apollo_path)
    print(f"Existing Apollo accounts: {len(existing_accounts) // 2}")  # Divide by 2 since we store name + domain keys

    # Build employee ranges based on min-employees
    if args.min_employees <= 200:
        employee_ranges = EMPLOYEE_RANGES_200_PLUS
    else:
        # Filter ranges to only include those above threshold
        employee_ranges = []
        range_mins = {'201-500': 201, '501-1000': 501, '1001-2000': 1001,
                      '2001-5000': 2001, '5001-10000': 5001, '10001+': 10001}
        for r, min_val in range_mins.items():
            if min_val >= args.min_employees or (min_val < args.min_employees and int(r.split('-')[0]) >= args.min_employees):
                employee_ranges.append(r)
        if not employee_ranges:
            employee_ranges = ['10001+']

    # Get account stages for filtering
    stages = get_account_stages()
    non_client_stage_ids = get_non_client_stage_ids(stages)

    # Preview
    print(f"\n{'=' * 70}")
    print("APOLLO PIPELINE PREVIEW")
    print(f"{'=' * 70}")
    print(f"Source: {args.source}")
    print(f"Companies to import: {len(companies)}")
    print(f"Employee filter: >{args.min_employees}")
    print(f"Employee ranges: {employee_ranges}")
    print(f"Stage filter: Excluding current clients ({len(stages) - len(non_client_stage_ids)} stages excluded)")
    print(f"Existing Apollo accounts: {len(existing_accounts) // 2}")

    if not args.yes:
        print()
        response = input("Proceed with Apollo import + filter? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Step 1: Bulk create accounts
    print(f"\n{'=' * 70}")
    print("STEP 1: BULK CREATE IN APOLLO")
    print(f"{'=' * 70}")

    created = bulk_create_accounts(companies)

    # Step 2: Search with filters
    print(f"\n{'=' * 70}")
    print("STEP 2: SEARCH WITH FILTERS")
    print(f"{'=' * 70}")

    # Extract domains from input for targeted search
    domains = [c.get('Website', '') for c in companies if c.get('Website')]

    filtered_accounts = search_accounts_filtered(
        non_client_stage_ids,
        employee_ranges,
        domain_list=domains,
    )

    # Step 3: Save results
    print(f"\n{'=' * 70}")
    print("STEP 3: SAVE FILTERED ACCOUNTS")
    print(f"{'=' * 70}")

    saved_path, new_count = save_apollo_accounts(
        filtered_accounts, args.source, existing_accounts, data_dir
    )

    # Summary
    print(f"\n{'=' * 70}")
    print("APOLLO PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Accounts imported: {len(created)}")
    print(f"Accounts matching filters: {len(filtered_accounts)}")
    print(f"New accounts saved: {new_count}")
    print(f"Output: {saved_path}")
    print(f"{'=' * 70}")

    return str(saved_path)


if __name__ == '__main__':
    main()
