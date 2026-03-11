#!/usr/bin/env python3
"""
Enrich LinkedIn URLs - Find missing LinkedIn profile URLs via Apollo People Search.

For each champion without a LinkedIn URL, searches Apollo by name + email + company
to find their LinkedIn profile URL.

Input: champions_to_scrape.json (from load_champions.py)
Output: champions_to_scrape.json (updated in-place with LinkedIn URLs)

Usage:
    python enrich_linkedin_urls.py <champions_json> [--yes]
"""

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

SKILL_DIR = Path(__file__).parent.parent

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

RATE_LIMIT_DELAY = 1.0


# =============================================================================
# APOLLO API
# =============================================================================

def apollo_headers():
    return {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
    }


def apollo_request(method, endpoint, json_data=None, params=None):
    url = f'{APOLLO_API_BASE}/{endpoint}'

    if json_data is not None:
        json_data['api_key'] = APOLLO_API_KEY
    if params is not None:
        params['api_key'] = APOLLO_API_KEY

    try:
        if method == 'GET':
            response = requests.get(
                url, headers=apollo_headers(),
                params=params or {'api_key': APOLLO_API_KEY},
                timeout=30,
            )
        else:
            response = requests.post(
                url, headers=apollo_headers(),
                json=json_data, timeout=60,
            )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        body = e.response.text[:300]
        print(f"  Apollo API error ({status}): {body}")
        if status == 429:
            print("  Rate limited. Waiting 60s...")
            time.sleep(60)
            return apollo_request(method, endpoint, json_data, params)
        raise
    except Exception as e:
        print(f"  Apollo request error: {e}")
        raise


# =============================================================================
# ENRICHMENT
# =============================================================================

def find_linkedin_url(name, email, company):
    """Search Apollo for a person by name + email to get their LinkedIn URL"""
    # Try exact email match first
    try:
        data = apollo_request('POST', 'mixed_people/api_search', {
            'q_keywords': email,
            'page': 1,
            'per_page': 1,
        })
        people = data.get('people', [])
        if people:
            linkedin = people[0].get('linkedin_url', '')
            if linkedin:
                return linkedin, 'email_match'
    except Exception:
        pass

    # Fallback: search by name + company
    try:
        data = apollo_request('POST', 'mixed_people/api_search', {
            'q_keywords': f'{name} {company}',
            'page': 1,
            'per_page': 3,
        })
        people = data.get('people', [])

        # Find best match by checking name similarity
        name_lower = name.lower()
        for person in people:
            full_name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip().lower()
            if name_lower in full_name or full_name in name_lower:
                linkedin = person.get('linkedin_url', '')
                if linkedin:
                    return linkedin, 'name_match'

        # If no name match, take first result with LinkedIn
        for person in people:
            linkedin = person.get('linkedin_url', '')
            if linkedin:
                return linkedin, 'best_guess'

    except Exception as e:
        return None, f'error: {str(e)}'

    return None, 'not_found'


def enrich_all(champions):
    """Enrich LinkedIn URLs for champions missing them"""
    to_enrich = [c for c in champions if not c.get('linkedin_url')]
    already_have = len(champions) - len(to_enrich)

    if not to_enrich:
        print("\nAll champions already have LinkedIn URLs. Skipping.")
        return champions, 0, 0

    print(f"\nEnriching {len(to_enrich)} champions (skipping {already_have} with URLs)...")

    found = 0
    not_found = 0

    for i, champion in enumerate(to_enrich, 1):
        name = champion['name']
        email = champion['email']
        company = champion['company']

        print(f"  [{i}/{len(to_enrich)}] {name} ({company})")

        linkedin_url, status = find_linkedin_url(name, email, company)

        if linkedin_url:
            champion['linkedin_url'] = linkedin_url
            found += 1
            print(f"    -> found ({status})")
        else:
            not_found += 1
            print(f"    -> {status}")

        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n  Enrichment complete: {found} found, {not_found} not found")
    return champions, found, not_found


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Find missing LinkedIn URLs via Apollo People Search'
    )
    parser.add_argument('champions_json', help='Path to champions_to_scrape.json')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 1b: ENRICH LINKEDIN URLS")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    input_path = Path(args.champions_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        champions = json.load(f)

    to_enrich = sum(1 for c in champions if not c.get('linkedin_url'))
    already_have = len(champions) - to_enrich

    print(f"\nChampions: {len(champions)}")
    print(f"  With LinkedIn URL: {already_have}")
    print(f"  Need enrichment: {to_enrich}")

    if to_enrich == 0:
        print("\nAll champions have LinkedIn URLs. Skipping.")
        sys.exit(0)

    if not args.yes:
        print()
        response = input("Proceed with LinkedIn URL enrichment? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Enrich
    champions, found, not_found = enrich_all(champions)

    # Save updated file (in-place)
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(champions, f, indent=2, ensure_ascii=False)

    # Summary
    total_with_url = sum(1 for c in champions if c.get('linkedin_url'))
    total_without = len(champions) - total_with_url

    print(f"\n{'=' * 70}")
    print("ENRICHMENT COMPLETE")
    print(f"{'=' * 70}")
    print(f"Found: {found}")
    print(f"Not found: {not_found}")
    print(f"Total with LinkedIn URL: {total_with_url}/{len(champions)}")
    if total_without:
        print(f"Champions without URL ({total_without}) will be skipped in scraping step.")
    print(f"Output: {input_path}")


if __name__ == '__main__':
    main()
