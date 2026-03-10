#!/usr/bin/env python3
"""
Qualify Companies - ICP filtering via Apollo native search filters.

Extracts unique companies from followers, enriches via Apollo, filters by:
- Employee count range (default: 200-2,000)
- Relevant industries (SaaS, agencies, e-commerce, media)
- Exclude competitors (from references/competitors.txt)

Uses Apollo's native filtering (NOT Claude) for simpler workflow and lower cost.

Input: followers_deduped.json (from dedupe_followers.py)
Output: companies_qualified.json

Usage:
    python qualify_companies.py <input_json> <output_json> \
        [--min-employees N] [--max-employees N]
"""

import json
import sys
import os
import time
import argparse
import requests
from pathlib import Path
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
REFERENCES_DIR = SKILL_DIR / 'references'

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

RATE_LIMIT_DELAY = 1.0

DEFAULT_MIN_EMPLOYEES = 200
DEFAULT_MAX_EMPLOYEES = 2000

# Industry keywords (used for manual filtering if Apollo doesn't provide industry filter)
RELEVANT_INDUSTRY_KEYWORDS = [
    'software', 'saas', 'technology', 'marketing', 'agency', 'advertising',
    'media', 'digital', 'ecommerce', 'e-commerce', 'retail', 'consulting',
    'services', 'internet', 'online', 'web', 'mobile', 'app', 'platform',
    'data', 'analytics', 'automation', 'enterprise', 'b2b', 'startup',
]


# =============================================================================
# COMPETITOR EXCLUSION
# =============================================================================

