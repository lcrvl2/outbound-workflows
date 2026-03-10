#!/usr/bin/env python3
"""
Mentions Enrichment - Company Domain Enrichment via DataForSEO

Transforms mention tracking CSV exports into Apollo.io-ready account lists.

Features:
- Per-source master files (prevents re-enriching same companies)
- Mandatory dry-run with user confirmation
- DataForSEO balance check before proceeding
- Normalized name matching (lowercase, no spaces)
- Domain filtering (social media, news, directories, etc.)

Usage:
    python enrich_mentions.py <input_csv> [--threshold N] [--source NAME]

Cost: ~$0.0006 per query = $0.60 per 1,000
"""

import csv
import time
import requests
import base64
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from datetime import date
from collections import defaultdict

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
# MASTER_DIR and OUTPUT_DIR are now set per-competitor via --data-dir parameter
FILTER_FILE = SKILL_DIR / 'references' / 'domain_filter_list.txt'

# DataForSEO API credentials
DFS_LOGIN = os.getenv('DATAFORSEO_USERNAME') or os.getenv('DATAFORSEO_LOGIN', '')
DFS_PASSWORD = os.getenv('DATAFORSEO_PASSWORD', '')

# DataForSEO API endpoints
DFS_BASE = 'https://api.dataforseo.com'
DFS_TASK_POST = f'{DFS_BASE}/v3/serp/google/organic/task_post'
DFS_TASKS_READY = f'{DFS_BASE}/v3/serp/google/organic/tasks_ready'
DFS_TASK_GET = f'{DFS_BASE}/v3/serp/google/organic/task_get/advanced'
DFS_BALANCE = f'{DFS_BASE}/v3/appendix/user_data'

# Batch settings
BATCH_SIZE = 100
POLL_INTERVAL = 5
MAX_WAIT_TIME = 600

# Default reach threshold
DEFAULT_THRESHOLD = 10000

# Cost per query
COST_PER_QUERY = 0.0006

# Country code to location mapping
COUNTRY_LOCATIONS = {
    'US': 'United States', 'GB': 'United Kingdom', 'CA': 'Canada',
    'AU': 'Australia', 'MX': 'Mexico', 'BR': 'Brazil', 'FR': 'France',
    'DE': 'Germany', 'IT': 'Italy', 'ES': 'Spain', 'IN': 'India',
    'JP': 'Japan', 'CN': 'China', 'AR': 'Argentina', 'PE': 'Peru',
    'NL': 'Netherlands', 'BE': 'Belgium', 'CH': 'Switzerland',
    'AT': 'Austria', 'SE': 'Sweden', 'NO': 'Norway', 'DK': 'Denmark',
    'FI': 'Finland', 'PL': 'Poland', 'PT': 'Portugal', 'IE': 'Ireland',
    'NZ': 'New Zealand', 'SG': 'Singapore', 'HK': 'Hong Kong',
    'KR': 'South Korea', 'TW': 'Taiwan', 'TH': 'Thailand', 'MY': 'Malaysia',
    'PH': 'Philippines', 'ID': 'Indonesia', 'VN': 'Vietnam',
    'ZA': 'South Africa', 'NG': 'Nigeria', 'EG': 'Egypt', 'KE': 'Kenya',
    'AE': 'United Arab Emirates', 'SA': 'Saudi Arabia', 'IL': 'Israel',
    'TR': 'Turkey', 'RU': 'Russia', 'UA': 'Ukraine', 'CZ': 'Czech Republic',
    'RO': 'Romania', 'HU': 'Hungary', 'GR': 'Greece', 'CL': 'Chile',
    'CO': 'Colombia', 'VE': 'Venezuela', 'EC': 'Ecuador',
}

# =============================================================================
# COLUMN DETECTION
# =============================================================================

COLUMN_ALIASES = {
    'company_name': ['source_name', 'company', 'name', 'Company Name', 'company_name'],
    'reach': ['cumulative_reach', 'reach', 'Cumulative Reach', 'cumulative reach'],
    'country': ['country', 'Country'],
    'alert_name': ['alert_name', 'alert', 'tracking_name', 'source', 'Alert Name'],
}


