#!/usr/bin/env python3
"""
Test Actors — Validate both Apify actors on 5 companies before full run.

Run this FIRST to confirm exact field names from rigelbytes output
(output schema is empty in Apify store — field names unknown until tested).

Usage:
    python scripts/test_actors.py --input test_5.csv

Input CSV must have a `linkedin_url` column (and optionally `domain`).

Output:
    generated-outputs/test-{date}/raw_followers.json
    generated-outputs/test-{date}/raw_posts.json
    Field audit printed to console
"""

import csv
import json
import sys
import os
import time
import argparse
import requests
from pathlib import Path
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
OUTPUT_DIR = SKILL_DIR / 'generated-outputs'

APIFY_TOKEN = os.getenv('APIFY_TOKEN', '')
APIFY_BASE = 'https://api.apify.com/v2'

ACTOR_FOLLOWERS = 'rigelbytes~linkedin-company-details'
ACTOR_POSTS = 'harvestapi~linkedin-company-posts'

POLL_INTERVAL = 15      # seconds between status checks
MAX_POLL_ITERATIONS = 80  # 80 × 15s = 20 min max


# =============================================================================
# URL NORMALIZATION
# =============================================================================

def normalize_company_url(url):
    """Normalize LinkedIn company URL to canonical form."""
    if not url:
        return ''
    import re
    url = url.lower().strip().rstrip('/')
    if '?' in url:
        url = url.split('?')[0]
    # Normalize locale subdomains: fr.linkedin.com → www.linkedin.com
    url = re.sub(r'https?://[a-z]{2,3}\.linkedin\.com/', 'https://www.linkedin.com/', url)
    url = re.sub(r'http://(www\.)?linkedin\.com/', 'https://www.linkedin.com/', url)
    # Ensure https and www
    if url.startswith('linkedin.com'):
        url = 'https://www.' + url
    return url


# =============================================================================
# APIFY HELPERS
# =============================================================================

