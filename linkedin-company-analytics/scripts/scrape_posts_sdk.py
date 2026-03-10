#!/usr/bin/env python3
"""
Scrape Posts (SDK version) — Fetch LinkedIn company posts via Apify SDK.

Uses the official apify-client SDK instead of raw requests for better reliability.

Usage:
    python scripts/scrape_posts_sdk.py --input companies.csv --output-dir PATH [--batch-size 50] [--yes]
"""

import csv
import json
import sys
import os
import argparse
from pathlib import Path
from apify_client import ApifyClient

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

APIFY_TOKEN = os.getenv('APIFY_TOKEN', '')
ACTOR_POSTS = 'harvestapi/linkedin-company-posts'

BATCH_SIZE = 50
COST_PER_POST = 0.002
POSTS_LOW_ESTIMATE = 3
POSTS_HIGH_ESTIMATE = 10


# =============================================================================
# CSV LOADING
# =============================================================================

def load_company_urls(csv_path):
    """Load LinkedIn URLs from CSV."""
    urls = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (
                row.get('linkedin_url') or
                row.get('LinkedIn URL') or
                row.get('Company Linkedin Url') or
                ''
            ).strip()
            if url:
                urls.append(url)
    return urls


# =============================================================================
# SCRAPING
# =============================================================================

def scrape_batch(client, urls, batch_num, total_batches):
    """Scrape one batch of companies using Apify SDK."""
    print(f"\n  Batch {batch_num}/{total_batches} ({len(urls)} URLs)")

    try:
        # Start the actor run
        run = client.actor(ACTOR_POSTS).call(
            run_input={
                'targetUrls': urls,
                'postedLimit': '3months',
                'maxPosts': 0,
                'includeReposts': False,
                'includeQuotePosts': False,
                'scrapeReactions': False,
                'scrapeComments': False,
            }
        )

        # Get dataset items
        items = []
        for item in client.dataset(run['defaultDatasetId']).iterate_items():
            items.append(item)

        print(f"    ✓ Got {len(items)} posts")
        return items, None

    except Exception as e:
        print(f"    ✗ Error: {str(e)}")
        return [], str(e)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='LinkedIn company posts scraper (SDK version)'
    )

    parser.add_argument('--input', required=True, help='CSV with linkedin_url column')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--batch-size', type=int, default=50, help='URLs per batch (default: 50)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')

    args = parser.parse_args()

    # Validate
    csv_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not csv_path.exists():
        print(f"Error: Input CSV not found: {csv_path}")
        sys.exit(1)

    if not APIFY_TOKEN:
        print("Error: APIFY_TOKEN not found in environment")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'raw_posts.json'

    # Load URLs
    print("Loading companies...")
    urls = load_company_urls(csv_path)
    print(f"✓ Loaded {len(urls)} companies")

    # Create batches
    batches = []
    for i in range(0, len(urls), args.batch_size):
        batches.append(urls[i:i + args.batch_size])

    print(f"\nScraping Plan:")
    print(f"  Companies: {len(urls)}")
    print(f"  Batches: {len(batches)} (batch size: {args.batch_size})")
    print(f"  Output: {output_path}")
    print(f"\nCost estimate: ${len(urls) * POSTS_LOW_ESTIMATE * COST_PER_POST:.2f}–${len(urls) * POSTS_HIGH_ESTIMATE * COST_PER_POST:.2f}")
    print(f"  ({len(urls)} companies × {POSTS_LOW_ESTIMATE}–{POSTS_HIGH_ESTIMATE} posts × ${COST_PER_POST}/post)")

    if not args.yes:
        response = input("\nProceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Initialize client
    client = ApifyClient(APIFY_TOKEN)

    # Scrape batches
    print(f"\n{'=' * 70}")
    print("SCRAPING POSTS")
    print(f"{'=' * 70}")

    all_posts = []
    errors = []

    for i, batch_urls in enumerate(batches, 1):
        posts, error = scrape_batch(client, batch_urls, i, len(batches))

        if posts:
            all_posts.extend(posts)
            # Write incrementally
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_posts, f, indent=2)
            print(f"    Incremental save: {len(all_posts)} total posts")

        if error:
            errors.append(f"Batch {i}: {error}")

    # Final output
    print(f"\n{'=' * 70}")
    print("SCRAPING COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total posts: {len(all_posts)}")
    print(f"Output: {output_path}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")

    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
