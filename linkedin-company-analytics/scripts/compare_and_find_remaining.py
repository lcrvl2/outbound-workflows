#!/usr/bin/env python3
"""
Compare and Find Remaining — Identify unprocessed companies from ABM master list.

Compares metrics_enriched.csv (already processed) against ABM master list.
Outputs remaining_companies.csv with companies that still need LinkedIn analytics.

Usage:
    python scripts/compare_and_find_remaining.py \
        --abm-list "ABM accounts.csv" \
        --processed generated-outputs/abm_1k-2026-02-18/metrics_enriched.csv \
        --output remaining_companies.csv

Examples:
    # From workspace root
    cd linkedin-company-analytics
    python scripts/compare_and_find_remaining.py \
        --abm-list "../ABM accounts.csv" \
        --processed generated-outputs/abm_1k-2026-02-18/metrics_enriched.csv

    # Custom output location
    python scripts/compare_and_find_remaining.py \
        --abm-list "../ABM accounts.csv" \
        --processed generated-outputs/abm_1k-2026-02-18/metrics_enriched.csv \
        --output batch2_companies.csv
"""

import csv
import sys
import re
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass


# =============================================================================
# URL NORMALIZATION (from analyze_metrics.py)
# =============================================================================

def normalize_company_url(url):
    """Normalize LinkedIn company URL to canonical form for join key."""
    if not url:
        return ''
    url = url.lower().strip().rstrip('/')
    if '?' in url:
        url = url.split('?')[0]
    url = re.sub(r'https?://[a-z]{2,3}\.linkedin\.com/', 'https://www.linkedin.com/', url)
    url = re.sub(r'http://(www\.)?linkedin\.com/', 'https://www.linkedin.com/', url)
    if url.startswith('linkedin.com'):
        url = 'https://www.' + url
    return url


# =============================================================================
# CSV LOADING
# =============================================================================

def load_processed_urls(csv_path):
    """Load normalized LinkedIn URLs from metrics_enriched.csv."""
    urls = set()
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = (row.get('linkedin_url') or '').strip()
                if url:
                    normalized = normalize_company_url(url)
                    if normalized:
                        urls.add(normalized)
    except Exception as e:
        print(f"Error reading processed CSV: {e}")
        sys.exit(1)
    return urls


def load_abm_companies(csv_path):
    """Load all companies from ABM master list with metadata."""
    companies = []
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try multiple column name variations
                url = (
                    row.get('Company Linkedin Url') or
                    row.get('Company LinkedIn URL') or
                    row.get('linkedin_url') or
                    row.get('LinkedIn URL') or
                    ''
                ).strip()

                if not url:
                    continue

                normalized = normalize_company_url(url)
                if not normalized:
                    continue

                # Extract domain and company name
                domain = (
                    row.get('Website') or
                    row.get('domain') or
                    row.get('Domain') or
                    ''
                ).strip()

                company_name = (
                    row.get('Company Name') or
                    row.get('company_name') or
                    row.get('Account Name') or
                    ''
                ).strip()

                companies.append({
                    'linkedin_url': normalized,
                    'domain': domain,
                    'company_name': company_name,
                })
    except Exception as e:
        print(f"Error reading ABM master CSV: {e}")
        sys.exit(1)

    return companies


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Compare processed companies with ABM master to find remaining',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard usage
  python scripts/compare_and_find_remaining.py \\
      --abm-list "../ABM accounts.csv" \\
      --processed generated-outputs/abm_1k-2026-02-18/metrics_enriched.csv

  # Custom output
  python scripts/compare_and_find_remaining.py \\
      --abm-list "../ABM accounts.csv" \\
      --processed generated-outputs/abm_1k-2026-02-18/metrics_enriched.csv \\
      --output batch2_companies.csv
        """
    )

    parser.add_argument('--abm-list', required=True,
                        help='Path to ABM master CSV (full target list)')
    parser.add_argument('--processed', required=True,
                        help='Path to metrics_enriched.csv from previous run')
    parser.add_argument('--output', default='remaining_companies.csv',
                        help='Output CSV path (default: remaining_companies.csv)')

    args = parser.parse_args()

    # Validate input files
    abm_path = Path(args.abm_list)
    processed_path = Path(args.processed)

    if not abm_path.exists():
        print(f"Error: ABM master CSV not found: {abm_path}")
        sys.exit(1)

    if not processed_path.exists():
        print(f"Error: Processed CSV not found: {processed_path}")
        sys.exit(1)

    # Load data
    print("Loading processed companies...")
    processed_urls = load_processed_urls(str(processed_path))

    print("Loading ABM master list...")
    abm_companies = load_abm_companies(str(abm_path))

    # Find remaining companies
    remaining = [
        company for company in abm_companies
        if company['linkedin_url'] not in processed_urls
    ]

    # Deduplicate by URL (in case ABM list has duplicates)
    seen_urls = set()
    remaining_deduped = []
    for company in remaining:
        url = company['linkedin_url']
        if url not in seen_urls:
            seen_urls.add(url)
            remaining_deduped.append(company)

    # Stats
    total_abm = len(abm_companies)
    total_processed = len(processed_urls)
    total_remaining = len(remaining_deduped)

    # Print summary
    print()
    print("=" * 70)
    print("COMPARISON: ABM LIST vs PROCESSED COMPANIES")
    print("=" * 70)
    print(f"ABM Master:        {total_abm:4d} companies")
    print(f"Already Processed: {total_processed:4d} companies")
    print(f"Remaining:         {total_remaining:4d} companies")
    print("=" * 70)

    if total_remaining == 0:
        print("\nAll companies have been processed! No remaining companies to analyze.")
        return

    # Write output CSV
    output_path = Path(args.output)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['linkedin_url', 'domain', 'company_name']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for company in remaining_deduped:
            writer.writerow(company)

    print(f"\nOutput: {output_path}")
    print(f"Ready for: python scripts/run_pipeline.py --input {output_path} --source NAME")
    print("=" * 70)


if __name__ == '__main__':
    main()
