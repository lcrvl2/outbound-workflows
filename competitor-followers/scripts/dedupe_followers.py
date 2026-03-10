#!/usr/bin/env python3
"""
Dedupe Followers - Cross-competitor deduplication with master file tracking.

Loads master file to prevent re-processing, deduplicates by LinkedIn URL,
tracks which competitor each follower came from (attribution).

Input: followers_raw.json (from extract_followers.py)
Output: followers_deduped.json

Usage:
    python dedupe_followers.py <input_json> <output_json> --source NAME
"""

import json
import csv
import sys
import argparse
from pathlib import Path
from datetime import date

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
MASTER_DIR = SKILL_DIR / 'master'


# =============================================================================
# MASTER FILE
# =============================================================================

def normalize_source_name(source_name):
    """Normalize source name for file naming"""
    import re
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_master_path(source_name):
    """Get path to master CSV for this source"""
    normalized = normalize_source_name(source_name)
    return MASTER_DIR / f'{normalized}_followers_master.csv'


def load_master_urls(source_name):
    """Load LinkedIn URLs from master file (already processed)"""
    master_path = get_master_path(source_name)
    urls = set()

    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                linkedin_url = row.get('linkedin_url', '').strip().lower()
                if linkedin_url:
                    urls.add(linkedin_url)

    return urls


def update_master(source_name, new_followers):
    """Append new followers to master file"""
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    master_path = get_master_path(source_name)

    fieldnames = [
        'linkedin_url', 'name', 'title', 'company',
        'source_competitor', 'date_extracted'
    ]

    # Load existing rows
    existing_rows = []
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    # Append new followers
    all_rows = existing_rows + new_followers

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    return master_path


# =============================================================================
# DEDUPLICATION
# =============================================================================

def dedupe_followers(followers, existing_urls):
    """
    Deduplicate followers by LinkedIn URL.

    - Remove duplicates within input (keep first occurrence)
    - Remove followers already in master file
    - Track which competitor each follower came from
    """
    seen_urls = set()
    deduped = []

    stats = {
        'total_input': len(followers),
        'duplicates_within_input': 0,
        'already_in_master': 0,
        'new_unique': 0,
    }

    for follower in followers:
        linkedin_url = follower.get('linkedin_url', '').strip().lower()

        if not linkedin_url:
            continue

        # Check if already in master
        if linkedin_url in existing_urls:
            stats['already_in_master'] += 1
            continue

        # Check for duplicates within input
        if linkedin_url in seen_urls:
            stats['duplicates_within_input'] += 1
            continue

        seen_urls.add(linkedin_url)
        deduped.append(follower)
        stats['new_unique'] += 1

    return deduped, stats


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Deduplicate followers across competitors and master file'
    )
    parser.add_argument('input_json', help='Input JSON file (followers_raw.json)')
    parser.add_argument('output_json', help='Output JSON file (followers_deduped.json)')
    parser.add_argument('--source', required=True, help='Source name for master file')

    args = parser.parse_args()

    print("=" * 70)
    print("FOLLOWER DEDUPLICATION")
    print("=" * 70)

    # Load input
    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        followers = json.load(f)

    print(f"\nSource: {args.source}")
    print(f"Input followers: {len(followers)}")

    # Load master
    existing_urls = load_master_urls(args.source)
    print(f"Already processed (in master): {len(existing_urls)}")

    # Deduplicate
    deduped, stats = dedupe_followers(followers, existing_urls)

    print("\nDeduplication Results:")
    print(f"  Total input: {stats['total_input']}")
    print(f"  Duplicates within input: {stats['duplicates_within_input']}")
    print(f"  Already in master: {stats['already_in_master']}")
    print(f"  New unique followers: {stats['new_unique']}")

    if not deduped:
        print("\n⚠️  No new followers to process. All already in master.")
        # Write empty output
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
        sys.exit(0)

    # Add extraction date
    today = date.today().isoformat()
    for follower in deduped:
        follower['date_extracted'] = today

    # Update master
    master_path = update_master(args.source, deduped)
    print(f"\n✓ Master file updated: {master_path}")

    # Save output
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved {len(deduped)} unique followers to: {output_path}")


if __name__ == '__main__':
    main()
