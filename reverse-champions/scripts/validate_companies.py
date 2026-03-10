#!/usr/bin/env python3
"""
Validate Companies - Check target companies against ICP, exclude competitors & customers.

For each target company (previous employer of a champion):
1. Apollo Org Search to enrich company data
2. ICP check: employee count, geography
3. Competitor exclusion: domain in competitors.txt
4. Customer check: Apollo account stage/label
5. Group by target company: merge all champions who worked there

Input: roles_filtered.json (from filter_roles.py)
Output: companies_validated.json

Usage:
    python validate_companies.py <roles_json> [--min-employees N] [--max-employees N] [--geo GEO] [--yes]
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
# COMPETITOR EXCLUSION
# =============================================================================

def load_competitors():
    """Load competitor domains from competitors.txt"""
    competitors_path = SKILL_DIR / 'references' / 'competitors.txt'
    domains = set()
    if competitors_path.exists():
        with open(competitors_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith('#'):
                    domains.add(line)
    return domains


# =============================================================================
# COMPANY VALIDATION
# =============================================================================

def search_company(company_name):
    """Search Apollo for a company by name and return enriched data"""
    try:
        data = apollo_request('POST', 'mixed_companies/search', {
            'q_organization_name': company_name,
            'page': 1,
            'per_page': 3,
        })
        organizations = data.get('organizations', [])

        if not organizations:
            return None

        # Find best match
        name_lower = company_name.lower()
        for org in organizations:
            org_name = (org.get('name') or '').lower()
            if name_lower in org_name or org_name in name_lower:
                return org

        # Fallback to first result
        return organizations[0]

    except Exception as e:
        print(f"    Search error: {e}")
        return None


def check_if_customer(organization_id):
    """Check if a company is already a customer via Apollo account data"""
    if not organization_id:
        return False

    try:
        data = apollo_request('POST', 'mixed_companies/search', {
            'organization_ids': [organization_id],
            'page': 1,
            'per_page': 1,
        })
        organizations = data.get('organizations', [])
        if not organizations:
            return False

        org = organizations[0]
        # Check for customer indicators in Apollo
        account = org.get('account', {}) or {}
        stage = (account.get('stage') or '').lower()
        labels = [l.lower() for l in (account.get('labels') or [])]

        customer_signals = ['customer', 'won', 'closed-won', 'active', 'closed won']
        if any(s in stage for s in customer_signals):
            return True
        if any(any(s in l for s in customer_signals) for l in labels):
            return True

        return False

    except Exception:
        return False


def validate_company(org, min_employees=None, max_employees=None, geo=None,
                     competitor_domains=None):
    """Validate a company against ICP criteria"""
    reasons = []

    if not org:
        return False, ['not_found_in_apollo']

    domain = (org.get('primary_domain') or org.get('website_url') or '').lower()
    # Extract domain from URL if needed
    if '/' in domain:
        from urllib.parse import urlparse
        parsed = urlparse(domain if domain.startswith('http') else f'https://{domain}')
        domain = parsed.netloc or parsed.path
    domain = domain.replace('www.', '')

    # Competitor check
    if competitor_domains and domain in competitor_domains:
        reasons.append(f'competitor ({domain})')

    # Employee count
    employee_count = org.get('estimated_num_employees') or org.get('employee_count') or 0
    if min_employees and employee_count < min_employees:
        reasons.append(f'too_small ({employee_count} employees)')
    if max_employees and employee_count > max_employees:
        reasons.append(f'too_large ({employee_count} employees)')

    # Geography
    if geo:
        country = (org.get('country') or '').lower()
        if geo.lower() not in country and country not in geo.lower():
            # Also check HQ location
            hq = (org.get('raw_address') or org.get('city') or '').lower()
            if geo.lower() not in hq:
                reasons.append(f'wrong_geo ({org.get("country", "unknown")})')

    if reasons:
        return False, reasons
    return True, []


# =============================================================================
# ORCHESTRATION
# =============================================================================

def validate_all_companies(champions_filtered, min_employees=None, max_employees=None, geo=None):
    """Validate all target companies and group by company"""
    competitor_domains = load_competitors()

    # Build a map of unique target companies -> list of champions
    company_map = {}  # company_name_lower -> {company_name, champions: [...]}

    for champion in champions_filtered:
        for employer in champion.get('relevant_employers', []):
            company_name = employer['company_name']
            key = company_name.lower().strip()

            if key not in company_map:
                company_map[key] = {
                    'company_name': company_name,
                    'champions': [],
                }

            company_map[key]['champions'].append({
                'name': champion['champion_name'],
                'email': champion['champion_email'],
                'cw_company': champion['champion_company'],
                'role_at_target': employer['title'],
            })

    total_companies = len(company_map)
    print(f"\nValidating {total_companies} unique target companies...")

    results = []
    excluded = {'competitor': 0, 'icp_fail': 0, 'customer': 0, 'not_found': 0}

    for i, (key, company_data) in enumerate(company_map.items(), 1):
        company_name = company_data['company_name']
        print(f"  [{i}/{total_companies}] {company_name}")

        # Search Apollo
        org = search_company(company_name)
        time.sleep(RATE_LIMIT_DELAY)

        if not org:
            excluded['not_found'] += 1
            print(f"    -> not found in Apollo")
            continue

        # Validate ICP
        valid, reasons = validate_company(
            org, min_employees, max_employees, geo, competitor_domains
        )

        if not valid:
            for reason in reasons:
                if 'competitor' in reason:
                    excluded['competitor'] += 1
                else:
                    excluded['icp_fail'] += 1
            print(f"    -> excluded: {', '.join(reasons)}")
            continue

        # Check if customer
        org_id = org.get('id', '')
        is_customer = check_if_customer(org_id)
        time.sleep(RATE_LIMIT_DELAY)

        if is_customer:
            excluded['customer'] += 1
            print(f"    -> excluded: already a customer")
            continue

        # Extract enriched data
        domain = (org.get('primary_domain') or '').lower()
        if not domain:
            website = org.get('website_url', '')
            if website:
                from urllib.parse import urlparse
                parsed = urlparse(website if website.startswith('http') else f'https://{website}')
                domain = (parsed.netloc or parsed.path).replace('www.', '')

        results.append({
            'company_name': org.get('name', company_name),
            'domain': domain,
            'organization_id': org_id,
            'employee_count': org.get('estimated_num_employees') or org.get('employee_count'),
            'industry': org.get('industry', ''),
            'country': org.get('country', ''),
            'champions': company_data['champions'],
        })

        champion_count = len(company_data['champions'])
        print(f"    -> valid ({champion_count} champion{'s' if champion_count > 1 else ''})")

    print(f"\n  Validation complete:")
    print(f"    Valid: {len(results)}")
    print(f"    Not found: {excluded['not_found']}")
    print(f"    Competitor: {excluded['competitor']}")
    print(f"    ICP fail: {excluded['icp_fail']}")
    print(f"    Already customer: {excluded['customer']}")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Validate target companies against ICP and group by company'
    )
    parser.add_argument('roles_json', help='Path to roles_filtered.json')
    parser.add_argument('--min-employees', type=int, default=None,
                        help='Minimum employee count')
    parser.add_argument('--max-employees', type=int, default=None,
                        help='Maximum employee count')
    parser.add_argument('--geo', default=None,
                        help='Geographic filter (e.g., "United States")')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE CHAMPIONS - STEP 4: VALIDATE COMPANIES")
    print("=" * 70)

    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set in .env")
        sys.exit(1)

    input_path = Path(args.roles_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        champions_filtered = json.load(f)

    # Count unique target companies
    unique_companies = set()
    for c in champions_filtered:
        for e in c.get('relevant_employers', []):
            unique_companies.add(e['company_name'].lower())

    competitor_domains = load_competitors()

    print(f"\nChampions with relevant history: {len(champions_filtered)}")
    print(f"Unique target companies: {len(unique_companies)}")
    print(f"Competitor domains loaded: {len(competitor_domains)}")
    if args.min_employees or args.max_employees:
        print(f"Employee filter: {args.min_employees or 'any'} - {args.max_employees or 'any'}")
    if args.geo:
        print(f"Geo filter: {args.geo}")

    if not args.yes:
        print()
        response = input("Proceed with company validation? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Validate
    results = validate_all_companies(
        champions_filtered,
        min_employees=args.min_employees,
        max_employees=args.max_employees,
        geo=args.geo,
    )

    # Save output
    output_path = input_path.parent / 'companies_validated.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    multi_champion = sum(1 for c in results if len(c['champions']) > 1)

    print(f"\n{'=' * 70}")
    print("VALIDATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Valid target companies: {len(results)}/{len(unique_companies)}")
    print(f"Companies with multiple champions: {multi_champion}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