def load_competitor_domains():
    """Load competitor domains from references/competitors.txt"""
    competitors_path = REFERENCES_DIR / 'competitors.txt'
    domains = set()

    if not competitors_path.exists():
        return domains

    with open(competitors_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            domains.add(line.lower())

    return domains


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
# COMPANY ENRICHMENT
# =============================================================================

def enrich_company(company_name, domain=None):
    """
    Enrich company via Apollo organization search.

    Returns organization data if found, None otherwise.
    """
    search_params = {
        'page': 1,
        'per_page': 1,
    }

    # Prefer domain-based search if available
    if domain:
        search_params['q_organization_domains'] = domain
    else:
        search_params['q_organization_name'] = company_name

    try:
        data = apollo_request('POST', 'mixed_companies/search', search_params)
        organizations = data.get('organizations', [])

        if not organizations:
            return None

        org = organizations[0]
        return {
            'organization_id': org.get('id'),
            'name': org.get('name'),
            'domain': org.get('primary_domain') or org.get('website_url', '').replace('http://', '').replace('https://', '').split('/')[0],
            'employee_count': org.get('estimated_num_employees', 0),
            'industry': org.get('industry') or org.get('keywords', [''])[0],
            'country': org.get('country'),
        }

    except Exception as e:
        print(f"    Enrichment error: {e}")
        return None


# =============================================================================
# ICP FILTERING
# =============================================================================

def is_relevant_industry(industry):
    """Check if industry matches relevant keywords"""
    if not industry:
        return False

    industry_lower = industry.lower()
    return any(keyword in industry_lower for keyword in RELEVANT_INDUSTRY_KEYWORDS)


def qualify_company(company_data, min_employees, max_employees, competitor_domains):
    """
    Apply ICP filters to company.

    Filters:
    - Employee count within range
    - Relevant industry (SaaS, agencies, e-commerce, media)
    - Not a competitor
    """
    # Employee count filter
    employee_count = company_data.get('employee_count', 0)
    if not (min_employees <= employee_count <= max_employees):
        return False, f"employee_count={employee_count} (outside {min_employees}-{max_employees})"

    # Competitor exclusion
    domain = company_data.get('domain', '').lower()
    if domain in competitor_domains:
        return False, "competitor"

    # Industry filter (if available)
    industry = company_data.get('industry')
    if industry and not is_relevant_industry(industry):
        return False, f"industry={industry} (not relevant)"

    return True, "qualified"


# =============================================================================
# COMPANY EXTRACTION
# =============================================================================

def extract_companies_from_followers(followers):
    """
    Extract unique companies from follower list.

    Groups followers by company name (many followers work at same company).
    """
    companies = defaultdict(list)

    for follower in followers:
        company_name = follower.get('company', '').strip()
        if not company_name or company_name.lower() in ['', 'n/a', 'none', 'self-employed']:
            continue

        companies[company_name].append(follower)

    return companies


# =============================================================================
# ORCHESTRATION
# =============================================================================

def qualify_all_companies(followers, min_employees, max_employees):
    """Qualify companies from follower list"""
    # Load competitor exclusion list
    competitor_domains = load_competitor_domains()
    print(f"\n  Loaded {len(competitor_domains)} competitor domains for exclusion")

    # Extract unique companies
    companies_by_name = extract_companies_from_followers(followers)
    print(f"\n  Extracted {len(companies_by_name)} unique companies from followers")

    qualified = []
    stats = {
        'total_companies': len(companies_by_name),
        'enrichment_failed': 0,
        'employee_count_failed': 0,
        'competitor_excluded': 0,
        'industry_failed': 0,
        'qualified': 0,
    }

    print("\n  Enriching and qualifying companies...")

    for i, (company_name, company_followers) in enumerate(companies_by_name.items(), 1):
        if i % 50 == 0:
            print(f"    Progress: {i}/{stats['total_companies']}")

        # Enrich via Apollo
        company_data = enrich_company(company_name)

        if not company_data:
            stats['enrichment_failed'] += 1
            continue

        # Apply ICP filters
        is_qualified, reason = qualify_company(
            company_data, min_employees, max_employees, competitor_domains
        )

        if not is_qualified:
            if 'employee_count' in reason:
                stats['employee_count_failed'] += 1
            elif 'competitor' in reason:
                stats['competitor_excluded'] += 1
            elif 'industry' in reason:
                stats['industry_failed'] += 1
            continue

        # Track source competitors (which competitors these followers came from)
        source_competitors = list(set(
            f.get('source_competitor', '') for f in company_followers
        ))

        qualified.append({
            'company_name': company_data['name'],
            'domain': company_data['domain'],
            'organization_id': company_data['organization_id'],
            'employee_count': company_data['employee_count'],
            'industry': company_data['industry'],
            'country': company_data['country'],
            'follower_count': len(company_followers),
            'source_competitors': source_competitors,
        })

        stats['qualified'] += 1

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    return qualified, stats


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Qualify companies by ICP using Apollo native filters'
    )
    parser.add_argument('input_json', help='Input JSON file (followers_deduped.json)')
    parser.add_argument('output_json', help='Output JSON file (companies_qualified.json)')
    parser.add_argument(
        '--min-employees',
        type=int,
        default=DEFAULT_MIN_EMPLOYEES,
        help=f'Minimum employee count (default: {DEFAULT_MIN_EMPLOYEES})',
    )
    parser.add_argument(
        '--max-employees',
        type=int,
        default=DEFAULT_MAX_EMPLOYEES,
        help=f'Maximum employee count (default: {DEFAULT_MAX_EMPLOYEES})',
    )

    args = parser.parse_args()

    print("=" * 70)
    print("COMPANY ICP QUALIFICATION")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    # Load input
    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        followers = json.load(f)

    print(f"\nInput followers: {len(followers)}")
    print(f"ICP criteria:")
    print(f"  Employee count: {args.min_employees:,} - {args.max_employees:,}")
    print(f"  Industries: SaaS, agencies, e-commerce, media (keyword-based)")

    # Qualify companies
    qualified, stats = qualify_all_companies(followers, args.min_employees, args.max_employees)

    # Summary
    print(f"\n{'=' * 70}")
    print("QUALIFICATION RESULTS")
    print(f"{'=' * 70}")
    print(f"Total companies: {stats['total_companies']}")
    print(f"Enrichment failed: {stats['enrichment_failed']}")
    print(f"Employee count (out of range): {stats['employee_count_failed']}")
    print(f"Competitors excluded: {stats['competitor_excluded']}")
    print(f"Industry (not relevant): {stats['industry_failed']}")
    print(f"✓ Qualified companies: {stats['qualified']}")

    if stats['total_companies'] > 0:
        pass_rate = (stats['qualified'] / stats['total_companies']) * 100
        print(f"\nICP pass rate: {pass_rate:.1f}%")

    if not qualified:
        print("\n⚠️  No companies passed ICP filter.")
        print("Consider adjusting --min-employees / --max-employees")
        sys.exit(1)

    # Save output
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(qualified, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(qualified)} qualified companies to: {output_path}")


if __name__ == '__main__':
    main()
