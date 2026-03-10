#!/usr/bin/env python3
"""
Scrape Posts — Fetch LinkedIn company posts via harvestapi actor (3-month window).

Processes companies in batches of 50, writes incremental JSON after each batch.
Only original posts are fetched (includeReposts=false) for accurate frequency calculation.

Usage:
    python scripts/scrape_posts.py --input companies.csv --output-dir PATH [--batch-size 50] [--yes]

Input CSV: must have a `linkedin_url` column.
Output: raw_posts.json (array of all post items from harvestapi)
"""

import csv
import json
import sys
import os
import re
import time
import argparse
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

APIFY_TOKEN = os.getenv('APIFY_TOKEN', '')
APIFY_BASE = 'https://api.apify.com/v2'

ACTOR_POSTS = 'harvestapi~linkedin-company-posts'

BATCH_SIZE = 50
POLL_INTERVAL = 15
MAX_POLL_ITERATIONS = 80   # 80 × 15s = 20 min max
COST_PER_POST = 0.002
POSTS_LOW_ESTIMATE = 3    # avg posts per company per 3 months (inactive)
POSTS_HIGH_ESTIMATE = 10  # avg posts per company per 3 months (active)


# =============================================================================
# URL NORMALIZATION
# =============================================================================

def normalize_company_url(url):
    """Normalize LinkedIn company URL to canonical form."""
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
# APIFY HELPERS
# =============================================================================

def start_run(urls):
    """Start a harvestapi actor run for a batch of company URLs."""
    try:
        response = requests.post(
            f'{APIFY_BASE}/acts/{ACTOR_POSTS}/runs',
            params={'token': APIFY_TOKEN},
            json={
                'targetUrls': urls,
                'postedLimit': '3months',
                'maxPosts': 0,
                'includeReposts': False,
                'includeQuotePosts': False,
                'scrapeReactions': False,
                'scrapeComments': False,
            },
            timeout=30,
        )
        response.raise_for_status()
        run_data = response.json().get('data', {})
        run_id = run_data.get('id')
        if not run_id:
            return None, 'no_run_id'
        return run_id, 'started'
    except Exception as e:
        return None, f'error: {str(e)}'


def poll_run(run_id, batch_label=''):
    """Poll until run completes. Returns (items, error_or_None)."""
    status_data = {}
    for i in range(MAX_POLL_ITERATIONS):
        time.sleep(POLL_INTERVAL)
        try:
            resp = requests.get(
                f'{APIFY_BASE}/actor-runs/{run_id}',
                params={'token': APIFY_TOKEN},
                timeout=15,
            )
            status_data = resp.json().get('data', {})
            status = status_data.get('status')
            elapsed = (i + 1) * POLL_INTERVAL
            print(f"    {batch_label} [{elapsed}s] {status}")

            if status == 'SUCCEEDED':
                break
            elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                return [], f'apify_{status.lower()}'
        except Exception as e:
            print(f"    Poll error: {e}")
            continue
    else:
        return [], 'timeout'

    dataset_id = status_data.get('defaultDatasetId')
    if not dataset_id:
        return [], 'no_dataset'

    items = []
    offset = 0
    page_size = 1000
    while True:
        try:
            resp = requests.get(
                f'{APIFY_BASE}/datasets/{dataset_id}/items',
                params={
                    'token': APIFY_TOKEN,
                    'offset': offset,
                    'limit': page_size,
                },
                timeout=60,
            )
            page = resp.json()
            if not page:
                break
            items.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        except Exception as e:
            print(f"    Dataset fetch error: {e}")
            break

    return items, None


# =============================================================================
# CSV LOADING
# =============================================================================

def load_companies(csv_path):
    """Load all rows with linkedin_url from CSV."""
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (
                row.get('linkedin_url') or
                row.get('LinkedIn URL') or
                row.get('Company Linkedin Url') or
                row.get('Company LinkedIn URL') or
                ''
            ).strip()
            domain = (
                row.get('domain') or
                row.get('Website') or
                ''
            ).strip()
            if url:
                rows.append({
                    'linkedin_url': normalize_company_url(url),
                    'domain': domain,
                })
    return rows


