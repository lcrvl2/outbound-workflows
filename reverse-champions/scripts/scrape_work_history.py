#!/usr/bin/env python3
"""
Scrape Work History - Use Apify LinkedIn Profile Scraper to get work experience.

Extracts the last 2 previous employers (excluding current company) per champion.
Failed scrapes are saved to scrape_failures.csv for easy re-runs.

Input: champions_to_scrape.json (with LinkedIn URLs from enrich step)
Output: work_history_scraped.json + scrape_failures.csv

Usage:
    python scrape_work_history.py <champions_json> [--yes]
"""

import json
import csv
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

SKILL_DIR = Path(__file__).parent.parent

APIFY_TOKEN = os.getenv('APIFY_TOKEN', '')
APIFY_PROFILE_ACTOR = 'harvestapi/linkedin-profile-scraper'

BATCH_SIZE = 25  # Profiles per Apify run
POLL_INTERVAL = 5  # seconds
MAX_POLL_ITERATIONS = 120  # 10 min max wait

MAX_PREVIOUS_EMPLOYERS = 2  # Only keep last 2 previous employers


# =============================================================================
# APIFY
# =============================================================================

def run_apify_batch(linkedin_urls):
    """Run Apify LinkedIn Profile Scraper on a batch of URLs"""
    if not APIFY_TOKEN:
        return {}, 'no_apify_token'

    try:
        # Start actor run
        response = requests.post(
            f'https://api.apify.com/v2/acts/{APIFY_PROFILE_ACTOR}/runs',
            params={'token': APIFY_TOKEN},
            json={
                'startUrls': [{'url': url} for url in linkedin_urls],
            },
            timeout=30,
        )
        response.raise_for_status()
        run_data = response.json().get('data', {})
        run_id = run_data.get('id')

        if not run_id:
            return {}, 'no_run_id'

        print(f"    Apify run started: {run_id} ({len(linkedin_urls)} profiles)")

        # Poll for completion
        status_data = {}
        for _ in range(MAX_POLL_ITERATIONS):
            time.sleep(POLL_INTERVAL)
            status_resp = requests.get(
                f'https://api.apify.com/v2/actor-runs/{run_id}',
                params={'token': APIFY_TOKEN},
                timeout=15,
            )
            status_data = status_resp.json().get('data', {})
            status = status_data.get('status')

            if status == 'SUCCEEDED':
                break
            elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                print(f"    Apify run {status}")
                return {}, f'apify_{status.lower()}'

        # Fetch results
        dataset_id = status_data.get('defaultDatasetId')
        if not dataset_id:
            return {}, 'no_dataset'

        items_resp = requests.get(
            f'https://api.apify.com/v2/datasets/{dataset_id}/items',
            params={'token': APIFY_TOKEN},
            timeout=60,
        )
        items = items_resp.json()

        # Map results by LinkedIn URL
        results = {}
        for item in items:
            profile_url = item.get('url', '') or item.get('profileUrl', '') or item.get('linkedinUrl', '')
            if profile_url:
                # Normalize URL for matching
                normalized = normalize_linkedin_url(profile_url)
                results[normalized] = item

        return results, 'success'

    except Exception as e:
        print(f"    Apify error: {e}")
        return {}, f'error: {str(e)}'


def normalize_linkedin_url(url):
    """Normalize LinkedIn URL for consistent matching"""
    if not url:
        return ''
    url = url.rstrip('/')
    # Remove query params
    if '?' in url:
        url = url.split('?')[0]
    return url.lower()


# =============================================================================
# WORK HISTORY EXTRACTION
# =============================================================================

def extract_previous_employers(profile_data, current_company):
    """Extract the last 2 previous employers from LinkedIn profile data"""
    experiences = profile_data.get('experience', []) or profile_data.get('positions', []) or []

    if not experiences:
        return []

    # Normalize current company for comparison
    current_lower = current_company.lower().strip() if current_company else ''

    previous = []
    for exp in experiences:
        company_name = exp.get('companyName', '') or exp.get('company', '') or ''
        if not company_name:
            continue

        # Skip current company
        if current_lower and current_lower in company_name.lower():
            continue

        title = exp.get('title', '') or exp.get('position', '') or ''
        start_date = exp.get('startDate', '') or exp.get('dateRange', {}).get('start', '') or ''
        end_date = exp.get('endDate', '') or exp.get('dateRange', {}).get('end', '') or ''
        description = exp.get('description', '') or ''

        previous.append({
            'company_name': company_name.strip(),
            'title': title.strip(),
            'start_date': str(start_date),
            'end_date': str(end_date),
            'description': description[:500] if description else '',
        })

    # Take only the last N previous employers (most recent first)
    return previous[:MAX_PREVIOUS_EMPLOYERS]


# =============================================================================
# ORCHESTRATION
# =============================================================================

