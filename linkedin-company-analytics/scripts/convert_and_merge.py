#!/usr/bin/env python3
"""
Convert and Merge — Convert old metrics_enriched.csv format to new schema and merge into master.

Old format fields:
  - posting_frequency (text labels like "active (2-4/wk)")

New format fields:
  - posting_range (0-5 numeric)
  - posting_range_label (standardized labels)
  - posting_frequency_category (Infrequent/Frequent)
  - posts_total (same as posts_last_90d)
  - posts_last_60d (need to calculate or leave empty)

Usage:
    python scripts/convert_and_merge.py \
        --old generated-outputs/abm_1k-2026-02-18/metrics_enriched.csv \
        --master master/abm_accounts_master.csv
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
# CONVERSION
# =============================================================================

def convert_posting_frequency_to_range(posting_frequency, posts_last_90d):
    """
    Convert old posting_frequency text to new posting_range numeric.

    Old labels:
      - "inactive (0 posts/90d)"
      - "rare (1-2/90d)"
      - "occasional (0.5-1/wk)"
      - "active (2-4/wk)"
      - "very active (4+/wk)"

    New ranges based on posts_last_90d:
      0: Inactive (0)
      1: Very Low (1-3)
      2: Low (4-10)
      3: Medium (11-25)
      4: High (26-50)
      5: Very High (50+)
    """
    try:
        posts = int(posts_last_90d) if posts_last_90d else 0
    except (ValueError, TypeError):
        posts = 0

    if posts == 0:
        return 0, 'Inactive (0 posts/90d)', 'Infrequent'
    elif posts <= 3:
        return 1, 'Very Low (1-3 posts/90d)', 'Infrequent'
    elif posts <= 10:
        return 2, 'Low (4-10 posts/90d)', 'Infrequent'
    elif posts <= 25:
        return 3, 'Medium (11-25 posts/90d)', 'Frequent'
    elif posts <= 50:
        return 4, 'High (26-50 posts/90d)', 'Frequent'
    else:
        return 5, 'Very High (50+ posts/90d)', 'Frequent'


def convert_row(old_row):
    """Convert old format row to new format."""
    posts_last_90d = old_row.get('posts_last_90d', '').strip()
    posts_last_30d = old_row.get('posts_last_30d', '').strip()

    posting_range, posting_range_label, posting_freq_cat = convert_posting_frequency_to_range(
        old_row.get('posting_frequency', ''),
        posts_last_90d
    )

    # Calculate posts_last_60d estimate (if we have 30d and 90d)
    # Simple estimate: if posts_last_30d exists, assume posts_last_60d ≈ posts_last_30d * 2
    posts_last_60d = ''
    if posts_last_30d and posts_last_90d:
        try:
            p30 = int(posts_last_30d)
            p90 = int(posts_last_90d)
            # Better estimate: 60d posts = 30d posts + (90d-30d)/2
            posts_last_60d = str(min(p30 + (p90 - p30) // 2, p90))
        except (ValueError, TypeError):
            posts_last_60d = ''

    new_row = {
        'linkedin_url': old_row.get('linkedin_url', '').strip(),
        'domain': old_row.get('domain', '').strip(),
        'company_name': old_row.get('company_name', '').strip(),
        'follower_count': old_row.get('follower_count', '').strip(),
        'posting_range': posting_range,
        'posting_range_label': posting_range_label,
        'posting_frequency_category': posting_freq_cat,
        'posts_total': posts_last_90d,  # Same as posts_last_90d
        'posts_last_90d': posts_last_90d,
        'posts_last_60d': posts_last_60d,
        'posts_last_30d': posts_last_30d,
        'avg_posts_per_week': old_row.get('avg_posts_per_week', '').strip(),
        'days_since_last_post': old_row.get('days_since_last_post', '').strip(),
        'last_post_date': old_row.get('last_post_date', '').strip(),
        'top_post_likes': old_row.get('top_post_likes', '').strip(),
        'snapshot_date': old_row.get('snapshot_date', '').strip(),
    }

    return new_row


# =============================================================================
# MERGE
# =============================================================================

def load_master(master_path):
    """Load existing master file, keyed by normalized URL."""
    master = {}

    if not master_path.exists():
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


def merge_converted_data(master, converted_data):
    """Merge converted data into master, updating rows that exist."""
    updated_count = 0

    for normalized_url, new_row in converted_data.items():
        if normalized_url in master:
            # Update existing entry
            master[normalized_url].update({
                'posting_range': new_row['posting_range'],
                'posting_range_label': new_row['posting_range_label'],
                'posting_frequency_category': new_row['posting_frequency_category'],
                'posts_total': new_row['posts_total'],
                'posts_last_90d': new_row['posts_last_90d'],
                'posts_last_60d': new_row['posts_last_60d'],
                'posts_last_30d': new_row['posts_last_30d'],
                'avg_posts_per_week': new_row['avg_posts_per_week'],
                'days_since_last_post': new_row['days_since_last_post'],
                'last_post_date': new_row['last_post_date'],
                'top_post_likes': new_row['top_post_likes'],
                'snapshot_date': new_row['snapshot_date'],
            })
            updated_count += 1
        else:
            # Add new entry (shouldn't happen if master is complete)
            master[normalized_url] = new_row

    return updated_count


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Convert old metrics_enriched.csv and merge into master')
    parser.add_argument('--old', required=True, help='Path to old metrics_enriched.csv')
    parser.add_argument('--master', required=True, help='Path to master CSV')

    args = parser.parse_args()

    old_path = Path(args.old)
    master_path = Path(args.master)

    if not old_path.exists():
        print(f"Error: Old data file not found: {old_path}")
        sys.exit(1)

    if not master_path.exists():
        print(f"Error: Master file not found: {master_path}")
        sys.exit(1)

    print("=" * 70)
    print("CONVERT AND MERGE")
    print("=" * 70)
    print(f"Old data: {old_path}")
    print(f"Master:   {master_path}")
    print()

    # Load and convert old data
    print("Loading and converting old data...")
    converted_data = {}

    with open(old_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            new_row = convert_row(row)
            url = new_row['linkedin_url']
            if url:
                normalized = normalize_company_url(url)
                converted_data[normalized] = new_row

    print(f"✓ Converted {len(converted_data)} companies")

    # Load master
    print("Loading master...")
    master = load_master(master_path)
    print(f"✓ Loaded {len(master)} existing entries")

    # Merge
    print("Merging...")
    updated_count = merge_converted_data(master, converted_data)
    print(f"✓ Updated {updated_count} companies")

    # Write
    fieldnames = [
        'linkedin_url',
        'domain',
        'company_name',
        'follower_count',
        'posting_range',
        'posting_range_label',
        'posting_frequency_category',
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

    sorted_rows = sorted(master.values(), key=lambda r: r.get('linkedin_url', ''))

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_rows)

    print(f"✓ Wrote {len(sorted_rows)} companies to: {master_path}")

    # Summary stats
    no_data = sum(1 for r in sorted_rows if r.get('posting_range') == '')
    infrequent = sum(1 for r in sorted_rows if r.get('posting_frequency_category') == 'Infrequent')
    frequent = sum(1 for r in sorted_rows if r.get('posting_frequency_category') == 'Frequent')

    print()
    print("=" * 70)
    print("MERGE COMPLETE")
    print("=" * 70)
    print(f"Total companies:  {len(sorted_rows)}")
    print(f"Updated:          {updated_count}")
    print()
    print("Posting Frequency Distribution:")
    print(f"  Infrequent: {infrequent:4d} ({infrequent/len(sorted_rows)*100:5.1f}%)")
    print(f"  Frequent:   {frequent:4d} ({frequent/len(sorted_rows)*100:5.1f}%)")
    print(f"  No data:    {no_data:4d} ({no_data/len(sorted_rows)*100:5.1f}%)")
    print("=" * 70)


if __name__ == '__main__':
    main()
