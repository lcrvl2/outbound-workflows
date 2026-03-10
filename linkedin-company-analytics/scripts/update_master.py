#!/usr/bin/env python3
"""
Update Master — Merge new posts_frequency.csv into master file.

Handles:
  - Existing entries: Update post metrics, keep follower_count
  - New entries: Add with post metrics, follower_count = empty
  - Normalize linkedin_url for matching
  - Update snapshot_date to today

Usage:
    python scripts/update_master.py \
        --master master/abm_1k_master.csv \
        --new generated-outputs/remaining_companies-2026-02-20/posts_frequency.csv \
        --source remaining_companies
"""

import csv
import re
import sys
from pathlib import Path
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass


# =============================================================================
# URL NORMALIZATION
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
# LOADING
# =============================================================================

def load_master(master_path):
    """Load existing master file, keyed by normalized URL."""
    master = {}

    if not master_path.exists():
        print(f"Note: Master file not found at {master_path} — will create new")
        return master

    with open(master_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('linkedin_url', '').strip()
            if not url:
                continue
            normalized = normalize_company_url(url)
            master[normalized] = row

    return master


def load_new_data(new_path):
    """Load new posts_frequency.csv, keyed by normalized URL."""
    new_data = {}

    with open(new_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('linkedin_url', '').strip()
            if not url:
                continue
            normalized = normalize_company_url(url)
            new_data[normalized] = row

    return new_data


# =============================================================================
# MERGE
# =============================================================================

def merge(master, new_data, snapshot_date):
    """
    Merge new data into master.

    - Existing entries: Update post metrics, keep follower_count
    - New entries: Add with post metrics, follower_count = empty
    """
    merged = {}

    # Process all existing master entries
    for normalized_url, master_row in master.items():
        new_row = new_data.get(normalized_url)

        if new_row:
            # Update existing entry with new post metrics
            merged_row = {
                'linkedin_url': master_row['linkedin_url'],  # Keep original format
                'domain': new_row.get('domain') or master_row.get('domain', ''),
                'company_name': new_row.get('company_name') or master_row.get('company_name', ''),
                'follower_count': master_row.get('follower_count', ''),  # Keep existing
                'posting_range': new_row.get('posting_range', ''),
                'posting_range_label': new_row.get('posting_range_label', ''),
                'posts_total': new_row.get('posts_total', ''),
                'posts_last_90d': new_row.get('posts_last_90d', ''),
                'posts_last_60d': new_row.get('posts_last_60d', ''),
                'posts_last_30d': new_row.get('posts_last_30d', ''),
                'avg_posts_per_week': new_row.get('avg_posts_per_week', ''),
                'days_since_last_post': new_row.get('days_since_last_post', ''),
                'last_post_date': new_row.get('last_post_date', ''),
                'top_post_likes': new_row.get('top_post_likes', ''),
                'snapshot_date': snapshot_date,
            }
        else:
            # Keep existing entry (no new data)
            merged_row = master_row.copy()

        merged[normalized_url] = merged_row

    # Add new entries not in master
    for normalized_url, new_row in new_data.items():
        if normalized_url not in merged:
            merged_row = {
                'linkedin_url': new_row['linkedin_url'],
                'domain': new_row.get('domain', ''),
                'company_name': new_row.get('company_name', ''),
                'follower_count': '',  # No follower data
                'posting_range': new_row.get('posting_range', ''),
                'posting_range_label': new_row.get('posting_range_label', ''),
                'posts_total': new_row.get('posts_total', ''),
                'posts_last_90d': new_row.get('posts_last_90d', ''),
                'posts_last_60d': new_row.get('posts_last_60d', ''),
                'posts_last_30d': new_row.get('posts_last_30d', ''),
                'avg_posts_per_week': new_row.get('avg_posts_per_week', ''),
                'days_since_last_post': new_row.get('days_since_last_post', ''),
                'last_post_date': new_row.get('last_post_date', ''),
                'top_post_likes': new_row.get('top_post_likes', ''),
                'snapshot_date': snapshot_date,
            }
            merged[normalized_url] = merged_row

    return merged


# =============================================================================
# OUTPUT
# =============================================================================

def write_master(output_path, merged):
    """Write merged master file."""
    fieldnames = [
        'linkedin_url',
        'domain',
        'company_name',
        'follower_count',
        'posting_range',
        'posting_range_label',
        'posts_total',
        'posts_last_90d',
        'posts_last_60d',
        'posts_last_30d',
        'avg_posts_per_week',
        'days_since_last_post',
        'last_post_date',
        'top_post_likes',
        'snapshot_date',
    ]

    # Sort by linkedin_url for consistency
    sorted_rows = sorted(merged.values(), key=lambda r: r['linkedin_url'])

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_rows)

    print(f"✓ Wrote {len(sorted_rows)} companies to: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Update master CSV with new post frequency data')
    parser.add_argument('--master', required=True, help='Path to master CSV')
    parser.add_argument('--new', required=True, help='Path to new posts_frequency.csv')
    parser.add_argument('--source', required=True, help='Source name for this update')

    args = parser.parse_args()

    master_path = Path(args.master)
    new_path = Path(args.new)

    if not new_path.exists():
        print(f"Error: New data file not found: {new_path}")
        sys.exit(1)

    snapshot_date = date.today().isoformat()

    print("=" * 70)
    print("UPDATE MASTER CSV")
    print("=" * 70)
    print(f"Master:   {master_path}")
    print(f"New data: {new_path}")
    print(f"Source:   {args.source}")
    print(f"Date:     {snapshot_date}")
    print()

    # Load
    print("Loading master...")
    master = load_master(master_path)
    print(f"✓ Loaded {len(master)} existing entries")

    print("Loading new data...")
    new_data = load_new_data(new_path)
    print(f"✓ Loaded {len(new_data)} new entries")

    # Merge
    print("Merging...")
    merged = merge(master, new_data, snapshot_date)

    updates = sum(1 for url in new_data if url in master)
    additions = sum(1 for url in new_data if url not in master)

    print(f"✓ Merged: {updates} updates + {additions} additions = {len(merged)} total")

    # Write
    master_path.parent.mkdir(parents=True, exist_ok=True)
    write_master(master_path, merged)

    print()
    print("=" * 70)
    print("MASTER UPDATE COMPLETE")
    print("=" * 70)
    print(f"Total companies: {len(merged)}")
    print(f"Updated:         {updates}")
    print(f"Added:           {additions}")
    print("=" * 70)


if __name__ == '__main__':
    main()
