#!/usr/bin/env python3
"""
Transform TheirStack Data - Convert API response to job_descriptions.json format.

Transforms TheirStack API response into the pipeline format expected by
extract_intel.py. Groups jobs by company domain, maps hiring manager fields
to contacts, and builds company context from SEO description.

Input: jobs_raw.json (from fetch_theirstack_jobs.py)
Output: job_descriptions.json (pipeline format)

Usage:
    python transform_theirstack_data.py <jobs_raw_json>
"""

import json
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

MAX_COMPANY_CONTEXT = 5000  # Truncate company context if too long
MIN_EMPLOYEE_COUNT = 200  # Filter companies with fewer than N employees

# =============================================================================
# HELPERS
# =============================================================================

def extract_domain(url):
    """Extract domain from company URL.

    Examples:
        https://www.funkemedien.de → funkemedien.de
        funkemedien.de → funkemedien.de
        https://linkedin.com/company/funke → None (LinkedIn URL)
    """
    if not url:
        return None

    # Add scheme if missing
    if not url.startswith('http'):
        url = f'https://{url}'

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        # Filter out linkedin.com URLs (not real company domains)
        if 'linkedin.com' in domain:
            return None

        return domain if domain else None
    except Exception:
        return None


def parse_full_name(full_name):
    """Split full name into first and last.

    Examples:
        "Leonard Wittig" → ("Leonard", "Wittig")
        "Mary" → ("Mary", None)
        "" → (None, None)
    """
    if not full_name:
        return None, None

    parts = full_name.strip().split()

    if len(parts) == 0:
        return None, None
    elif len(parts) == 1:
        return parts[0], None
    else:
        return parts[0], ' '.join(parts[1:])


def build_company_context(seo_desc, company_desc):
    """Concatenate company descriptions with truncation.

    Combines SEO description and company description into a single
    company_context field for intel extraction enrichment.
    """
    parts = []

    if seo_desc:
        parts.append(seo_desc.strip())

    if company_desc:
        parts.append(company_desc.strip())

    if not parts:
        return None

    context = '\n\n'.join(parts)

    # Truncate if too long
    if len(context) > MAX_COMPANY_CONTEXT:
        context = context[:MAX_COMPANY_CONTEXT] + '\n\n[...truncated]'

    return context


def extract_country_code(job):
    """Extract 2-letter country code from job data.

    Tries job_country_code first, falls back to parsing company location.
    """
    country_code = job.get('job_country_code', '')
    if country_code:
        return country_code.upper()

    # Fallback: try to parse from company location (if available)
    # For now, return None if not explicitly provided
    return None


# =============================================================================
# TRANSFORMATION
# =============================================================================