def scrape_all_profiles(champions):
    """Scrape LinkedIn profiles and extract work history"""
    # Filter to champions with LinkedIn URLs
    to_scrape = [c for c in champions if c.get('linkedin_url')]
    skipped_no_url = len(champions) - len(to_scrape)

    if not to_scrape:
        print("\nNo champions with LinkedIn URLs to scrape.")
        return [], []

    print(f"\nScraping {len(to_scrape)} LinkedIn profiles...")
    if skipped_no_url:
        print(f"  Skipping {skipped_no_url} champions without LinkedIn URLs")

    results = []
    failures = []

    # Process in batches
    for batch_start in range(0, len(to_scrape), BATCH_SIZE):
        batch = to_scrape[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(to_scrape) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} profiles)")

        urls = [c['linkedin_url'] for c in batch]
        normalized_urls = {normalize_linkedin_url(c['linkedin_url']): c for c in batch}

        profile_data, status = run_apify_batch(urls)

        if status != 'success':
            print(f"    Batch failed: {status}")
            for c in batch:
                failures.append({
                    'name': c['name'],
                    'email': c['email'],
                    'linkedin_url': c.get('linkedin_url', ''),
                    'error_reason': status,
                })
            continue

        # Match results back to champions
        for norm_url, champion in normalized_urls.items():
            profile = profile_data.get(norm_url)

            if not profile:
                # Try fuzzy matching by iterating all results
                for result_url, result_data in profile_data.items():
                    if champion['name'].lower() in (
                        f"{result_data.get('firstName', '')} {result_data.get('lastName', '')}".lower()
                    ):
                        profile = result_data
                        break

            if not profile:
                failures.append({
                    'name': champion['name'],
                    'email': champion['email'],
                    'linkedin_url': champion.get('linkedin_url', ''),
                    'error_reason': 'not_in_results',
                })
                print(f"    {champion['name']}: not in results")
                continue

            previous_employers = extract_previous_employers(profile, champion['company'])

            if not previous_employers:
                failures.append({
                    'name': champion['name'],
                    'email': champion['email'],
                    'linkedin_url': champion.get('linkedin_url', ''),
                    'error_reason': 'no_previous_employers',
                })
                print(f"    {champion['name']}: no previous employers found")
                continue

            results.append({
                'champion_name': champion['name'],
                'champion_email': champion['email'],
                'champion_company': champion['company'],
                'linkedin_url': champion['linkedin_url'],
                'previous_employers': previous_employers,
            })
            print(f"    {champion['name']}: {len(previous_employers)} previous employer(s)")

    # Also add champions without LinkedIn URLs as failures
    for c in champions:
        if not c.get('linkedin_url'):
            failures.append({
                'name': c['name'],
                'email': c['email'],
                'linkedin_url': '',
                'error_reason': 'no_linkedin_url',
            })

    return results, failures


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Scrape LinkedIn profiles to extract work history'
    )
    parser.add_argument('champions_json', help='Path to champions_to_scrape.json')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 2: SCRAPE WORK HISTORY")
    print("=" * 70)

    if not APIFY_TOKEN:
        print("Error: APIFY_TOKEN not set in .env")
        sys.exit(1)

    input_path = Path(args.champions_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        champions = json.load(f)

    with_url = sum(1 for c in champions if c.get('linkedin_url'))
    without_url = len(champions) - with_url
    est_cost = with_url * 0.004
    est_batches = (with_url + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\nChampions: {len(champions)}")
    print(f"  With LinkedIn URL: {with_url} (will scrape)")
    print(f"  Without LinkedIn URL: {without_url} (will skip)")
    print(f"Batches: {est_batches} (batch size: {BATCH_SIZE})")
    print(f"Estimated cost: ~${est_cost:.2f}")

    if with_url == 0:
        print("\nNo champions with LinkedIn URLs. Run enrichment step first.")
        sys.exit(1)

    if not args.yes:
        print()
        response = input("Proceed with LinkedIn profile scraping? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Scrape
    results, failures = scrape_all_profiles(champions)

    # Save results
    output_dir = input_path.parent
    output_path = output_dir / 'work_history_scraped.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Save failures CSV
    if failures:
        failures_path = output_dir / 'scrape_failures.csv'
        with open(failures_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'email', 'linkedin_url', 'error_reason'])
            writer.writeheader()
            writer.writerows(failures)
        print(f"\nFailures saved to: {failures_path}")

    # Summary
    total_employers = sum(len(r['previous_employers']) for r in results)
    failure_rate = len(failures) / len(champions) * 100 if champions else 0

    print(f"\n{'=' * 70}")
    print("SCRAPE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Scrape complete: {len(results)}/{len(champions)} succeeded, {len(failures)} failed ({failure_rate:.0f}% failure rate)")
    print(f"Total previous employers extracted: {total_employers}")
    print(f"Output: {output_path}")
    if failures:
        print(f"Failures: {output_dir / 'scrape_failures.csv'} (re-run with --csv scrape_failures.csv)")


if __name__ == '__main__':
    main()
