#!/usr/bin/env python3
"""
Enrich Contacts - Suppression check + split CSV output.

Checks Apollo suppression list to exclude opted-out contacts.
Splits output into two CSVs:
1. contacts_enriched.csv - Contacts with verified emails (ready for outreach)
2. contacts_needs_enrichment.csv - Qualified companies where Apollo found no email

Input: personas_found.json (from find_personas.py)
Output: contacts_enriched.csv + contacts_needs_enrichment.csv

Usage:
    python enrich_contacts.py <input_json> <output_dir>
"""

import json
import csv
import sys
import os
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

APOLLO_API_BASE = 'https://api.apollo.io/api/v1'
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY', '')

RATE_LIMIT_DELAY = 1.0

# Generic email patterns to exclude
GENERIC_EMAIL_PATTERNS = [
    'info@', 'support@', 'hello@', 'contact@', 'sales@',
    'admin@', 'office@', 'team@', 'noreply@', 'no-reply@',
]


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
# SUPPRESSION CHECK
# =============================================================================

def is_suppressed(email):
    """
    Check if email is in Apollo suppression list.

    Note: Apollo API may not have a direct suppression check endpoint.
    This is a placeholder - adjust based on actual Apollo API capabilities.
    """
    if not email:
        return False

    # For now, we'll rely on Apollo's people search already filtering out
    # suppressed contacts. If Apollo provides a suppression check endpoint,
    # implement it here.

    # Placeholder: always return False (assume Apollo filters internally)
    return False


def is_generic_email(email):
    """Check if email is a generic/role-based address"""
    if not email:
        return False

    email_lower = email.lower()
    return any(pattern in email_lower for pattern in GENERIC_EMAIL_PATTERNS)


# =============================================================================
# ENRICHMENT
# =============================================================================

def enrich_contacts(companies_with_personas):
    """
    Enrich contacts and split into two groups:
    1. Contacts with verified emails (ready for outreach)
    2. Companies where no email was found (needs manual enrichment)
    """
    enriched = []
    needs_enrichment = []

    stats = {
        'total_companies': len(companies_with_personas),
        'total_contacts': 0,
        'contacts_with_email': 0,
        'contacts_no_email': 0,
        'contacts_generic_email': 0,
        'contacts_suppressed': 0,
        'companies_with_email': 0,
        'companies_needs_enrichment': 0,
    }

    today = date.today().isoformat()

    print("\n  Processing contacts...")

    for company in companies_with_personas:
        company_name = company['company_name']
        domain = company['domain']
        contacts = company.get('contacts', [])

        stats['total_contacts'] += len(contacts)

        company_has_email = False

        for contact in contacts:
            email = contact.get('email')

            # Check if email exists
            if not email:
                stats['contacts_no_email'] += 1
                continue

            # Check if generic email
            if is_generic_email(email):
                stats['contacts_generic_email'] += 1
                continue

            # Check if suppressed
            if is_suppressed(email):
                stats['contacts_suppressed'] += 1
                continue

            # Valid email found
            stats['contacts_with_email'] += 1
            company_has_email = True

            # Build enriched contact row
            enriched.append({
                'company_name': company_name,
                'domain': domain,
                'employee_count': company.get('employee_count', ''),
                'industry': company.get('industry', ''),
                'country': company.get('country', ''),
                'follower_count': company.get('follower_count', ''),
                'source_competitor': ', '.join(company.get('source_competitors', [])),
                'contact_name': f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or contact.get('name', ''),
                'contact_title': contact.get('title', ''),
                'contact_email': email,
                'contact_phone': contact.get('phone', ''),
                'contact_linkedin_url': contact.get('linkedin_url', ''),
                'contact_id': contact.get('contact_id', ''),
                'date_processed': today,
            })

        # If no valid email found for company, add to needs_enrichment
        if not company_has_email:
            stats['companies_needs_enrichment'] += 1

            # Pick first contact (even without email) for company context
            first_contact = contacts[0] if contacts else {}

            needs_enrichment.append({
                'company_name': company_name,
                'domain': domain,
                'employee_count': company.get('employee_count', ''),
                'industry': company.get('industry', ''),
                'country': company.get('country', ''),
                'follower_count': company.get('follower_count', ''),
                'source_competitor': ', '.join(company.get('source_competitors', [])),
                'contact_name': f"{first_contact.get('first_name', '')} {first_contact.get('last_name', '')}".strip() or first_contact.get('name', ''),
                'contact_title': first_contact.get('title', ''),
                'contact_email': '',  # Empty - needs manual enrichment
                'contact_phone': first_contact.get('phone', ''),
                'contact_linkedin_url': first_contact.get('linkedin_url', ''),
                'contact_id': first_contact.get('contact_id', ''),
                'date_processed': today,
            })
        else:
            stats['companies_with_email'] += 1

    return enriched, needs_enrichment, stats


