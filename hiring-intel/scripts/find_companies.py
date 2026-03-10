#!/usr/bin/env python3
"""
Find Companies - Discover companies hiring for social media roles via Apollo.

Mode A (default): Search Apollo organizations with job title filters
Mode B (--list-id): Pull contacts from an existing Apollo People List,
                    extract their org IDs, then fetch job postings

Both modes:
  - Fetch job postings via Organization Job Postings API
  - Filter postings by social media keyword match
  - Check master file to skip already-processed companies
  - Output companies_with_jobs.json

Usage:
    # Mode A: org search
    python find_companies.py --source NAME [options]

    # Mode B: from Apollo People List
    python find_companies.py --source NAME --list-id LIST_ID
    python find_companies.py --source NAME --list-id list   # show available lists
"""

import json
import sys
import os
import re
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
MASTER_DIR = SKILL_DIR / 'master'
OUTPUT_DIR = SKILL_DIR / 'generated-outputs'

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

RATE_LIMIT_DELAY = 1.0

# Apollo People List IDs
MAIN_LIST_ID = '68e53b46980f6b00110bf2d2'   # Growth Squad: Companies Hiring Social Media Roles
TEST_LIST_ID = '699496644723ca0015945eff'    # Test list (use for single-company tests)

# Social media job title keywords
SM_KEYWORDS = [
    'social media manager',
    'social media coordinator',
    'community manager',
    'content manager',
    'social media strategist',
    'head of social',
    'social media specialist',
    'social media director',
    'social media lead',
]

# Apollo search keyword string (used in q_organization_job_titles)
SM_SEARCH_KEYWORDS = [
    'social media manager',
    'social media coordinator',
    'community manager',
    'social media strategist',
    'head of social media',
    'social media specialist',
]


# =============================================================================
# HELPERS
# =============================================================================

def normalize_name(name):
    if not name:
        return ''
    return re.sub(r'\s+', '', name.lower())


def normalize_source_name(source_name):
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_master_path(source_name):
    normalized = normalize_source_name(source_name)
    return MASTER_DIR / f'{normalized}_hiring_master.csv'


def load_master_domains(source_name):
    """Load already-processed company domains from master file"""
    master_path = get_master_path(source_name)
    domains = set()
    if master_path.exists():
        import csv
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get('domain', '').strip().lower()
                if domain:
                    domains.add(domain)
    return domains