def detect_column(headers, field_type):
    """Detect which column matches the field type"""
    aliases = COLUMN_ALIASES.get(field_type, [])
    for alias in aliases:
        if alias in headers:
            return alias
        # Case-insensitive match
        for h in headers:
            if h.lower() == alias.lower():
                return h
    return None


# =============================================================================
# HELPER FUNCTIONS
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
    # Remove special chars, replace spaces with underscores
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_auth_header():
    """Create Basic Auth header for DataForSEO API"""
    credentials = f"{DFS_LOGIN}:{DFS_PASSWORD}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}


def load_filter_domains():
    """Load domain filter list from file"""
    domains = set()
    if FILTER_FILE.exists():
        with open(FILTER_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    domains.add(line.lower())
    return domains


def extract_domain(url):
    """Extract clean domain from URL"""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return None


def is_filtered_domain(domain, filter_domains):
    """Check if domain should be filtered out"""
    if not domain:
        return True
    domain_lower = domain.lower()
    return any(filtered in domain_lower for filtered in filter_domains)


def check_dfs_balance():
    """Check DataForSEO account balance"""
    try:
        response = requests.get(
            DFS_BALANCE,
            headers=get_auth_header(),
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get('status_code') == 20000:
            tasks = data.get('tasks', [])
            if tasks and tasks[0].get('result'):
                result = tasks[0]['result'][0]
                return result.get('money', {}).get('balance', 0)
        return None
    except Exception as e:
        print(f"  Warning: Could not check balance: {e}")
        return None


# =============================================================================
# MASTER FILE OPERATIONS
# =============================================================================

def get_master_path(source_name, data_dir):
    """Get path to master file for a source"""
    normalized = normalize_source_name(source_name)
    master_dir = data_dir / 'master'
    return master_dir / f'{normalized}_master.csv'


def load_master_file(master_path):
    """Load master file, return dict of normalized_name -> record"""
    master = {}
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                norm_name = row.get('Normalized Name', '')
                if norm_name:
                    master[norm_name] = row
    return master


def save_master_file(master_path, master_data):
    """Save master file"""
    if not master_data:
        return

    master_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ['Company Name', 'Website', 'Country', 'Cumulative Reach',
                  'Status', 'Enriched Date', 'Normalized Name']

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in master_data.values():
            writer.writerow(record)


# =============================================================================
# DATA PROCESSING
# =============================================================================

def read_and_deduplicate(input_csv, threshold):
    """
    Read CSV, deduplicate by normalized name, filter by reach threshold.
    Returns: (companies list, source_name, stats dict)
    """
    # First pass: detect columns and source
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        name_col = detect_column(headers, 'company_name')
        reach_col = detect_column(headers, 'reach')
        country_col = detect_column(headers, 'country')
        alert_col = detect_column(headers, 'alert_name')

        if not name_col:
            raise ValueError(f"Could not detect company name column. Headers: {headers}")
        if not reach_col:
            raise ValueError(f"Could not detect reach column. Headers: {headers}")

    print(f"  Detected columns:")
    print(f"    Company name: {name_col}")
    print(f"    Reach: {reach_col}")
    print(f"    Country: {country_col or '(not found)'}")
    print(f"    Alert/Source: {alert_col or '(not found)'}")

    # Second pass: read and deduplicate
    entities = defaultdict(lambda: {
        'Company Name': None,
        'Country': '',
        'Cumulative Reach': 0,
        'Normalized Name': '',
    })

    source_name = None
    total_rows = 0
    empty_names = 0

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1

            # Get source name from first row with it
            if not source_name and alert_col and row.get(alert_col):
                source_name = row.get(alert_col)

            company_name = row.get(name_col, '').strip()
            if not company_name:
                empty_names += 1
                continue

            norm_name = normalize_name(company_name)

            try:
                reach = int(row.get(reach_col, 0) or 0)
            except (ValueError, TypeError):
                reach = 0

            # Keep record with highest reach
            if reach > entities[norm_name]['Cumulative Reach']:
                entities[norm_name]['Company Name'] = company_name
                entities[norm_name]['Cumulative Reach'] = reach
                entities[norm_name]['Normalized Name'] = norm_name
                if country_col:
                    entities[norm_name]['Country'] = row.get(country_col, '')

    # Filter by threshold and sort by reach
    companies = [
        e for e in entities.values()
        if e['Cumulative Reach'] >= threshold
    ]
    companies.sort(key=lambda x: x['Cumulative Reach'], reverse=True)

    stats = {
        'total_rows': total_rows,
        'empty_names': empty_names,
        'unique_companies': len(entities),
        'above_threshold': len(companies),
    }

    return companies, source_name, stats


# =============================================================================
# ENRICHMENT
# =============================================================================

def post_batch_tasks(companies_batch, batch_num):
    """POST a batch of tasks to DataForSEO queue"""
    post_data = []

    for company in companies_batch:
        company_name = company['Company Name']
        country = company.get('Country', '')
        # Handle multi-country entries (e.g., "DE, IN, PE")
        if ',' in country:
            country = country.split(',')[0].strip()
        location = COUNTRY_LOCATIONS.get(country, 'United States')
        query = f'"{company_name}" official website'

        post_data.append({
            'keyword': query,
            'location_name': location,
            'language_code': 'en',
            'depth': 10,
            'tag': company_name
        })

    try:
        response = requests.post(
            DFS_TASK_POST,
            headers=get_auth_header(),
            json=post_data,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()

        if data.get('status_code') != 20000:
            print(f"  ✗ Batch {batch_num} API error: {data.get('status_message')}")
            return {}

        task_mapping = {}
        for task in data.get('tasks', []):
            task_id = task.get('id')
            company_name = task.get('data', {}).get('tag')
            if task_id and company_name:
                task_mapping[task_id] = company_name

        print(f"  ✓ Batch {batch_num}: Queued {len(task_mapping)} tasks")
        return task_mapping

    except Exception as e:
        print(f"  ✗ Batch {batch_num} error: {str(e)}")
        return {}


def get_ready_tasks():
    """Get list of task IDs that are ready"""
    try:
        response = requests.get(
            DFS_TASKS_READY,
            headers=get_auth_header(),
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get('status_code') != 20000:
            return []

        ready_ids = []
        for task in data.get('tasks', []):
            result = task.get('result') or []
            for item in result:
                task_id = item.get('id')
                if task_id:
                    ready_ids.append(task_id)

        return ready_ids

    except Exception as e:
        return []


def get_task_result(task_id, filter_domains):
    """Get result for a specific task"""
    try:
        url = f"{DFS_TASK_GET}/{task_id}"
        response = requests.get(
            url,
            headers=get_auth_header(),
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get('status_code') != 20000:
            return None, f"API error: {data.get('status_message')}", 'Unknown'

        tasks = data.get('tasks', [])
        if not tasks:
            return None, 'No tasks in response', 'Unknown'

        task = tasks[0]
        company_name = task.get('data', {}).get('tag', 'Unknown')

        if task.get('status_code') != 20000:
            return None, f"Task error: {task.get('status_message')}", company_name

        result = task.get('result', [])
        if not result:
            return None, 'No result', company_name

        items = result[0].get('items', [])
        if not items:
            return None, 'No items', company_name

        # Find first non-filtered organic result
        for item in items:
            if item.get('type') == 'organic':
                url = item.get('url', '')
                domain = extract_domain(url)

                if domain and not is_filtered_domain(domain, filter_domains):
                    return domain, 'success', company_name

        return None, 'no_domain', company_name

    except Exception as e:
        return None, f'Error: {str(e)}', 'Unknown'


def run_enrichment(companies, filter_domains):
    """Run the enrichment process"""
    total = len(companies)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\nPosting {total} tasks in {num_batches} batches...")

    all_task_mappings = {}
    for batch_num in range(num_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total)
        batch = companies[start_idx:end_idx]

        task_mapping = post_batch_tasks(batch, batch_num + 1)
        all_task_mappings.update(task_mapping)

        if batch_num < num_batches - 1:
            time.sleep(0.5)

    total_tasks = len(all_task_mappings)
    print(f"\n✓ Total tasks queued: {total_tasks}")

    # Wait for results
    print("\nWaiting for results...")
    results = {}
    retrieved = set()
    start_time = time.time()

    while len(retrieved) < total_tasks:
        elapsed = time.time() - start_time

        if elapsed > MAX_WAIT_TIME:
            print(f"\n⚠ Timeout after {MAX_WAIT_TIME}s. Retrieved {len(retrieved)}/{total_tasks}")
            break

        ready_ids = get_ready_tasks()
        new_ready = [tid for tid in ready_ids if tid in all_task_mappings and tid not in retrieved]

        if new_ready:
            for task_id in new_ready:
                domain, status, company_name = get_task_result(task_id, filter_domains)
                results[company_name] = (domain, status)
                retrieved.add(task_id)

                if domain:
                    print(f"  ✓ {company_name} → {domain}")
                else:
                    print(f"  ✗ {company_name} → {status}")

        progress = len(retrieved) / total_tasks * 100
        print(f"  Progress: {len(retrieved)}/{total_tasks} ({progress:.1f}%) - {elapsed:.0f}s")

        if len(retrieved) < total_tasks:
            time.sleep(POLL_INTERVAL)

    # Mark unprocessed companies
    for company in companies:
        name = company['Company Name']
        if name not in results:
            results[name] = (None, 'timeout')

    return results


# =============================================================================
# OUTPUT
# =============================================================================

def export_outputs(companies, results, source_name, master_path, master_data, data_dir):
    """Export Apollo CSV, update master, save log"""
    today = date.today().isoformat()
    source_normalized = normalize_source_name(source_name)

    # Create output directory
    output_dir = data_dir / 'generated-outputs'
    output_subdir = output_dir / f'{source_normalized}-{today}'
    output_subdir.mkdir(parents=True, exist_ok=True)

    apollo_path = output_subdir / f'apollo_import_{today}.csv'
    log_path = output_subdir / f'enrichment_log.txt'
    summary_path = output_subdir / f'run_summary.txt'

    # Prepare data
    apollo_rows = []
    log_entries = []
    success_count = 0
    failed_count = 0

    for company in companies:
        name = company['Company Name']
        norm_name = normalize_name(name)
        domain, status = results.get(name, (None, 'unknown'))

        # Update master
        master_data[norm_name] = {
            'Company Name': name,
            'Website': domain or '',
            'Country': company.get('Country', ''),
            'Cumulative Reach': company.get('Cumulative Reach', 0),
            'Status': 'success' if domain else 'no_domain',
            'Enriched Date': today,
            'Normalized Name': norm_name,
        }

        if domain:
            success_count += 1
            log_entries.append(f"✓ {name} → {domain}")
            apollo_rows.append({
                'Company Name': name,
                'Website': domain,
                'Country': company.get('Country', ''),
                'Cumulative Reach': company.get('Cumulative Reach', 0),
            })
        else:
            failed_count += 1
            log_entries.append(f"✗ {name} → {status}")

    # Write Apollo CSV (success only)
    if apollo_rows:
        fieldnames = ['Company Name', 'Website', 'Country', 'Cumulative Reach']
        with open(apollo_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(apollo_rows)

    # Write log
    log_content = f"""Mentions Enrichment Log
{'=' * 70}
Date: {today}
Source: {source_name}

RESULTS
-------
Total enriched: {len(companies)}
Successful: {success_count} ({success_count/len(companies)*100:.1f}%)
Failed: {failed_count} ({failed_count/len(companies)*100:.1f}%)

DETAILS
-------
""" + '\n'.join(log_entries)

    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(log_content)

    # Write summary
    summary = f"""Run Summary
===========
Date: {today}
Source: {source_name}
Companies enriched: {len(companies)}
Successful: {success_count}
Failed: {failed_count}
Apollo CSV: {apollo_path}
Master file: {master_path}
"""

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)

    # Save master file
    save_master_file(master_path, master_data)

    return apollo_path, success_count, failed_count


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Enrich mention tracking CSV with company domains')
    parser.add_argument('input_csv', help='Path to input CSV file')
    parser.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD,
                        help=f'Minimum reach threshold (default: {DEFAULT_THRESHOLD})')
    parser.add_argument('--source', help='Override source name (default: auto-detect from CSV)')
    parser.add_argument('--data-dir', help='Data directory for this competitor (e.g., data/hootsuite/)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    # Set data_dir: use provided value or fall back to old structure
    if args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        # Backward compatibility
        data_dir = SKILL_DIR

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print("=" * 70)
    print("Mentions Enrichment - Domain Finder")
    print("=" * 70)
    print()

    # Check credentials
    if not DFS_LOGIN or not DFS_PASSWORD:
        print("Error: DataForSEO credentials not found.")
        print("Set DATAFORSEO_USERNAME and DATAFORSEO_PASSWORD environment variables.")
        sys.exit(1)

    # Load filter domains
    filter_domains = load_filter_domains()
    print(f"Loaded {len(filter_domains)} filter domains")

    # Step 1: Read and deduplicate
    print(f"\nStep 1: Reading {input_path.name}...")
    companies, source_name, stats = read_and_deduplicate(input_path, args.threshold)

    if args.source:
        source_name = args.source
    if not source_name:
        source_name = input_path.stem

    print(f"\n  Source: {source_name}")
    print(f"  Total rows: {stats['total_rows']:,}")
    print(f"  Empty names skipped: {stats['empty_names']:,}")
    print(f"  Unique companies: {stats['unique_companies']:,}")
    print(f"  Above threshold (≥{args.threshold:,}): {stats['above_threshold']:,}")

    if not companies:
        print("\nNo companies above threshold. Exiting.")
        sys.exit(0)

    # Step 2: Compare with master
    print(f"\nStep 2: Comparing with master file...")
    master_path = get_master_path(source_name, data_dir)
    master_data = load_master_file(master_path)

    print(f"  Master file: {master_path}")
    print(f"  Existing entries: {len(master_data):,}")

    # Filter out companies already in master
    new_companies = [
        c for c in companies
        if c['Normalized Name'] not in master_data
    ]
    skipped = len(companies) - len(new_companies)

    print(f"  Already in master (skipped): {skipped:,}")
    print(f"  New companies to enrich: {len(new_companies):,}")

    if not new_companies:
        print("\nNo new companies to enrich. All are already in master.")
        sys.exit(0)

    # Step 3: Dry run preview
    print("\n" + "=" * 70)
    print("DRY RUN PREVIEW")
    print("=" * 70)

    estimated_cost = len(new_companies) * COST_PER_QUERY
    balance = check_dfs_balance()

    print(f"\nSource file: {input_path.name}")
    print(f"Tracking source: {source_name}")
    print(f"Master file: {master_path.name} ({len(master_data)} existing)")
    print()
    print(f"Total rows: {stats['total_rows']:,}")
    print(f"After dedup: {stats['unique_companies']:,} unique companies")
    print(f"After reach filter (≥{args.threshold:,}): {stats['above_threshold']:,} companies")
    print(f"Already in master: {skipped:,} (skipped)")
    print(f"New companies to enrich: {len(new_companies):,}")
    print()
    print(f"Estimated cost: ${estimated_cost:.2f} ({len(new_companies)} × ${COST_PER_QUERY})")
    if balance is not None:
        status = "✓" if balance >= estimated_cost else "⚠ LOW"
        print(f"DataForSEO balance: ${balance:.2f} {status}")
    else:
        print("DataForSEO balance: (could not check)")

    print(f"\nTop 10 new companies by reach:")
    for i, c in enumerate(new_companies[:10], 1):
        print(f"  {i}. {c['Company Name']} - {c['Cumulative Reach']:,} reach")
    if len(new_companies) > 10:
        print(f"  ... and {len(new_companies) - 10} more")

    # Confirmation
    print()
    if not args.yes:
        response = input("Proceed with enrichment? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Step 4: Run enrichment
    print("\n" + "=" * 70)
    print("ENRICHMENT")
    print("=" * 70)

    results = run_enrichment(new_companies, filter_domains)

    # Step 5: Export outputs
    print("\n" + "=" * 70)
    print("SAVING OUTPUTS")
    print("=" * 70)

    apollo_path, success, failed = export_outputs(
        new_companies, results, source_name, master_path, master_data, data_dir
    )

    # Final summary
    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Successful: {success:,} ({success/len(new_companies)*100:.1f}%)")
    print(f"Failed: {failed:,} ({failed/len(new_companies)*100:.1f}%)")
    print(f"Cost: ~${len(new_companies) * COST_PER_QUERY:.2f}")
    print()
    print(f"Apollo CSV: {apollo_path}")
    print(f"Master updated: {master_path} (+{len(new_companies)} entries)")
    print("=" * 70)


if __name__ == '__main__':
    main()
