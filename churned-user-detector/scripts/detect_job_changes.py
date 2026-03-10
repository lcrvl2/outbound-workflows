#!/usr/bin/env python3
"""
Detect Job Changes - Enrich, scrape LinkedIn, classify, and validate emails.

Phase A: Enrich LinkedIn URLs (Apollo + Google fallback)
Phase B: Scrape LinkedIn profiles (Apify, parallelized batches)
Phase C: Classify (job_changer / still_there / went_to_competitor / no_current_role)
Phase D: Email validation for still_there (Apollo status + SMTP handshake)

Input: removed_users.json (from load_removed_users.py)
Output: job_changers.csv + in_between_jobs.csv + detection_failures.csv

Usage:
    python detect_job_changes.py <users_json> [--max-concurrent-batches 3] [--skip-email-check] [--yes]
"""

import json
import csv
import sys
import os
import re
import time
import smtplib
import argparse
import requests
from pathlib import Path

try:
    import dns.resolver
    HAS_DNS = True
except ImportError:
    HAS_DNS = False

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
REFERENCES_DIR = SKILL_DIR / 'references'

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

APIFY_TOKEN = os.getenv('APIFY_TOKEN', '')
APIFY_PROFILE_ACTOR = 'harvestapi~linkedin-profile-scraper'

DATAFORSEO_USERNAME = os.getenv('DATAFORSEO_USERNAME', '')
DATAFORSEO_PASSWORD = os.getenv('DATAFORSEO_PASSWORD', '')

RATE_LIMIT_DELAY = 1.0
BATCH_SIZE = 25
POLL_INTERVAL = 5
MAX_POLL_ITERATIONS = 120

# Catch-all domains where SMTP check is unreliable
CATCHALL_DOMAINS = {
    'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com',
    'live.com', 'yahoo.com', 'yahoo.fr', 'aol.com', 'icloud.com',
    'me.com', 'protonmail.com', 'proton.me',
}


# =============================================================================
# COMPETITOR LIST
# =============================================================================

def load_competitors():
    """Load competitor names from competitors.txt (domain format)"""
    competitors = set()
    path = REFERENCES_DIR / 'competitors.txt'
    if not path.exists():
        print(f"  Warning: competitors.txt not found at {path}")
        return competitors
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract company name from domain (e.g., "hootsuite.com" -> "hootsuite")
                name = line.split('.')[0].lower()
                competitors.add(name)
    return competitors

COMPETITORS = load_competitors()


# =============================================================================
# COMPANY NAME MATCHING
# =============================================================================

