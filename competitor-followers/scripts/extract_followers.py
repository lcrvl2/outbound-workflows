#!/usr/bin/env python3
"""
Extract Followers - Scrape LinkedIn company followers via Apify actor.

Uses: alizarin_refrigerator-owner/linkedin-company-followers-scraper
Cost: $0.02 per follower extracted
Rate: Respects LinkedIn rate limits automatically

Input: Competitor LinkedIn URLs (CLI args)
Output: followers_raw.json

Usage:
    python extract_followers.py <output_json> \\
        --competitors "URL1,URL2,URL3" \\
        [--max-followers N]
"""

import json
import sys
import os
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
APIFY_ACTOR_ID = 'alizarin_refrigerator-owner/linkedin-company-followers-scraper'
APIFY_API_BASE = 'https://api.apify.com/v2'

DEFAULT_MAX_FOLLOWERS = 5000  # Reasonable default to avoid huge costs


# =============================================================================
# APIFY API
# =============================================================================

def apify_headers():
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {APIFY_TOKEN}',
    }


def run_actor(company_urls, max_followers_per_company=None):
    """Run Apify actor to scrape LinkedIn followers"""
    url = f'{APIFY_API_BASE}/acts/{APIFY_ACTOR_ID}/runs'

    # Build actor input
    actor_input = {
        'companyUrls': company_urls,
        'maxFollowersPerCompany': max_followers_per_company or DEFAULT_MAX_FOLLOWERS,
    }

    print(f"Starting Apify actor: {APIFY_ACTOR_ID}")
    print(f"  Company URLs: {len(company_urls)}")
    print(f"  Max followers per company: {max_followers_per_company or DEFAULT_MAX_FOLLOWERS}")

    # Start actor run
    response = requests.post(
        url,
        headers=apify_headers(),
        json=actor_input,
        timeout=30,
    )
    response.raise_for_status()
    run_data = response.json()
    run_id = run_data['data']['id']

    print(f"  Actor run started: {run_id}")
    print(f"  Waiting for completion...")

    # Poll for completion
    run_url = f'{APIFY_API_BASE}/actor-runs/{run_id}'

    while True:
        time.sleep(10)  # Check every 10 seconds

        response = requests.get(run_url, headers=apify_headers(), timeout=30)
        response.raise_for_status()
        run_status = response.json()

        status = run_status['data']['status']

        if status == 'SUCCEEDED':
            print(f"  ✓ Actor run completed successfully")
            break
        elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
            print(f"  ✗ Actor run failed with status: {status}")
            sys.exit(1)
        else:
            print(f"  Status: {status}...")

    # Get dataset results
    dataset_id = run_status['data']['defaultDatasetId']
    dataset_url = f'{APIFY_API_BASE}/datasets/{dataset_id}/items'

    print(f"  Fetching results from dataset: {dataset_id}")

    response = requests.get(dataset_url, headers=apify_headers(), timeout=60)
    response.raise_for_status()
    followers = response.json()

    print(f"  ✓ Extracted {len(followers)} followers")

    return followers


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Extract LinkedIn followers from competitor pages via Apify'
    )
    parser.add_argument('output_json', help='Output JSON file path')
    parser.add_argument(
        '--competitors',
        required=True,
        help='Comma-separated LinkedIn company URLs',
    )
    parser.add_argument(
        '--max-followers',
        type=int,
        default=DEFAULT_MAX_FOLLOWERS,
        help=f'Max followers per company (default: {DEFAULT_MAX_FOLLOWERS}, 0 = unlimited)',
    )

    args = parser.parse_args()

    if not APIFY_TOKEN:
        print("Error: APIFY_TOKEN not found in environment")
        print("Set it in .env file or export APIFY_TOKEN=...")
        sys.exit(1)

    # Parse competitor URLs
    company_urls = [url.strip() for url in args.competitors.split(',') if url.strip()]

    if not company_urls:
        print("Error: No competitor URLs provided")
        sys.exit(1)

    # Validate LinkedIn URLs
    for url in company_urls:
        if 'linkedin.com/company/' not in url:
            print(f"Warning: URL may not be a LinkedIn company page: {url}")

    # Calculate estimated cost
    max_per_company = args.max_followers if args.max_followers > 0 else 10000  # Assume 10k if unlimited
    estimated_followers = len(company_urls) * max_per_company
    estimated_cost = estimated_followers * 0.02

    print("\n" + "="*60)
    print("FOLLOWER EXTRACTION - COST ESTIMATE")
    print("="*60)
    print(f"Competitors: {len(company_urls)}")
    print(f"Max followers per competitor: {args.max_followers if args.max_followers > 0 else 'UNLIMITED'}")
    print(f"Estimated total followers: {estimated_followers:,}")
    print(f"Estimated cost: ${estimated_cost:,.2f}")
    print("="*60)

    if args.max_followers == 0:
        print("\n⚠️  WARNING: No cap set (--max-followers 0)")
        print("   This could result in $1,000+ charges for popular competitors")

    confirm = input("\nProceed with extraction? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Aborted")
        sys.exit(0)

    # Run extraction
    print("\nExtracting followers...")
    followers = run_actor(company_urls, args.max_followers if args.max_followers > 0 else None)

    # Normalize follower data
    normalized = []
    for follower in followers:
        normalized.append({
            'linkedin_url': follower.get('profileUrl', ''),
            'name': follower.get('name', follower.get('fullName', '')),
            'title': follower.get('title', follower.get('headline', '')),
            'company': follower.get('company', follower.get('currentCompany', '')),
            'source_competitor': follower.get('sourceCompanyUrl', ''),
        })

    # Save output
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(normalized)} followers to: {output_path}")

    # Show cost summary
    actual_cost = len(normalized) * 0.02
    print(f"\nActual cost: ${actual_cost:.2f}")


if __name__ == '__main__':
    main()