def title_matches_sm(title):
    """Check if a job title matches social media keywords"""
    if not title:
        return False
    title_lower = title.lower()
    return any(kw in title_lower for kw in SM_KEYWORDS)


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
                timeout=30
            )
        else:
            response = requests.post(
                url, headers=apollo_headers(),
                json=json_data, timeout=60
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


def search_organizations(keyword, page=1, per_page=25, min_employees=None,
                         max_employees=None, geo=None):
    """Search Apollo organizations with job title filter"""
    search_params = {
        'page': page,
        'per_page': per_page,
        'q_organization_job_titles': [keyword],
    }

    if min_employees or max_employees:
        ranges = build_employee_ranges(min_employees, max_employees)
        if ranges:
            search_params['organization_num_employees_ranges'] = ranges

    if geo:
        search_params['organization_locations'] = [geo]

    return apollo_request('POST', 'mixed_companies/search', search_params)


def get_job_postings(organization_id):
    """Fetch job postings for a specific organization"""
    return apollo_request('GET', f'organizations/{organization_id}/job_postings')


def list_apollo_labels():
    """Fetch all Apollo labels (people lists and account lists)"""
    return apollo_request('GET', 'labels')


def get_label_modality(list_id):
    """Check if a label is 'contacts' (People List) or 'accounts' (Account List)"""
    data = apollo_request('GET', f'labels/{list_id}')
    return data.get('modality', 'contacts')


def search_contacts_by_list(list_id, max_pages=50):
    """
    Pull all contacts from an Apollo People List (modality=contacts).
    Returns list of contact dicts with org info.
    """
    all_contacts = []
    page = 1

    while page <= max_pages:
        data = apollo_request('POST', 'contacts/search', {
            'contact_label_ids': [list_id],
            'page': page,
            'per_page': 100,
        })

        contacts = data.get('contacts', [])
        if not contacts:
            break

        all_contacts.extend(contacts)

        pagination = data.get('pagination', {})
        total = pagination.get('total_entries', 0)
        print(f"    Page {page}: {len(contacts)} contacts (total: {total})")

        if len(all_contacts) >= total:
            break

        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_contacts


def search_accounts_by_list(list_id, max_pages=50):
    """
    Pull all accounts from an Apollo Account List (modality=accounts).
    Returns list of account dicts.
    """
    all_accounts = []
    page = 1

    while page <= max_pages:
        data = apollo_request('POST', 'accounts/search', {
            'label_ids': [list_id],
            'page': page,
            'per_page': 100,
        })

        accounts = data.get('accounts', [])
        if not accounts:
            break

        all_accounts.extend(accounts)

        pagination = data.get('pagination', {})
        total = pagination.get('total_entries', 0)
        print(f"    Page {page}: {len(accounts)} accounts (total: {total})")

        if len(all_accounts) >= total:
            break

        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_accounts


def companies_from_accounts(accounts, existing_domains):
    """
    Transform Apollo account results into company list format.
    No contacts attached — contacts will be found in Step 5.
    """
    companies = []
    for acc in accounts:
        domain = (acc.get('domain') or acc.get('primary_domain') or '').lower().strip()
        org_id = acc.get('organization_id') or acc.get('id', '')

        if not domain or not org_id:
            continue
        if domain in existing_domains:
            continue

        companies.append({
            'organization_id': org_id,
            'company_name': acc.get('name', ''),
            'domain': domain,
            'employee_count': acc.get('estimated_num_employees'),
            'industry': acc.get('industry', ''),
            'country': acc.get('country', ''),
            'city': acc.get('city', ''),
        })

    return companies


def companies_from_contacts(contacts, existing_domains):
    """
    Group contacts by organization domain, dedup, and build company list.
    Returns list of company dicts with 'contacts' array attached.
    """
    by_domain = {}

    for contact in contacts:
        org = contact.get('organization') or {}
        domain = (org.get('primary_domain') or org.get('website_url') or '').lower().strip()
        org_id = contact.get('organization_id') or org.get('id', '')

        if not domain or not org_id:
            continue

        if domain in existing_domains:
            continue

        if domain not in by_domain:
            by_domain[domain] = {
                'organization_id': org_id,
                'company_name': org.get('name', ''),
                'domain': domain,
                'employee_count': org.get('estimated_num_employees'),
                'industry': org.get('industry', ''),
                'country': org.get('country', ''),
                'city': org.get('city', ''),
                'contacts': [],
            }

        by_domain[domain]['contacts'].append({
            'contact_id': contact.get('id', ''),
            'first_name': contact.get('first_name', ''),
            'last_name': contact.get('last_name', ''),
            'title': contact.get('title', ''),
            'email': contact.get('email', ''),
        })

    return list(by_domain.values())


def build_employee_ranges(min_emp=None, max_emp=None):
    """Build Apollo employee range filters"""
    all_ranges = [
        ('1-10', 1, 10), ('11-20', 11, 20), ('21-50', 21, 50),
        ('51-100', 51, 100), ('101-200', 101, 200), ('201-500', 201, 500),
        ('501-1000', 501, 1000), ('1001-2000', 1001, 2000),
        ('2001-5000', 2001, 5000), ('5001-10000', 5001, 10000),
        ('10001+', 10001, 999999),
    ]
    result = []
    for label, lo, hi in all_ranges:
        if min_emp and hi < min_emp:
            continue
        if max_emp and lo > max_emp:
            continue
        result.append(label)
    return result


# =============================================================================
# PIPELINE
# =============================================================================

def find_companies(source, max_pages=5, min_employees=None, max_employees=None,
                   geo=None):
    """
    Search Apollo for companies hiring social media roles,
    then fetch their job posting URLs.
    """
    existing_domains = load_master_domains(source)
    print(f"  Master file: {len(existing_domains)} already-processed domains")

    all_companies = {}

    for keyword in SM_SEARCH_KEYWORDS:
        print(f"\n  Searching: \"{keyword}\"")

        for page in range(1, max_pages + 1):
            data = search_organizations(
                keyword, page=page, per_page=25,
                min_employees=min_employees, max_employees=max_employees,
                geo=geo,
            )

            organizations = data.get('organizations', [])
            pagination = data.get('pagination', {})
            total = pagination.get('total_entries', 0)

            if not organizations:
                break

            for org in organizations:
                org_id = org.get('id')
                domain = (org.get('primary_domain') or org.get('website_url') or '').lower().strip()
                name = org.get('name', '')

                if not org_id or not domain:
                    continue

                # Skip if already in master
                if domain in existing_domains:
                    continue

                # Skip if already found in this run
                if domain in all_companies:
                    continue

                all_companies[domain] = {
                    'organization_id': org_id,
                    'company_name': name,
                    'domain': domain,
                    'employee_count': org.get('estimated_num_employees'),
                    'industry': org.get('industry', ''),
                    'country': org.get('country', ''),
                    'city': org.get('city', ''),
                }

            print(f"    Page {page}: {len(organizations)} orgs (total: {total})")

            if len(organizations) < 25 or page * 25 >= total:
                break

            time.sleep(RATE_LIMIT_DELAY)

        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n  Found {len(all_companies)} unique companies (after master dedup)")
    return list(all_companies.values())


def fetch_job_urls(companies):
    """For each company, fetch job postings and filter to SM roles"""
    results = []
    total = len(companies)

    print(f"\nFetching job postings for {total} companies...")

    for i, company in enumerate(companies, 1):
        org_id = company['organization_id']
        name = company['company_name']

        try:
            data = get_job_postings(org_id)
            postings = data.get('organization_job_postings', data.get('job_postings', []))

            sm_jobs = []
            for posting in postings:
                title = posting.get('title', '')
                if title_matches_sm(title):
                    sm_jobs.append({
                        'job_id': posting.get('id', ''),
                        'title': title,
                        'url': posting.get('url', ''),
                    })

            if sm_jobs:
                company['job_postings'] = sm_jobs
                results.append(company)
                print(f"  [{i}/{total}] {name}: {len(sm_jobs)} SM job(s)")
            else:
                print(f"  [{i}/{total}] {name}: no SM jobs in postings")

        except Exception as e:
            print(f"  [{i}/{total}] {name}: error - {e}")

        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    print(f"\n  Companies with SM job postings: {len(results)}")
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Find companies hiring for social media roles via Apollo'
    )
    parser.add_argument('--source', required=True, help='Source name for this run')
    parser.add_argument('--list-id', default=MAIN_LIST_ID,
                        help='Apollo People List ID (default: main list). Use "list" to show available lists, "test" to use the test list.')
    parser.add_argument('--min-employees', type=int, default=None,
                        help='Minimum employee count')
    parser.add_argument('--max-employees', type=int, default=None,
                        help='Maximum employee count')
    parser.add_argument('--geo', default=None,
                        help='Geographic filter (e.g., "United States")')
    parser.add_argument('--max-pages', type=int, default=5,
                        help='Max pages per search keyword (default: 5)')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("HIRING INTEL - STEP 1: FIND COMPANIES")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    # Shorthand: --list-id test → use TEST_LIST_ID
    if args.list_id == 'test':
        args.list_id = TEST_LIST_ID
        print(f"Using test list: {TEST_LIST_ID}")

    # Discovery mode: list available Apollo lists
    if args.list_id == 'list':
        print("\nFetching Apollo People Lists...")
        data = list_apollo_labels()
        labels = data if isinstance(data, list) else data.get('labels', [])
        if not labels:
            print("  No lists found.")
            sys.exit(0)
        print(f"\n  Found {len(labels)} list(s):\n")
        for label in labels:
            print(f"  ID: {label.get('id')}")
            print(f"  Name: {label.get('name', 'unnamed')}")
            modality = label.get('modality', '?')
            count = label.get('cached_count', label.get('count', '?'))
            print(f"  Type: {modality} | Count: {count}")
            print()
        print("Use --list-id <ID> to pull contacts from a specific list.")
        sys.exit(0)

    # =========================================================================
    # MODE B: List-based flow
    # =========================================================================
    if args.list_id:
        # Auto-detect list type
        modality = get_label_modality(args.list_id)
        list_type = 'Account List' if modality == 'accounts' else 'People List'
        print(f"\nMode: {list_type}")
        print(f"Source: {args.source}")
        print(f"List ID: {args.list_id}")

        existing_domains = load_master_domains(args.source)
        print(f"  Master file: {len(existing_domains)} already-processed domains")

        if modality == 'accounts':
            # Account List: search accounts, no pre-loaded contacts
            print(f"\n  Fetching accounts from list {args.list_id}...")
            accounts = search_accounts_by_list(args.list_id)

            if not accounts:
                print("\nNo accounts found in list. Exiting.")
                sys.exit(0)

            print(f"\n  Total accounts pulled: {len(accounts)}")
            companies = companies_from_accounts(accounts, existing_domains)
        else:
            # People List: search contacts, group by org
            print(f"\n  Fetching contacts from list {args.list_id}...")
            contacts = search_contacts_by_list(args.list_id)

            if not contacts:
                print("\nNo contacts found in list. Exiting.")
                sys.exit(0)

            print(f"\n  Total contacts pulled: {len(contacts)}")
            companies = companies_from_contacts(contacts, existing_domains)

        print(f"  Unique companies (after master dedup): {len(companies)}")

        if not companies:
            print("\nNo new companies found. Exiting.")
            sys.exit(0)

        # Fetch job postings
        companies_with_jobs = fetch_job_urls(companies)

        if not companies_with_jobs:
            print("\nNo companies with matching social media job postings. Exiting.")
            sys.exit(0)

    # =========================================================================
    # MODE A: Org search flow (default)
    # =========================================================================
    else:
        print(f"\nMode: Organization Search")
        print(f"Source: {args.source}")
        print(f"Employee filter: {args.min_employees or 'any'} - {args.max_employees or 'any'}")
        print(f"Geo: {args.geo or 'all'}")
        print(f"Max pages per keyword: {args.max_pages}")

        companies = find_companies(
            args.source,
            max_pages=args.max_pages,
            min_employees=args.min_employees,
            max_employees=args.max_employees,
            geo=args.geo,
        )

        if not companies:
            print("\nNo new companies found. Exiting.")
            sys.exit(0)

        companies_with_jobs = fetch_job_urls(companies)

        if not companies_with_jobs:
            print("\nNo companies with matching social media job postings. Exiting.")
            sys.exit(0)

    # =========================================================================
    # COMMON: Preview + save
    # =========================================================================
    total_jobs = sum(len(c.get('job_postings', [])) for c in companies_with_jobs)
    total_contacts = sum(len(c.get('contacts', [])) for c in companies_with_jobs)

    print(f"\n{'=' * 70}")
    print("DRY RUN PREVIEW")
    print(f"{'=' * 70}")
    print(f"Companies with SM job postings: {len(companies_with_jobs)}")
    print(f"Total job postings to scrape: {total_jobs}")
    if total_contacts:
        print(f"Pre-loaded contacts: {total_contacts}")
    print(f"\nTop 10 companies:")
    for i, c in enumerate(companies_with_jobs[:10], 1):
        jobs = c.get('job_postings', [])
        titles = ', '.join(j['title'] for j in jobs[:2])
        if len(jobs) > 2:
            titles += f' +{len(jobs) - 2} more'
        contacts_info = f", {len(c.get('contacts', []))} contacts" if c.get('contacts') else ''
        print(f"  {i}. {c['company_name']} ({c.get('employee_count', '?')} emp) - {titles}{contacts_info}")
    if len(companies_with_jobs) > 10:
        print(f"  ... and {len(companies_with_jobs) - 10} more")

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Save output
    source_slug = normalize_source_name(args.source)
    today = date.today().isoformat()
    output_subdir = OUTPUT_DIR / f'{source_slug}-{today}'
    output_subdir.mkdir(parents=True, exist_ok=True)

    output_path = output_subdir / 'companies_with_jobs.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(companies_with_jobs, f, indent=2, ensure_ascii=False)

    print(f"\nOutput: {output_path}")
    print(f"Companies: {len(companies_with_jobs)}")
    print(f"Jobs to scrape: {total_jobs}")
    if total_contacts:
        print(f"Pre-loaded contacts: {total_contacts}")


if __name__ == '__main__':
    main()