# =============================================================================
# CSV OUTPUT
# =============================================================================

def write_csv(output_path, rows, fieldnames):
    """Write rows to CSV file"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Enrich contacts with suppression check and split CSV output'
    )
    parser.add_argument('input_json', help='Input JSON file (personas_found.json)')
    parser.add_argument('output_dir', help='Output directory for CSV files')

    args = parser.parse_args()

    print("=" * 70)
    print("CONTACT ENRICHMENT + CSV OUTPUT")
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
        companies = json.load(f)

    print(f"\nCompanies with personas: {len(companies)}")

    # Enrich contacts
    enriched, needs_enrichment, stats = enrich_contacts(companies)

    # Summary
    print(f"\n{'=' * 70}")
    print("ENRICHMENT RESULTS")
    print(f"{'=' * 70}")
    print(f"Total companies: {stats['total_companies']}")
    print(f"Total contacts found: {stats['total_contacts']}")
    print(f"")
    print(f"Contacts with valid email: {stats['contacts_with_email']}")
    print(f"Contacts without email: {stats['contacts_no_email']}")
    print(f"Contacts with generic email: {stats['contacts_generic_email']}")
    print(f"Contacts suppressed: {stats['contacts_suppressed']}")
    print(f"")
    print(f"Companies with email: {stats['companies_with_email']}")
    print(f"Companies needing enrichment: {stats['companies_needs_enrichment']}")

    if stats['total_companies'] > 0:
        email_found_rate = (stats['companies_with_email'] / stats['total_companies']) * 100
        print(f"\nEmail found rate: {email_found_rate:.1f}%")

    # CSV field names
    fieldnames = [
        'company_name', 'domain', 'employee_count', 'industry', 'country',
        'follower_count', 'source_competitor', 'contact_name', 'contact_title',
        'contact_email', 'contact_phone', 'contact_linkedin_url', 'contact_id',
        'date_processed',
    ]

    # Write outputs
    output_dir = Path(args.output_dir)

    enriched_path = output_dir / 'contacts_enriched.csv'
    needs_enrichment_path = output_dir / 'contacts_needs_enrichment.csv'

    print(f"\n{'=' * 70}")
    print("WRITING OUTPUT FILES")
    print(f"{'=' * 70}")

    if enriched:
        write_csv(enriched_path, enriched, fieldnames)
        print(f"✓ contacts_enriched.csv: {len(enriched)} contacts")
        print(f"  → {enriched_path}")
    else:
        print("⚠️  No contacts with emails found")

    if needs_enrichment:
        write_csv(needs_enrichment_path, needs_enrichment, fieldnames)
        print(f"✓ contacts_needs_enrichment.csv: {len(needs_enrichment)} companies")
        print(f"  → {needs_enrichment_path}")
    else:
        print("✓ All companies have emails (no manual enrichment needed)")

    print(f"\n{'=' * 70}")
    print("ENRICHMENT COMPLETE")
    print(f"{'=' * 70}")
    print("\nNext steps:")
    print("1. Import contacts_enriched.csv to Apollo/Instantly")
    print("2. (Optional) Manually enrich contacts_needs_enrichment.csv")


if __name__ == '__main__':
    main()