def start_actor_run(actor_id, input_data):
    """Start an Apify actor run and return the run_id."""
    try:
        response = requests.post(
            f'{APIFY_BASE}/acts/{actor_id}/runs',
            params={'token': APIFY_TOKEN},
            json=input_data,
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


def poll_run(run_id, label=''):
    """Poll an Apify run until completion. Returns (items, error_or_None)."""
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
            print(f"  {label} [{elapsed}s] Status: {status}")

            if status == 'SUCCEEDED':
                break
            elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                return [], f'apify_{status.lower()}'
        except Exception as e:
            print(f"  Poll error: {e}")
            continue
    else:
        return [], 'timeout'

    dataset_id = status_data.get('defaultDatasetId')
    if not dataset_id:
        return [], 'no_dataset'

    # Fetch all items (paginated)
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
            print(f"  Dataset fetch error: {e}")
            break

    return items, None


# =============================================================================
# FIELD AUDIT
# =============================================================================

def audit_fields(items, label):
    """Print all top-level field names found across items."""
    if not items:
        print(f"\n  [{label}] No items returned — cannot audit fields.")
        return

    all_keys = set()
    for item in items:
        if isinstance(item, dict):
            all_keys.update(item.keys())

    print(f"\n  [{label}] Fields found ({len(items)} items):")
    for key in sorted(all_keys):
        # Show a sample value from the first item that has it
        sample = next((item.get(key) for item in items if key in item and item.get(key) is not None), None)
        sample_str = repr(sample)
        if len(sample_str) > 80:
            sample_str = sample_str[:77] + '...'
        print(f"    {key}: {sample_str}")


# =============================================================================
# CSV LOADING
# =============================================================================

def load_urls(csv_path, limit=5):
    """Load linkedin_url (and domain) from CSV, return first N rows."""
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get('linkedin_url') or row.get('LinkedIn URL') or '').strip()
            domain = (row.get('domain') or '').strip()
            if url:
                rows.append({'linkedin_url': normalize_company_url(url), 'domain': domain})
            if len(rows) >= limit:
                break
    return rows


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Test both Apify actors on 5 companies and print field audit'
    )
    parser.add_argument('--input', required=True, help='CSV with linkedin_url column')
    parser.add_argument('--limit', type=int, default=5, help='Number of companies to test (default: 5)')
    args = parser.parse_args()

    print("=" * 70)
    print("LINKEDIN COMPANY ANALYTICS — ACTOR TEST")
    print("=" * 70)

    if not APIFY_TOKEN:
        print("Error: APIFY_TOKEN not set in .env")
        sys.exit(1)

    csv_path = Path(args.input)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    # Load URLs
    rows = load_urls(str(csv_path), limit=args.limit)
    if not rows:
        print("No LinkedIn URLs found in CSV.")
        sys.exit(1)

    urls = [r['linkedin_url'] for r in rows]
    print(f"\nTesting {len(urls)} companies:")
    for r in rows:
        print(f"  - {r['linkedin_url']}" + (f" ({r['domain']})" if r['domain'] else ''))

    # Output directory
    today = date.today().isoformat()
    output_dir = OUTPUT_DIR / f'test-{today}'
    output_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Actor 1: rigelbytes — follower count
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("ACTOR 1: rigelbytes/linkedin-company-details (follower count)")
    print(f"{'=' * 70}")
    print(f"  URLs: {len(urls)}")
    print(f"  Estimated cost: {len(urls)} × $0.01 = ${len(urls) * 0.01:.2f}")

    run_id, status = start_actor_run(ACTOR_FOLLOWERS, {
        'urls': [{'url': u} for u in urls],
        'proxyConfiguration': {
            'useApifyProxy': True,
            'apifyProxyGroups': ['RESIDENTIAL'],
        },
    })

    if not run_id:
        print(f"  Failed to start rigelbytes: {status}")
        follower_items = []
    else:
        print(f"  Run started: {run_id}")
        follower_items, err = poll_run(run_id, label='rigelbytes')
        if err:
            print(f"  rigelbytes failed: {err}")
            follower_items = []
        else:
            print(f"  rigelbytes: {len(follower_items)} items returned")
            followers_path = output_dir / 'raw_followers.json'
            with open(followers_path, 'w', encoding='utf-8') as f:
                json.dump(follower_items, f, indent=2, ensure_ascii=False)
            print(f"  Saved: {followers_path}")

    # =========================================================================
    # Actor 2: harvestapi — posts
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("ACTOR 2: harvestapi/linkedin-company-posts (post frequency)")
    print(f"{'=' * 70}")
    print(f"  URLs: {len(urls)}")
    print(f"  Period: 3 months (postedLimit='3months')")
    print(f"  Estimated cost: varies by post count × $0.002/post")

    run_id, status = start_actor_run(ACTOR_POSTS, {
        'targetUrls': urls,
        'postedLimit': '3months',
        'maxPosts': 0,
        'includeReposts': False,
        'includeQuotePosts': False,
        'scrapeReactions': False,
        'scrapeComments': False,
    })

    if not run_id:
        print(f"  Failed to start harvestapi: {status}")
        post_items = []
    else:
        print(f"  Run started: {run_id}")
        post_items, err = poll_run(run_id, label='harvestapi')
        if err:
            print(f"  harvestapi failed: {err}")
            post_items = []
        else:
            print(f"  harvestapi: {len(post_items)} items returned")
            posts_path = output_dir / 'raw_posts.json'
            with open(posts_path, 'w', encoding='utf-8') as f:
                json.dump(post_items, f, indent=2, ensure_ascii=False)
            print(f"  Saved: {posts_path}")

    # =========================================================================
    # Field Audit
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("FIELD AUDIT")
    print(f"{'=' * 70}")

    audit_fields(follower_items, 'rigelbytes/linkedin-company-details')
    audit_fields(post_items, 'harvestapi/linkedin-company-posts')

    # =========================================================================
    # Summary
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("TEST COMPLETE")
    print(f"{'=' * 70}")
    print(f"Output directory: {output_dir}")
    print()
    print("Next steps:")
    print("  1. Check raw_followers.json — find the follower count field name")
    print("  2. Check raw_posts.json — find the timestamp + engagement field names")
    print("  3. Update analyze_metrics.py with confirmed field names")
    print("  4. Run full pipeline: python scripts/run_pipeline.py --input companies.csv --source NAME")


if __name__ == '__main__':
    main()