def normalize_company(name):
    """Normalize company name for fuzzy comparison"""
    if not name:
        return ''
    name = name.lower().strip()
    for suffix in ['inc', 'inc.', 'corp', 'corp.', 'corporation', 'ltd', 'ltd.',
                   'llc', 'gmbh', 'sarl', 'sas', 'sa', 'ag', 'co', 'co.',
                   'group', 'holdings', 'plc', 'limited', 'the']:
        name = re.sub(r'\b' + re.escape(suffix) + r'\.?\b', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name.strip()


def is_same_company(a, b):
    """Check if two company names refer to the same company"""
    a, b = normalize_company(a), normalize_company(b)
    if not a or not b:
        return False
    return a in b or b in a


def is_competitor(company_name):
    """Check if a company is in the competitor list"""
    normalized = normalize_company(company_name)
    if not normalized:
        return False
    for comp in COMPETITORS:
        if comp in normalized or normalized in comp:
            return True
    return False


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
# PHASE A: ENRICH LINKEDIN URLS
# =============================================================================

def _split_name(name):
    """Split a full name into first and last name."""
    parts = name.strip().split()
    if len(parts) >= 2:
        return parts[0], ' '.join(parts[1:])
    return name, ''


def _domain_from_email(email):
    """Extract clean company name from email domain (e.g. sophie.colin@septeo.com → septeo)."""
    domain = email.split('@')[1] if '@' in email else ''
    # Skip personal email domains
    personal = {'gmail.com', 'yahoo.com', 'yahoo.fr', 'hotmail.com', 'outlook.com',
                'live.com', 'aol.com', 'icloud.com', 'me.com', 'protonmail.com', 'proton.me'}
    if domain.lower() in personal:
        return None
    return domain.split('.')[0].lower() if domain else None


def find_linkedin_via_apollo(name, email, company):
    """Search Apollo for LinkedIn URL + email status. Returns (url, email_status, match_type)."""
    # Tier 1: people/match by email (direct enrichment — most reliable)
    try:
        data = apollo_request('POST', 'people/match', {
            'email': email,
        })
        person = data.get('person')
        if person:
            linkedin = person.get('linkedin_url', '')
            email_status = person.get('email_status', '')
            if linkedin:
                return linkedin, email_status, 'email_match'
            # Got person but no LinkedIn — still capture email_status
            if email_status:
                return None, email_status, 'no_linkedin'
    except Exception:
        pass

    time.sleep(RATE_LIMIT_DELAY)

    # Tier 2: people/match by name + company (for email misses)
    # api_search doesn't return linkedin_url on free tier, so use people/match instead
    try:
        first_name, last_name = _split_name(name)
        # Try with email domain as org if different from company name
        domain = _domain_from_email(email)
        organization_name = company

        data = apollo_request('POST', 'people/match', {
            'first_name': first_name,
            'last_name': last_name,
            'organization_name': organization_name,
        })
        person = data.get('person')
        if person:
            linkedin = person.get('linkedin_url', '')
            if linkedin:
                return linkedin, person.get('email_status', ''), 'name_match'
    except Exception:
        pass

    # Tier 2b: try with email domain as org name (handles parent company emails)
    if domain and normalize_company(domain) != normalize_company(company):
        time.sleep(RATE_LIMIT_DELAY)
        try:
            first_name, last_name = _split_name(name)
            data = apollo_request('POST', 'people/match', {
                'first_name': first_name,
                'last_name': last_name,
                'domain': email.split('@')[1],
            })
            person = data.get('person')
            if person:
                linkedin = person.get('linkedin_url', '')
                if linkedin:
                    return linkedin, person.get('email_status', ''), 'domain_match'
        except Exception:
            pass

    return None, None, 'not_found'


def _strip_accents(text):
    """Remove accents from text for search queries."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _google_search_linkedin(query):
    """Run a Google search via DataForSEO SERP API (synchronous) and return first linkedin.com/in/ URL."""
    if not DATAFORSEO_USERNAME or not DATAFORSEO_PASSWORD:
        return None

    try:
        response = requests.post(
            'https://api.dataforseo.com/v3/serp/google/organic/live/advanced',
            auth=(DATAFORSEO_USERNAME, DATAFORSEO_PASSWORD),
            json=[{
                'keyword': query,
                'location_code': 2840,  # United States
                'language_code': 'en',
                'device': 'desktop',
                'depth': 10,
            }],
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        tasks = data.get('tasks', [])
        if not tasks or tasks[0].get('status_code') != 20000:
            return None

        results = tasks[0].get('result', [])
        if not results:
            return None

        for item in results[0].get('items', []):
            if item.get('type') != 'organic':
                continue
            url = item.get('url', '')
            if 'linkedin.com/in/' in url:
                return url

    except Exception as e:
        print(f"    DataForSEO search error: {e}")

    return None


def find_linkedin_via_google(name, company, email=''):
    """Fallback: Google search site:linkedin.com/in with multiple query strategies (DataForSEO)."""
    if not DATAFORSEO_USERNAME:
        return None

    clean_name = _strip_accents(name)

    # Strategy 1: name + company
    url = _google_search_linkedin(f'site:linkedin.com/in "{clean_name}" "{company}"')
    if url:
        return url

    # Strategy 2: name + email domain (handles parent company domains)
    domain_name = _domain_from_email(email)
    if domain_name and normalize_company(domain_name) != normalize_company(company):
        url = _google_search_linkedin(f'site:linkedin.com/in "{clean_name}" "{domain_name}"')
        if url:
            return url

    # Strategy 3: name only (last resort, higher false positive risk)
    url = _google_search_linkedin(f'site:linkedin.com/in "{clean_name}"')
    if url:
        return url

    return None


def enrich_all_users(users):
    """Phase A: Enrich LinkedIn URLs for all users via Apollo + Google fallback."""
    print(f"\n{'=' * 70}")
    print("PHASE A: ENRICH LINKEDIN URLS")
    print(f"{'=' * 70}")

    total = len(users)
    found_apollo = 0
    found_google = 0
    not_found = 0

    for i, user in enumerate(users, 1):
        name = user['name']
        email = user['email']
        company = user['old_company']

        print(f"  [{i}/{total}] {name} ({company})")

        # Apollo enrichment
        linkedin, email_status, match_type = find_linkedin_via_apollo(name, email, company)
        user['apollo_email_status'] = email_status or ''

        if linkedin:
            user['linkedin_url'] = linkedin
            user['linkedin_source'] = 'apollo'
            found_apollo += 1
            print(f"    -> Apollo: {match_type}")
            time.sleep(RATE_LIMIT_DELAY)
            continue

        time.sleep(RATE_LIMIT_DELAY)

        # Google fallback
        linkedin = find_linkedin_via_google(name, company, email)
        if linkedin:
            user['linkedin_url'] = linkedin
            user['linkedin_source'] = 'google'
            found_google += 1
            print(f"    -> Google fallback")
        else:
            not_found += 1
            print(f"    -> not found")

    print(f"\n  Phase A complete:")
    print(f"    Apollo: {found_apollo}")
    print(f"    Google: {found_google}")
    print(f"    Not found: {not_found}")

    return users


# =============================================================================
# PHASE B: SCRAPE LINKEDIN PROFILES (APIFY)
# =============================================================================

def normalize_linkedin_url(url):
    """Normalize LinkedIn URL for consistent matching.
    Handles locale subdomains (fr.linkedin.com, de.linkedin.com, etc.)
    by stripping them to a canonical linkedin.com/in/slug form.
    Also strips trailing locale suffixes like /en, /fr from the path."""
    if not url:
        return ''
    url = url.lower().strip()
    url = url.rstrip('/')
    if '?' in url:
        url = url.split('?')[0]
    # Normalize locale subdomains: fr.linkedin.com → www.linkedin.com
    url = re.sub(r'https?://[a-z]{2,3}\.linkedin\.com/', 'https://www.linkedin.com/', url)
    # Also normalize http → https and missing www
    url = re.sub(r'http://(www\.)?linkedin\.com/', 'https://www.linkedin.com/', url)
    # Strip trailing locale suffixes from path (e.g. /in/slug/en → /in/slug)
    url = re.sub(r'/in/([^/]+)/[a-z]{2}$', r'/in/\1', url)
    return url


def run_apify_batch(linkedin_urls):
    """Run Apify LinkedIn Profile Scraper on a batch of URLs."""
    if not APIFY_TOKEN:
        return {}, 'no_apify_token'

    try:
        response = requests.post(
            f'https://api.apify.com/v2/acts/{APIFY_PROFILE_ACTOR}/runs',
            params={'token': APIFY_TOKEN},
            json={
                'profileScraperMode': 'Profile details no email ($4 per 1k)',
                'queries': linkedin_urls,
            },
            timeout=30,
        )
        response.raise_for_status()
        run_data = response.json().get('data', {})
        run_id = run_data.get('id')

        if not run_id:
            return {}, 'no_run_id'

        return run_id, 'started'

    except Exception as e:
        return {}, f'error: {str(e)}'


def poll_apify_run(run_id):
    """Poll an Apify run until completion, return results dict keyed by normalized URL."""
    status_data = {}
    for _ in range(MAX_POLL_ITERATIONS):
        time.sleep(POLL_INTERVAL)
        try:
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
                return {}, f'apify_{status.lower()}'
        except Exception:
            continue

    dataset_id = status_data.get('defaultDatasetId')
    if not dataset_id:
        return {}, 'no_dataset'

    try:
        items_resp = requests.get(
            f'https://api.apify.com/v2/datasets/{dataset_id}/items',
            params={'token': APIFY_TOKEN},
            timeout=60,
        )
        items = items_resp.json()
    except Exception as e:
        return {}, f'fetch_error: {str(e)}'

    results = {}
    for item in items:
        profile_url = item.get('url', '') or item.get('profileUrl', '') or item.get('linkedinUrl', '')
        if profile_url:
            normalized = normalize_linkedin_url(profile_url)
            results[normalized] = item

    return results, 'success'


def scrape_all_profiles(users, max_concurrent=3):
    """Phase B: Scrape LinkedIn profiles with parallel Apify batches."""
    print(f"\n{'=' * 70}")
    print("PHASE B: SCRAPE LINKEDIN PROFILES")
    print(f"{'=' * 70}")

    to_scrape = [u for u in users if u.get('linkedin_url')]
    skipped = len(users) - len(to_scrape)

    if not to_scrape:
        print("\n  No users with LinkedIn URLs to scrape.")
        return {}

    print(f"\n  Profiles to scrape: {len(to_scrape)}")
    if skipped:
        print(f"  Skipping {skipped} users without LinkedIn URLs")

    est_cost = len(to_scrape) * 0.004
    total_batches = (len(to_scrape) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  Batches: {total_batches} (size {BATCH_SIZE}, max concurrent {max_concurrent})")
    print(f"  Estimated cost: ~${est_cost:.2f}")

    # Build batches — normalize URLs before sending to Apify so locale
    # subdomains (fr.linkedin.com) and trailing locale suffixes (/en) are
    # resolved to canonical form. This ensures scraper results match our lookup keys.
    batches = []
    for start in range(0, len(to_scrape), BATCH_SIZE):
        batch = to_scrape[start:start + BATCH_SIZE]
        urls = [normalize_linkedin_url(u['linkedin_url']) for u in batch]
        batches.append(urls)

    # Launch batches with concurrency control
    all_profiles = {}
    batch_idx = 0

    while batch_idx < len(batches):
        # Launch up to max_concurrent batches
        active_runs = {}
        launch_count = min(max_concurrent, len(batches) - batch_idx)

        for _ in range(launch_count):
            urls = batches[batch_idx]
            batch_num = batch_idx + 1
            print(f"\n  Launching batch {batch_num}/{len(batches)} ({len(urls)} profiles)")

            run_id, status = run_apify_batch(urls)
            if status == 'started':
                active_runs[run_id] = batch_num
            else:
                print(f"    Batch {batch_num} failed to start: {status}")

            batch_idx += 1

        # Poll all active runs
        for run_id, batch_num in active_runs.items():
            print(f"  Polling batch {batch_num} (run {run_id})...")
            results, status = poll_apify_run(run_id)
            if status == 'success':
                all_profiles.update(results)
                print(f"    Batch {batch_num}: {len(results)} profiles scraped")
            else:
                print(f"    Batch {batch_num} failed: {status}")

    print(f"\n  Phase B complete: {len(all_profiles)} profiles scraped")
    return all_profiles


# =============================================================================
# PHASE C: CLASSIFY
# =============================================================================

def extract_current_position(profile_data):
    """Extract the current position (no end date / 'present') from a LinkedIn profile."""
    experiences = profile_data.get('experience', []) or profile_data.get('positions', []) or []

    for exp in experiences:
        end = exp.get('endDate', '') or ''
        # Also check nested dateRange
        if not end:
            date_range = exp.get('dateRange', {})
            if isinstance(date_range, dict):
                end = date_range.get('end', '')

        if not end or 'present' in str(end).lower():
            return {
                'company_name': (exp.get('companyName', '') or exp.get('company', '')).strip(),
                'title': (exp.get('title', '') or exp.get('position', '')).strip(),
                'start_date': str(exp.get('startDate', '') or ''),
            }

    return None


def verify_profile_has_old_company(profile_data, old_company):
    """Check if any experience entry matches the old company name.
    Returns True if old_company found in experience history (= right profile)."""
    experiences = profile_data.get('experience', []) or profile_data.get('positions', []) or []
    for exp in experiences:
        company = (exp.get('companyName', '') or exp.get('company', '')).strip()
        if is_same_company(company, old_company):
            return True
    return False


def classify_user(user, profile_data):
    """
    Classify a user based on their LinkedIn profile vs old company.
    Returns: (classification, details_dict)
    """
    # For Google-sourced profiles, verify this is the right person by checking
    # that old_company appears somewhere in their LinkedIn experience history.
    # Apollo email_match profiles are inherently correct (matched by email).
    if user.get('linkedin_source') == 'google':
        if not verify_profile_has_old_company(profile_data, user['old_company']):
            return 'wrong_profile', {'failure_reason': 'old_company_not_in_experience'}

    current = extract_current_position(profile_data)

    if not current or not current['company_name']:
        return 'no_current_role', {'reason': 'no current position found on LinkedIn'}

    new_company = current['company_name']
    old_company = user['old_company']

    if is_same_company(new_company, old_company):
        return 'still_there', {
            'current_company': new_company,
            'current_title': current['title'],
        }

    if is_competitor(new_company):
        return 'went_to_competitor', {
            'new_company': new_company,
            'new_title': current['title'],
        }

    return 'job_changer', {
        'new_company': new_company,
        'new_title': current['title'],
        'start_date': current.get('start_date', ''),
    }


def classify_all_users(users, profiles):
    """Phase C: Classify all users based on scraped LinkedIn data."""
    print(f"\n{'=' * 70}")
    print("PHASE C: CLASSIFY USERS")
    print(f"{'=' * 70}")

    results = {
        'job_changer': [],
        'still_there': [],
        'went_to_competitor': [],
        'no_current_role': [],
        'no_profile': [],
        'wrong_profile': [],
    }

    for user in users:
        linkedin = user.get('linkedin_url')
        if not linkedin:
            results['no_profile'].append({**user, 'failure_reason': 'no_linkedin_url'})
            continue

        normalized = normalize_linkedin_url(linkedin)
        profile = profiles.get(normalized)

        if not profile:
            # Try fuzzy match by name
            for result_url, result_data in profiles.items():
                name_lower = user['name'].lower()
                profile_name = f"{result_data.get('firstName', '')} {result_data.get('lastName', '')}".strip().lower()
                if name_lower in profile_name or profile_name in name_lower:
                    profile = result_data
                    break

        if not profile:
            results['no_profile'].append({**user, 'failure_reason': 'not_in_scrape_results'})
            continue

        classification, details = classify_user(user, profile)
        results[classification].append({**user, **details})

    # Stats
    print(f"\n  Classification results:")
    print(f"    Job changers: {len(results['job_changer'])}")
    print(f"    Still there: {len(results['still_there'])}")
    print(f"    Went to competitor: {len(results['went_to_competitor'])}")
    print(f"    No current role: {len(results['no_current_role'])}")
    print(f"    Wrong profile: {len(results['wrong_profile'])}")
    print(f"    No profile data: {len(results['no_profile'])}")

    return results


# =============================================================================
# PHASE D: EMAIL VALIDATION
# =============================================================================

def verify_email_smtp(email):
    """SMTP handshake to check if mailbox exists. Returns True/False/None (inconclusive)."""
    if not HAS_DNS:
        return None

    domain = email.split('@')[1]

    # Skip personal email domains — SMTP check is unreliable for these
    personal_domains = {'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.fr',
                        'hotmail.com', 'outlook.com', 'live.com', 'aol.com',
                        'icloud.com', 'me.com', 'protonmail.com', 'proton.me'}
    if domain.lower() in CATCHALL_DOMAINS or domain.lower() in personal_domains:
        return None  # Catch-all or personal, unreliable

    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_host = str(mx_records[0].exchange).rstrip('.')

        with smtplib.SMTP(mx_host, timeout=10) as smtp:
            smtp.helo('verify.local')
            smtp.mail('test@verify.local')
            code, _ = smtp.rcpt(email)
            return code == 250

    except Exception:
        return None  # Inconclusive


def validate_still_there_emails(still_there_users):
    """
    Phase D: For 'still_there' users, check if their email is actually dead.
    If Apollo says bounced/unavailable OR SMTP says mailbox gone → in_between_jobs.
    """
    print(f"\n{'=' * 70}")
    print("PHASE D: EMAIL VALIDATION (still_there users)")
    print(f"{'=' * 70}")

    if not still_there_users:
        print("\n  No still_there users to validate.")
        return [], still_there_users

    print(f"\n  Checking {len(still_there_users)} emails...")

    truly_still_there = []
    in_between_jobs = []

    for i, user in enumerate(still_there_users, 1):
        email = user['email']
        apollo_status = user.get('apollo_email_status', '')

        print(f"  [{i}/{len(still_there_users)}] {email}", end='')

        # Check 1: Apollo email status
        if apollo_status in ('unavailable', 'bounced'):
            print(f" -> Apollo: {apollo_status} → in_between_jobs")
            in_between_jobs.append({**user, 'email_status': f'apollo_{apollo_status}'})
            continue

        # Check 2: SMTP handshake
        smtp_result = verify_email_smtp(email)
        if smtp_result is False:
            print(f" -> SMTP: mailbox gone → in_between_jobs")
            in_between_jobs.append({**user, 'email_status': 'smtp_bounced'})
            continue

        if smtp_result is None:
            status_note = 'inconclusive'
        else:
            status_note = 'valid'

        print(f" -> {status_note}")
        truly_still_there.append(user)

    print(f"\n  Phase D complete:")
    print(f"    Still there (confirmed): {len(truly_still_there)}")
    print(f"    In between jobs: {len(in_between_jobs)}")

    return in_between_jobs, truly_still_there


# =============================================================================
# MASTER FILE
# =============================================================================

def update_master(source, users):
    """Append processed emails to master file for dedup on future runs."""
    import re
    normalized = re.sub(r'[^\w\s-]', '', source.lower())
    normalized = re.sub(r'\s+', '_', normalized)

    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    master_path = MASTER_DIR / f'{normalized}_removed_users_master.csv'

    existing_emails = set()
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_emails.add(row.get('email', '').strip().lower())

    new_rows = [u for u in users if u['email'] not in existing_emails]

    if not new_rows:
        return

    write_header = not master_path.exists()
    with open(master_path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['email', 'name', 'old_company', 'processed_date'])
        if write_header:
            writer.writeheader()
        from datetime import date
        today = date.today().isoformat()
        for u in new_rows:
            writer.writerow({
                'email': u['email'],
                'name': u['name'],
                'old_company': u['old_company'],
                'processed_date': today,
            })


# =============================================================================
# OUTPUT
# =============================================================================

# =============================================================================
# TITLE RELEVANCE FILTER
# =============================================================================

# Keywords indicating a role that would use a social media management tool
RELEVANT_TITLE_KEYWORDS = [
    'social media', 'community manager', 'content', 'marketing',
    'communication', 'digital', 'brand', 'growth', 'media manager',
    'creative', 'advertising', 'pr ', 'public relation', 'relations publiques',
    'community', 'engagement', 'influence', 'strateg',
    # French equivalents
    'chargé', 'chargée', 'responsable', 'directeur', 'directrice',
    'chef de projet', 'coordinat',
    # Catch-all leadership roles that likely manage social
    'cmo', 'vp market', 'head of market', 'head of comm', 'head of digital',
    'founder', 'co-founder', 'ceo', 'owner', 'director',
]

# Keywords that explicitly disqualify a title (even if other keywords match)
DISQUALIFYING_KEYWORDS = [
    'bank teller', 'psycholog', 'house wife', 'store host', 'recepti',
    'praktikant am empfang', 'gardiennage', 'security', 'procurement',
    'product lifecycle', 'senior associate', 'talent acquisition',
    'developer advocate', 'senior developer',
]


def is_relevant_title(title):
    """Check if a job title suggests the person would use a social media tool.
    Returns True if qualified, False if unqualified."""
    if not title:
        return False
    title_lower = title.lower()
    # Check disqualifying keywords first
    for kw in DISQUALIFYING_KEYWORDS:
        if kw in title_lower:
            return False
    # Check for relevant keywords
    for kw in RELEVANT_TITLE_KEYWORDS:
        if kw in title_lower:
            return True
    return False


def split_qualified_job_changers(job_changers):
    """Split job changers into qualified (relevant title) and unqualified."""
    qualified = []
    unqualified = []
    for u in job_changers:
        if is_relevant_title(u.get('new_title', '')):
            qualified.append(u)
        else:
            unqualified.append(u)
    return qualified, unqualified


def write_job_changers_csv(job_changers, output_path):
    """Write BDR-ready job_changers.csv"""
    fieldnames = ['name', 'email', 'old_company', 'new_company', 'new_title',
                  'linkedin_url', 'mrr', 'country', 'plan']
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for u in job_changers:
            writer.writerow({
                'name': u.get('name', ''),
                'email': u.get('email', ''),
                'old_company': u.get('old_company', ''),
                'new_company': u.get('new_company', ''),
                'new_title': u.get('new_title', ''),
                'linkedin_url': u.get('linkedin_url', ''),
                'mrr': u.get('mrr', ''),
                'country': u.get('country', ''),
                'plan': u.get('plan', ''),
            })


def write_in_between_csv(in_between, output_path):
    """Write in_between_jobs.csv"""
    fieldnames = ['name', 'email', 'old_company', 'linkedin_url', 'mrr',
                  'country', 'plan', 'email_status']
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for u in in_between:
            writer.writerow({
                'name': u.get('name', ''),
                'email': u.get('email', ''),
                'old_company': u.get('old_company', ''),
                'linkedin_url': u.get('linkedin_url', ''),
                'mrr': u.get('mrr', ''),
                'country': u.get('country', ''),
                'plan': u.get('plan', ''),
                'email_status': u.get('email_status', ''),
            })


def write_failures_csv(failures, output_path):
    """Write detection_failures.csv"""
    fieldnames = ['name', 'email', 'old_company', 'linkedin_url', 'failure_reason']
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for u in failures:
            writer.writerow({
                'name': u.get('name', ''),
                'email': u.get('email', ''),
                'old_company': u.get('old_company', ''),
                'linkedin_url': u.get('linkedin_url', ''),
                'failure_reason': u.get('failure_reason', u.get('reason', '')),
            })


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Detect job changes via LinkedIn scraping + email validation'
    )
    parser.add_argument('users_json', help='Path to removed_users.json')
    parser.add_argument('--source', default=None,
                        help='Source name for master tracking (auto-detected from filename if omitted)')
    parser.add_argument('--max-concurrent-batches', type=int, default=3,
                        help='Max parallel Apify batches (default: 3)')
    parser.add_argument('--skip-email-check', action='store_true',
                        help='Skip SMTP email validation (Phase D)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("CHURNED USER DETECTOR - STEP 2: DETECT JOB CHANGES")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    if not APIFY_TOKEN:
        print("Error: APIFY_TOKEN not set in .env")
        sys.exit(1)

    if not DATAFORSEO_USERNAME:
        print("Warning: DATAFORSEO_USERNAME not set. Google fallback will be disabled.")

    input_path = Path(args.users_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        users = json.load(f)

    est_cost = len(users) * 0.004
    print(f"\nUsers to process: {len(users)}")
    print(f"Max concurrent batches: {args.max_concurrent_batches}")
    print(f"Google fallback: {'DataForSEO' if DATAFORSEO_USERNAME else 'disabled'}")
    print(f"Email validation: {'disabled' if args.skip_email_check else 'enabled (Apollo + SMTP)'}")
    if not HAS_DNS and not args.skip_email_check:
        print("  Warning: dnspython not installed. SMTP check will be skipped.")
        print("  Install with: pip install dnspython")
    print(f"Estimated Apify cost: ~${est_cost:.2f}")
    print(f"Competitors loaded: {len(COMPETITORS)}")

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # ===== PHASE A: Enrich LinkedIn URLs =====
    users = enrich_all_users(users)

    # ===== PHASE B: Scrape LinkedIn profiles =====
    profiles = scrape_all_profiles(users, max_concurrent=args.max_concurrent_batches)

    # ===== PHASE C: Classify =====
    results = classify_all_users(users, profiles)

    # ===== PHASE D: Email validation =====
    in_between_jobs = []
    if not args.skip_email_check and results['still_there']:
        new_in_between, results['still_there'] = validate_still_there_emails(results['still_there'])
        in_between_jobs.extend(new_in_between)

    # Also add no_current_role to in_between (they likely left but haven't updated LinkedIn)
    for u in results['no_current_role']:
        in_between_jobs.append({**u, 'email_status': 'no_current_linkedin_role'})

    # ===== OUTPUT =====
    output_dir = input_path.parent

    # Split job changers by title relevance
    qualified, unqualified = split_qualified_job_changers(results['job_changer'])

    # Qualified job changers CSV (BDR-ready)
    job_changers_path = output_dir / 'job_changers.csv'
    write_job_changers_csv(qualified, job_changers_path)

    # Unqualified job changers CSV (for review)
    if unqualified:
        unqualified_path = output_dir / 'job_changers_unqualified.csv'
        write_job_changers_csv(unqualified, unqualified_path)

    # In-between jobs CSV
    in_between_path = output_dir / 'in_between_jobs.csv'
    write_in_between_csv(in_between_jobs, in_between_path)

    # Failures CSV
    failures = results['no_profile'] + results['wrong_profile'] + results['went_to_competitor']
    # Tag competitors with reason
    for u in results['went_to_competitor']:
        u['failure_reason'] = f"went_to_competitor: {u.get('new_company', '')}"
    failures_path = output_dir / 'detection_failures.csv'
    write_failures_csv(failures, failures_path)

    # Update master
    source = args.source
    if not source:
        # Try to extract from parent dir name
        source = input_path.parent.name or 'unknown'
    update_master(source, users)

    # ===== SUMMARY =====
    total = len(users)
    print(f"\n{'=' * 70}")
    print("DETECTION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total processed: {total}")
    print(f"  Job changers (qualified): {len(qualified)} -> {job_changers_path}")
    if unqualified:
        print(f"  Job changers (unqualified): {len(unqualified)} -> {output_dir / 'job_changers_unqualified.csv'}")
    print(f"  In between jobs: {len(in_between_jobs)} -> {in_between_path}")
    print(f"  Still at company: {len(results['still_there'])} (ignored)")
    print(f"  Went to competitor: {len(results['went_to_competitor'])} (excluded)")
    print(f"  Wrong profile: {len(results['wrong_profile'])} (excluded)")
    print(f"  No profile data: {len(results['no_profile'])} (failures)")
    print(f"Failures: {failures_path}")
    print(f"Master updated: {MASTER_DIR}")


if __name__ == '__main__':
    main()
