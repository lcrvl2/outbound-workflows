#!/usr/bin/env python3
"""
Scrape Profiles - Use Apify LinkedIn Profile Scraper to get profile data.

Extracts headline, current title, current company, summary, and skills.
Failed scrapes are saved to scrape_failures.csv.

Input: contacts_to_process.json
Output: profiles_scraped.json + scrape_failures.csv

Usage:
    python scrape_profiles.py <contacts_json> [--yes]
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

BATCH_SIZE = 25
POLL_INTERVAL = 5
MAX_POLL_ITERATIONS = 120


# =============================================================================
# APIFY
# =============================================================================

def run_apify_batch(linkedin_urls):
    """Run Apify LinkedIn Profile Scraper on a batch of URLs"""
    if not APIFY_TOKEN:
        return {}, 'no_apify_token'

    try:
        response = requests.post(
            f'https://api.apify.com/v2/acts/{APIFY_PROFILE_ACTOR}/runs',
            params={'token': APIFY_TOKEN},
            json={'startUrls': [{'url': url} for url in linkedin_urls]},
            timeout=30,
        )
        response.raise_for_status()
        run_data = response.json().get('data', {})
        run_id = run_data.get('id')

        if not run_id:
            return {}, 'no_run_id'

        print(f"    Apify run started: {run_id} ({len(linkedin_urls)} profiles)")

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

        dataset_id = status_data.get('defaultDatasetId')
        if not dataset_id:
            return {}, 'no_dataset'

        items_resp = requests.get(
            f'https://api.apify.com/v2/datasets/{dataset_id}/items',
            params={'token': APIFY_TOKEN},
            timeout=60,
        )
        items = items_resp.json()

        results = {}
        for item in items:
            profile_url = (
                item.get('url', '') or
                item.get('profileUrl', '') or
                item.get('linkedinUrl', '')
            )
            if profile_url:
                results[normalize_linkedin_url(profile_url)] = item

        return results, 'success'

    except Exception as e:
        print(f"    Apify error: {e}")
        return {}, f'error: {str(e)}'


def normalize_linkedin_url(url):
    if not url:
        return ''
    url = url.strip().rstrip('/')
    if '?' in url:
        url = url.split('?')[0]
    return url.lower()


# =============================================================================
# PROFILE EXTRACTION
# =============================================================================

def extract_profile_data(raw_profile):
    """Extract relevant fields from raw Apify profile response"""
    # Headline
    headline = (
        raw_profile.get('headline', '') or
        raw_profile.get('summary', '') or
        ''
    ).strip()

    # Current title and company
    experiences = (
        raw_profile.get('experience', []) or
        raw_profile.get('positions', []) or
        []
    )
    current_title = ''
    current_company = ''

    if experiences:
        current = experiences[0]
        current_title = (
            current.get('title', '') or
            current.get('position', '') or
            ''
        ).strip()
        current_company = (
            current.get('companyName', '') or
            current.get('company', '') or
            ''
        ).strip()

    # Fallback: top-level fields
    if not current_title:
        current_title = raw_profile.get('jobTitle', '') or raw_profile.get('occupation', '') or ''
    if not current_company:
        current_company = raw_profile.get('currentCompany', '') or ''

    # About/summary text
    about = (
        raw_profile.get('about', '') or
        raw_profile.get('description', '') or
        ''
    ).strip()
    # Cap to 1000 chars to avoid bloating prompts
    if len(about) > 1000:
        about = about[:1000]

    # Skills
    skills_raw = raw_profile.get('skills', []) or []
    skills = []
    for s in skills_raw[:20]:  # cap at 20
        if isinstance(s, str):
            skills.append(s.strip())
        elif isinstance(s, dict):
            name = s.get('name', '') or s.get('skill', '') or ''
            if name:
                skills.append(name.strip())

    return {
        'headline': headline,
        'current_title': current_title,
        'current_company': current_company,
        'summary': about,
        'skills': skills,
    }


# =============================================================================
# ORCHESTRATION
# =============================================================================

def scrape_all_profiles(contacts):
    """Scrape LinkedIn profiles and extract profile data"""
    to_scrape = [c for c in contacts if c.get('linkedin_url')]
    skipped_no_url = len(contacts) - len(to_scrape)

    if not to_scrape:
        print("\nNo contacts with LinkedIn URLs to scrape.")
        return [], []

    print(f"\nScraping {len(to_scrape)} LinkedIn profiles...")
    if skipped_no_url:
        print(f"  Skipping {skipped_no_url} contacts without LinkedIn URLs")

    results = []
    failures = []

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
                failures.append({**c, 'error_reason': status})
            continue

        for norm_url, contact in normalized_urls.items():
            raw = profile_data.get(norm_url)

            if not raw:
                # Fuzzy fallback by name
                first = contact.get('first_name', '').lower()
                last = contact.get('last_name', '').lower()
                if first and last:
                    for result_url, result_data in profile_data.items():
                        result_name = (
                            f"{result_data.get('firstName', '')} {result_data.get('lastName', '')}".lower()
                        )
                        if first in result_name and last in result_name:
                            raw = result_data
                            break

            if not raw:
                failures.append({**contact, 'error_reason': 'not_in_results'})
                name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                print(f"    {name or contact['linkedin_url']}: not in results")
                continue

            profile = extract_profile_data(raw)
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

            results.append({
                **contact,
                'profile': profile,
            })
            print(f"    {name or contact['linkedin_url']}: scraped ({profile['current_title'] or 'no title'})")

    return results, failures


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Scrape LinkedIn profiles to extract profile data'
    )
    parser.add_argument('contacts_json', help='Path to contacts_to_process.json')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("LINKEDIN PROFILE PERSONALIZER - STEP 2: SCRAPE PROFILES")
    print("=" * 70)

    if not APIFY_TOKEN:
        print("Error: APIFY_TOKEN not set in .env")
        sys.exit(1)

    input_path = Path(args.contacts_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        contacts = json.load(f)

    est_cost = len(contacts) * 0.004
    est_batches = (len(contacts) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\nContacts to scrape: {len(contacts)}")
    print(f"Batches: {est_batches} (batch size: {BATCH_SIZE})")
    print(f"Estimated cost: ~${est_cost:.2f}")

    if not args.yes:
        print()
        response = input("Proceed with LinkedIn profile scraping? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    results, failures = scrape_all_profiles(contacts)

    output_dir = input_path.parent
    output_path = output_dir / 'profiles_scraped.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    if failures:
        failures_path = output_dir / 'scrape_failures.csv'
        fieldnames = ['linkedin_url', 'first_name', 'last_name', 'email', 'company', 'error_reason']
        with open(failures_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(failures)
        print(f"\nFailures saved to: {failures_path}")

    failure_rate = len(failures) / len(contacts) * 100 if contacts else 0

    print(f"\n{'=' * 70}")
    print("SCRAPE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Scraped: {len(results)}/{len(contacts)} succeeded, {len(failures)} failed ({failure_rate:.0f}% failure rate)")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
