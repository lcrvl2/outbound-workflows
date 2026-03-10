#!/usr/bin/env python3
"""
Fetch TheirStack Jobs - Fetch job postings from TheirStack API with pagination.

Fetches jobs discovered since the last successful run (or N days ago for first run).
Handles pagination, rate limiting, and saves raw API response.

Input: None (reads from .env and master file for last run timestamp)
Output: jobs_raw.json in generated-outputs/{source}-{YYYY-MM-DD}/

Usage:
    python fetch_theirstack_jobs.py [--limit N] [--lookback-days N]
"""

import json
import sys
import os
import time
import argparse
import requests
import csv
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
MASTER_DIR = SKILL_DIR / 'master'
OUTPUT_DIR = SKILL_DIR / 'generated-outputs'

THEIRSTACK_API_BASE = 'https://api.theirstack.com/v1'
THEIRSTACK_API_KEY = os.getenv('THEIRSTACK_API_KEY', '')

# Social media job title keywords
JOB_TITLES = [
    'social media',
]

# Geographic filters (North America)
JOB_COUNTRIES = ['US', 'CA', 'MX']

# Technology exclusions (companies using these tools)
EXCLUDE_TECHNOLOGIES = ['agorapulse']

# Minimum employee count (applied post-fetch in transform step)
MIN_EMPLOYEE_COUNT = 200

RATE_LIMIT_DELAY = 0.5  # Seconds between pagination requests
MAX_BACKOFF_TIME = 120  # Max wait time for exponential backoff

# =============================================================================
# HELPERS
# =============================================================================

def get_source_name():
    """Auto-generate source name from current date"""
    today = datetime.now().strftime('%Y-%m-%d')
    return f'theirstack_{today}'


def get_output_dir(source):
    """Get output directory for this run"""
    return OUTPUT_DIR / source


def get_master_path(source):
    """Get path to master CSV for this source"""
    return MASTER_DIR / f'{source}_hiring_master.csv'


def get_last_run_timestamp(source):
    """Get timestamp of last successful run from master file.

    Returns ISO 8601 timestamp string. If no master file exists,
    returns timestamp from N days ago (default 7).
    """
    master_path = get_master_path(source)

    if not master_path.exists():
        # First run - use lookback period
        lookback_days = 7
        past = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        return past.isoformat()

    # Read master file and find most recent date_processed
    try:
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            dates = [row.get('date_processed', '') for row in reader]
            dates = [d for d in dates if d]  # Filter empty

            if not dates:
                # Master exists but empty - use 7 days ago
                past = datetime.now(timezone.utc) - timedelta(days=7)
                return past.isoformat()

            # Parse most recent date and add 1 second
            most_recent = max(dates)
            dt = datetime.fromisoformat(most_recent.replace('Z', '+00:00'))
            next_ts = dt + timedelta(seconds=1)
            return next_ts.isoformat()

    except Exception as e:
        print(f"Warning: Error reading master file: {e}")
        # Fallback to 7 days ago
        past = datetime.now(timezone.utc) - timedelta(days=7)
        return past.isoformat()


# =============================================================================
# THEIRSTACK API
# =============================================================================

def fetch_jobs_since(job_titles=None, max_results=10000):
    """Fetch jobs from TheirStack API with pagination.

    Args:
        job_titles: List of job title keywords to search for
        max_results: Maximum number of results to fetch

    Returns:
        List of job dictionaries from API response
    """
    if not THEIRSTACK_API_KEY:
        print("Error: THEIRSTACK_API_KEY not set in .env")
        return []

    headers = {
        'Authorization': f'Bearer {THEIRSTACK_API_KEY}',
        'Content-Type': 'application/json',
    }

    payload = {
        'posted_at_max_age_days': 7,  # Last 7 days
        'job_title_or': job_titles or JOB_TITLES,
        'job_country_code_or': JOB_COUNTRIES,
        'job_technology_slug_not': EXCLUDE_TECHNOLOGIES,
        'order_by': [{'field': 'date_posted', 'desc': True}],
        'limit': 25,  # API plan limit
        'offset': 0,
        'include_total_results': True,  # Get total count
    }

    all_jobs = []
    page = 1

    print(f"\nFetching jobs posted in last {payload['posted_at_max_age_days']} days")
    print(f"Job title keywords: {', '.join(payload['job_title_or'])}")
    print(f"Countries: {', '.join(payload['job_country_code_or'])}")
    print(f"Excluding technologies: {', '.join(payload['job_technology_slug_not'])}")

    while len(all_jobs) < max_results:
        print(f"\n  Page {page} (offset {payload['offset']})...", end=' ')

        try:
            response = requests.post(
                f'{THEIRSTACK_API_BASE}/jobs/search',
                headers=headers,
                json=payload,
                timeout=30,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                retry_after = min(retry_after, MAX_BACKOFF_TIME)
                print(f"\n  Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()

            jobs = data.get('data', [])  # API returns 'data' not 'jobs'
            metadata = data.get('metadata', {})
            total = metadata.get('total_results', 0)

            if not jobs:
                print("no more results")
                break

            all_jobs.extend(jobs)
            print(f"fetched {len(jobs)} jobs (total: {len(all_jobs)}/{total})")

            # Check if we've fetched all available
            if len(all_jobs) >= total:
                print(f"\n  Fetched all {total} available jobs")
                break

            # Next page
            payload['offset'] += 25
            page += 1

            # Proactive rate limit delay
            time.sleep(RATE_LIMIT_DELAY)

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            body = e.response.text[:500]
            print(f"\n  API error ({status}): {body}")

            if status >= 500:
                # Server error - retry with exponential backoff
                wait_time = min(2 ** (page - 1), MAX_BACKOFF_TIME)
                print(f"  Server error. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                # Client error - bail
                raise

        except Exception as e:
            print(f"\n  Request error: {e}")
            raise

    return all_jobs


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Fetch job postings from TheirStack API with pagination'
    )
    parser.add_argument('--limit', type=int, default=10000,
                        help='Maximum number of jobs to fetch (default: 10000)')
    parser.add_argument('--lookback-days', type=int, default=7,
                        help='Days to look back for first run (default: 7)')

    args = parser.parse_args()

    print("=" * 70)
    print("HIRING INTEL THEIRSTACK - STEP 0: FETCH JOBS")
    print("=" * 70)

    if not THEIRSTACK_API_KEY:
        print("\nError: THEIRSTACK_API_KEY not set in .env")
        print("Please add your TheirStack API key to the .env file")
        sys.exit(1)

    # Auto-generate source name
    source = get_source_name()
    print(f"\nSource: {source}")

    # Fetch jobs
    jobs = fetch_jobs_since(
        max_results=args.limit,
    )

    if not jobs:
        print("\nNo jobs found. Exiting.")
        sys.exit(0)

    # Save raw API response
    output_dir = get_output_dir(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / 'jobs_raw.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'=' * 70}")
    print("FETCH COMPLETE")
    print(f"{'=' * 70}")
    print(f"Jobs fetched: {len(jobs)}")
    print(f"Output: {output_path}")

    # Show sample fields from first job
    if jobs:
        print(f"\nSample job fields (first result):")
        sample = jobs[0]
        key_fields = [
            'job_title', 'company_name', 'discovered_at',
            'hiring_manager_full_name', 'job_description'
        ]
        for field in key_fields:
            value = sample.get(field, '')
            if field == 'job_description':
                value = value[:100] + '...' if len(value) > 100 else value
            print(f"  {field}: {value}")


if __name__ == '__main__':
    main()