def transform_jobs_to_pipeline_format(jobs):
    """Transform TheirStack API response to job_descriptions.json format.

    Groups jobs by company domain, maps hiring manager to contacts,
    and builds pipeline-compatible structure. Filters companies by employee count.

    Returns:
        List of company dictionaries in pipeline format
    """
    # Group jobs by company domain
    companies_by_domain = defaultdict(list)

    skipped_count = {'no_domain': 0, 'too_small': 0}

    for job in jobs:
        # Get company_object for employee count and domain
        company_obj = job.get('company_object', {})

        # Filter by employee count first
        employee_count = company_obj.get('employee_count')
        if employee_count is None or employee_count < MIN_EMPLOYEE_COUNT:
            skipped_count['too_small'] += 1
            continue

        # Extract domain from company_object.domain first, then fallback to job.company_domain
        domain = company_obj.get('domain') or job.get('company_domain')

        if not domain:
            # Fallback: try company_object.linkedin_url
            linkedin_url = company_obj.get('linkedin_url')
            if linkedin_url:
                # Extract company slug from LinkedIn URL
                # https://linkedin.com/company/funke → funke
                try:
                    slug = linkedin_url.rstrip('/').split('/')[-1]
                    domain = f'linkedin.com/company/{slug}'  # Use as identifier
                except:
                    pass

        if not domain:
            # Skip jobs without identifiable domain
            skipped_count['no_domain'] += 1
            continue

        companies_by_domain[domain].append(job)

    if skipped_count['too_small'] > 0:
        print(f"  Filtered out {skipped_count['too_small']} jobs from companies < {MIN_EMPLOYEE_COUNT} employees")
    if skipped_count['no_domain'] > 0:
        print(f"  Skipped {skipped_count['no_domain']} jobs without identifiable domain")

    # Build pipeline format
    results = []

    for domain, jobs_list in companies_by_domain.items():
        # Use first job for company-level fields (all jobs from same company)
        first_job = jobs_list[0]
        company_obj = first_job.get('company_object', {})

        # Get hiring manager from hiring_team (first person)
        hiring_team = first_job.get('hiring_team', [])
        hiring_manager = hiring_team[0] if hiring_team else {}

        # Parse hiring manager name
        first_name = hiring_manager.get('first_name')
        full_name = hiring_manager.get('full_name', '')
        if not first_name and full_name:
            # Parse from full_name if first_name not provided
            first_name, last_name = parse_full_name(full_name)
        else:
            # Use provided first_name and parse rest from full_name
            last_name = full_name.replace(first_name, '').strip() if first_name else None

        # Build contact (hiring manager)
        contact = {
            'contact_id': None,  # Not in Apollo yet
            'first_name': first_name,
            'last_name': last_name,
            'title': hiring_manager.get('role', ''),
            'email': None,  # Not provided by TheirStack
            'linkedin_url': hiring_manager.get('linkedin_url', ''),
        }

        # Build company context from company_object
        company_context = build_company_context(
            company_obj.get('seo_description'),
            company_obj.get('long_description')
        )

        # Map job postings
        jobs_mapped = []
        for job in jobs_list:
            jobs_mapped.append({
                'title': job.get('job_title', ''),
                'url': job.get('url', ''),
                'description': job.get('description', ''),  # API uses 'description' not 'job_description'
                'scrape_status': 'theirstack_provided',  # Distinguish from scraped
            })

        # Build company record
        company_record = {
            'company_name': company_obj.get('name') or first_job.get('company', ''),
            'domain': domain,
            'organization_id': None,  # Not in Apollo yet
            'employee_count': company_obj.get('employee_count'),
            'industry': company_obj.get('industry', ''),
            'country': first_job.get('country_code', ''),
            'contacts': [contact] if first_name else [],  # Only include if we have a name
            'company_context': company_context,
            'jobs': jobs_mapped,
        }

        results.append(company_record)

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Transform TheirStack API response to pipeline format'
    )
    parser.add_argument('jobs_raw_json', help='Path to jobs_raw.json')

    args = parser.parse_args()

    print("=" * 70)
    print("HIRING INTEL THEIRSTACK - STEP 1: TRANSFORM DATA")
    print("=" * 70)

    # Load raw jobs
    input_path = Path(args.jobs_raw_json)
    if not input_path.exists():
        print(f"\nError: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    total_jobs = len(jobs)
    print(f"\nRaw jobs: {total_jobs}")

    # Transform
    print("\nTransforming to pipeline format...")
    companies = transform_jobs_to_pipeline_format(jobs)

    total_companies = len(companies)
    total_jobs_after = sum(len(c['jobs']) for c in companies)
    companies_with_contacts = sum(1 for c in companies if c['contacts'])

    print(f"\n  Companies grouped: {total_companies}")
    print(f"  Jobs mapped: {total_jobs_after}")
    print(f"  Companies with hiring manager: {companies_with_contacts}")

    # Save output alongside input
    output_path = input_path.parent / 'job_descriptions.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'=' * 70}")
    print("TRANSFORMATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Companies: {total_companies}")
    print(f"Jobs: {total_jobs_after}")
    print(f"Output: {output_path}")

    # Show sample
    if companies:
        print(f"\nSample company (first result):")
        sample = companies[0]
        print(f"  Company: {sample['company_name']} ({sample['domain']})")
        print(f"  Industry: {sample['industry']}")
        print(f"  Employees: {sample['employee_count']}")
        print(f"  Jobs: {len(sample['jobs'])}")
        if sample['contacts']:
            c = sample['contacts'][0]
            print(f"  Hiring Manager: {c['first_name']} {c['last_name']} ({c['title']})")
        if sample['company_context']:
            ctx = sample['company_context'][:150]
            print(f"  Context: {ctx}{'...' if len(sample['company_context']) > 150 else ''}")


if __name__ == '__main__':
    main()