# =============================================================================
# INCREMENTAL JSON WRITE
# =============================================================================

def load_existing_output(output_path):
    """Load existing items from output file (crash recovery)."""
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_output(output_path, items):
    """Write all items to JSON output file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


# =============================================================================
# MAIN SCRAPE
# =============================================================================

def scrape_posts(companies, output_path, batch_size=BATCH_SIZE):
    """Scrape posts for all companies, incrementally saving after each batch."""
    all_items = load_existing_output(output_path)
    already_done = len(all_items)
    if already_done:
        print(f"\n  Resuming: {already_done} items already saved.")

    total = len(companies)
    total_batches = (total + batch_size - 1) // batch_size
    failed_batches = []

    for batch_num in range(total_batches):
        start = batch_num * batch_size
        batch = companies[start:start + batch_size]
        urls = [c['linkedin_url'] for c in batch]

        print(f"\n  Batch {batch_num + 1}/{total_batches} ({len(urls)} URLs)")

        run_id, status = start_run(urls)
        if not run_id:
            print(f"    Failed to start: {status}")
            failed_batches.append((batch_num + 1, urls, status))
            continue

        print(f"    Run ID: {run_id}")
        items, err = poll_run(run_id, batch_label=f'Batch {batch_num + 1}')

        if err:
            print(f"    Batch failed: {err}")
            failed_batches.append((batch_num + 1, urls, err))
            continue

        print(f"    Got {len(items)} posts")
        all_items.extend(items)
        save_output(output_path, all_items)
        print(f"    Saved incrementally → total {len(all_items)} posts")

    return all_items, failed_batches


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Scrape LinkedIn company posts via harvestapi (3-month window)'
    )
    parser.add_argument('--input', required=True, help='CSV with linkedin_url column')
    parser.add_argument('--output-dir', required=True, help='Output directory path')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help=f'URLs per actor run (default: {BATCH_SIZE})')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompt')
    args = parser.parse_args()

    print("=" * 70)
    print("SCRAPE POSTS — harvestapi/linkedin-company-posts")
    print("=" * 70)

    if not APIFY_TOKEN:
        print("Error: APIFY_TOKEN not set in .env")
        sys.exit(1)

    csv_path = Path(args.input)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    companies = load_companies(str(csv_path))
    if not companies:
        print("No companies with LinkedIn URLs found.")
        sys.exit(0)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'raw_posts.json'

    total_batches = (len(companies) + args.batch_size - 1) // args.batch_size
    cost_low = len(companies) * POSTS_LOW_ESTIMATE * COST_PER_POST
    cost_high = len(companies) * POSTS_HIGH_ESTIMATE * COST_PER_POST

    print(f"\nInput:        {csv_path}")
    print(f"Companies:    {len(companies)}")
    print(f"Period:       3 months (original posts only)")
    print(f"Batch size:   {args.batch_size}")
    print(f"Batches:      {total_batches}")
    print(f"Output:       {output_path}")
    print(f"\nCost estimate: ${cost_low:.2f}–${cost_high:.2f}")
    print(f"  ({len(companies)} companies × {POSTS_LOW_ESTIMATE}–{POSTS_HIGH_ESTIMATE} posts × ${COST_PER_POST}/post)")
    print(f"  (active companies cost more — actual cost known only after run)")

    if output_path.exists():
        existing = load_existing_output(output_path)
        if existing:
            print(f"\nExisting output found: {len(existing)} posts — will append new batches.")

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    all_items, failed_batches = scrape_posts(companies, output_path, args.batch_size)

    print(f"\n{'=' * 70}")
    print("SCRAPE POSTS COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total posts:    {len(all_items)}")
    print(f"Failed batches: {len(failed_batches)}")
    est_actual_cost = len(all_items) * COST_PER_POST
    print(f"Estimated cost: {len(all_items)} posts × ${COST_PER_POST} = ${est_actual_cost:.2f}")
    print(f"Output:         {output_path}")

    if failed_batches:
        print("\nFailed batches:")
        for batch_num, urls, err in failed_batches:
            print(f"  Batch {batch_num}: {err}")
            for u in urls:
                print(f"    - {u}")


if __name__ == '__main__':
    main()
