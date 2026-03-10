#!/usr/bin/env python3
"""
Scrape Descriptions - Extract full job descriptions from posting URLs.

Layer 1: Crawl4AI (free) for careers pages and generic URLs
Layer 2: Apify LinkedIn Jobs scraper for linkedin.com URLs

Input: companies_with_jobs.json (from find_companies.py)
Output: job_descriptions.json (company + raw JD text)

Usage:
    python scrape_descriptions.py <companies_json> [--yes]
"""

import json
import sys
import os
import time
import argparse
import requests
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent

# Crawl4AI - self-hosted or cloud endpoint
CRAWL4AI_BASE = os.getenv('CRAWL4AI_BASE_URL', 'http://localhost:11235')

# Apify - for LinkedIn job URLs
APIFY_TOKEN = os.getenv('APIFY_TOKEN', '')
APIFY_LINKEDIN_ACTOR = 'apimaestro~linkedin-job-detail'  # LinkedIn Job Details Scraper

RATE_LIMIT_DELAY = 1.5
SCRAPE_TIMEOUT = 30


# =============================================================================
# HELPERS
# =============================================================================

def is_linkedin_url(url):
    """Check if URL is a LinkedIn job posting"""
    if not url:
        return False
    parsed = urlparse(url)
    return 'linkedin.com' in parsed.netloc.lower()


def clean_text(text):
    """Clean scraped text - remove excessive whitespace"""
    if not text:
        return ''
    import re
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


# =============================================================================
# CRAWL4AI (Layer 1 - Free, for non-LinkedIn URLs)
# =============================================================================

def scrape_with_crawl4ai(url):
    """Scrape a URL using Crawl4AI and return markdown content"""
    try:
        response = requests.post(
            f'{CRAWL4AI_BASE}/crawl',
            json={
                'urls': [url],
                'word_count_threshold': 50,
                'extraction_strategy': 'NoExtractionStrategy',
            },
            timeout=SCRAPE_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        # Crawl4AI returns {"results": [{...}]} or flat dict/list
        if isinstance(data, dict) and 'results' in data:
            results_list = data['results']
            result = results_list[0] if results_list else {}
        elif isinstance(data, list) and data:
            result = data[0]
        elif isinstance(data, dict):
            result = data
        else:
            return None, 'unexpected response format'

        markdown = result.get('markdown') or result.get('extracted_content') or result.get('text', '')

        if markdown and len(markdown) > 100:
            return clean_text(markdown), 'success'

        # Fallback: build context from metadata (useful for JS-heavy SPAs)
        metadata = result.get('metadata', {})
        if metadata:
            parts = []
            if metadata.get('title'):
                parts.append(metadata['title'])
            if metadata.get('description') or metadata.get('og:description'):
                parts.append(metadata.get('description') or metadata.get('og:description'))
            if metadata.get('keywords'):
                parts.append(f"Keywords: {metadata['keywords']}")
            meta_text = '\n'.join(parts)
            if meta_text and len(meta_text) > 30:
                return clean_text(meta_text), 'success_metadata'

        return None, 'content too short'

    except requests.exceptions.ConnectionError:
        return None, 'crawl4ai_unavailable'
    except requests.exceptions.Timeout:
        return None, 'timeout'
    except Exception as e:
        return None, f'error: {str(e)}'


# =============================================================================
# DIRECT HTTP FALLBACK (Layer 1b - for simple career pages)
# =============================================================================

def scrape_with_requests(url):
    """Simple HTTP request fallback for career pages"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=SCRAPE_TIMEOUT,
                                allow_redirects=True)
        response.raise_for_status()

        html = response.text

        # Very basic HTML to text extraction
        import re
        # Remove script/style
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Convert common tags to newlines
        html = re.sub(r'<br\s*/?\s*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', html, flags=re.IGNORECASE)
        # Remove remaining tags
        html = re.sub(r'<[^>]+>', ' ', html)
        # Clean up entities
        html = html.replace('&nbsp;', ' ').replace('&amp;', '&')
        html = html.replace('&lt;', '<').replace('&gt;', '>')

        text = clean_text(html)
        if text and len(text) > 200:
            return text[:10000], 'success'
        else:
            return None, 'content too short'

    except Exception as e:
        return None, f'error: {str(e)}'


# =============================================================================
# APIFY LINKEDIN (Layer 2 - for LinkedIn URLs)
# =============================================================================

def extract_linkedin_job_id(url):
    """Extract numeric job ID from a LinkedIn job URL.
    e.g. https://www.linkedin.com/jobs/view/4369333985/ -> '4369333985'
    e.g. https://uk.linkedin.com/jobs/view/video-content-creator-...-4321504284 -> '4321504284'
    """
    import re
    # Try /jobs/view/{id} pattern first
    match = re.search(r'/jobs/view/(\d+)', url)
    if match:
        return match.group(1)
    # Fallback: last numeric sequence in URL (covers slug-style URLs)
    match = re.search(r'-(\d{7,})(?:\?|$|/)', url)
    if match:
        return match.group(1)
    # Last resort: any long number
    match = re.search(r'(\d{7,})', url)
    if match:
        return match.group(1)
    return None


def scrape_linkedin_with_apify(urls):
    """
    Scrape LinkedIn job URLs using Apify LinkedIn Job Details Scraper.
    Uses apimaestro/linkedin-job-detail which takes job IDs (not URLs).
    Returns dict of url -> (description, status).
    """
    if not APIFY_TOKEN:
        return {url: (None, 'no_apify_token') for url in urls}

    results = {}

    # Extract job IDs and build mapping
    url_to_id = {}
    id_to_urls = {}  # one ID can match multiple URL formats
    for url in urls:
        job_id = extract_linkedin_job_id(url)
        if job_id:
            url_to_id[url] = job_id
            id_to_urls.setdefault(job_id, []).append(url)
        else:
            results[url] = (None, 'no_job_id_in_url')

    if not url_to_id:
        return results

    job_ids = list(set(url_to_id.values()))
    print(f"  Extracted {len(job_ids)} job IDs from {len(urls)} URLs")

    try:
        # Start the actor run with job IDs
        response = requests.post(
            f'https://api.apify.com/v2/acts/{APIFY_LINKEDIN_ACTOR}/runs',
            params={'token': APIFY_TOKEN},
            json={'job_id': job_ids},
            timeout=30,
        )
        response.raise_for_status()
        run_data = response.json().get('data', {})
        run_id = run_data.get('id')

        if not run_id:
            for url in urls:
                if url not in results:
                    results[url] = (None, 'no_run_id')
            return results

        print(f"  Apify run started: {run_id}")

        # Poll for completion
        status_data = {}
        for _ in range(60):  # Max 5 min wait
            time.sleep(5)
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
                print(f"  Apify run {status}")
                for url in urls:
                    if url not in results:
                        results[url] = (None, f'apify_{status.lower()}')
                return results

        # Fetch results
        dataset_id = status_data.get('defaultDatasetId')
        if not dataset_id:
            for url in urls:
                if url not in results:
                    results[url] = (None, 'no_dataset')
            return results

        items_resp = requests.get(
            f'https://api.apify.com/v2/datasets/{dataset_id}/items',
            params={'token': APIFY_TOKEN},
            timeout=30,
        )
        items = items_resp.json()

        # Map results back to original URLs via job posting ID
        for item in items:
            job_info = item.get('job_info', {})
            description = job_info.get('description', '')
            posting_id = str(job_info.get('job_posting_id', ''))

            if not description:
                continue

            # Find original URLs for this job ID
            matched_urls = id_to_urls.get(posting_id, [])
            for matched_url in matched_urls:
                results[matched_url] = (clean_text(description), 'success')

        # Mark unfound URLs
        for url in urls:
            if url not in results:
                results[url] = (None, 'not_in_results')

        return results

    except Exception as e:
        print(f"  Apify error: {e}")
        for url in urls:
            if url not in results:
                results[url] = (None, f'apify_error: {str(e)}')
        return results


# =============================================================================
# ORCHESTRATION
# =============================================================================

def scrape_all_jobs(companies):
    """Scrape job descriptions for all companies"""
    results = []
    linkedin_queue = []
    total_jobs = sum(len(c.get('job_postings', [])) for c in companies)
    processed = 0

    print(f"\nScraping {total_jobs} job postings...")

    # First pass: scrape non-LinkedIn URLs with Crawl4AI/requests
    for company in companies:
        company_result = {
            'company_name': company['company_name'],
            'domain': company['domain'],
            'organization_id': company['organization_id'],
            'employee_count': company.get('employee_count'),
            'industry': company.get('industry', ''),
            'country': company.get('country', ''),
            'contacts': company.get('contacts', []),
            'jobs': [],
        }

        for job in company.get('job_postings', []):
            processed += 1
            url = job.get('url', '')
            title = job.get('title', '')

            if not url:
                company_result['jobs'].append({
                    'title': title,
                    'url': '',
                    'description': None,
                    'scrape_status': 'no_url',
                })
                continue

            if is_linkedin_url(url):
                # Queue LinkedIn URLs for batch Apify processing
                linkedin_queue.append((company_result, job))
                continue

            # Try Crawl4AI first
            print(f"  [{processed}/{total_jobs}] {company['company_name']} - {title}")
            description, status = scrape_with_crawl4ai(url)

            # Fallback to direct HTTP if Crawl4AI unavailable
            if status == 'crawl4ai_unavailable':
                description, status = scrape_with_requests(url)

            company_result['jobs'].append({
                'title': title,
                'url': url,
                'description': description,
                'scrape_status': status,
            })

            if description:
                print(f"    -> {len(description)} chars")
            else:
                print(f"    -> {status}")

            time.sleep(RATE_LIMIT_DELAY)

        if company_result['jobs']:
            results.append(company_result)

    # Second pass: batch scrape LinkedIn URLs with Apify
    if linkedin_queue:
        print(f"\n  Scraping {len(linkedin_queue)} LinkedIn URLs via Apify...")
        linkedin_urls = [job.get('url', '') for _, job in linkedin_queue]
        linkedin_results = scrape_linkedin_with_apify(linkedin_urls)

        for company_result, job in linkedin_queue:
            url = job.get('url', '')
            description, status = linkedin_results.get(url, (None, 'not_processed'))

            company_result['jobs'].append({
                'title': job.get('title', ''),
                'url': url,
                'description': description,
                'scrape_status': status,
            })

            # Ensure this company is in results
            if company_result not in results:
                results.append(company_result)

    # Third pass: scrape company homepages for additional context
    print(f"\n  Scraping {len(results)} company homepages...")
    homepage_ok = 0
    for company_result in results:
        domain = company_result.get('domain', '')
        if not domain:
            company_result['company_context'] = None
            continue

        homepage_url = f'https://{domain}'
        print(f"  Homepage: {homepage_url}")
        content, status = scrape_with_crawl4ai(homepage_url)

        # Fallback to direct HTTP
        if status == 'crawl4ai_unavailable':
            content, status = scrape_with_requests(homepage_url)

        if content:
            company_result['company_context'] = content[:5000]
            homepage_ok += 1
            print(f"    -> {len(content[:5000])} chars")
        else:
            company_result['company_context'] = None
            print(f"    -> {status}")

        time.sleep(RATE_LIMIT_DELAY)

    # Stats
    total_scraped = sum(
        1 for c in results
        for j in c['jobs']
        if j.get('description')
    )
    total_failed = sum(
        1 for c in results
        for j in c['jobs']
        if not j.get('description')
    )

    print(f"\n  Scrape complete: {total_scraped} JDs success, {total_failed} failed, {homepage_ok} homepages scraped")
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Scrape full job descriptions from posting URLs'
    )
    parser.add_argument('companies_json', help='Path to companies_with_jobs.json')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("HIRING INTEL - STEP 2: SCRAPE JOB DESCRIPTIONS")
    print("=" * 70)

    input_path = Path(args.companies_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)

    total_companies = len(companies)
    total_jobs = sum(len(c.get('job_postings', [])) for c in companies)
    linkedin_jobs = sum(
        1 for c in companies
        for j in c.get('job_postings', [])
        if is_linkedin_url(j.get('url', ''))
    )
    other_jobs = total_jobs - linkedin_jobs

    print(f"\nCompanies: {total_companies}")
    print(f"Total jobs to scrape: {total_jobs}")
    print(f"  LinkedIn URLs: {linkedin_jobs}" + (' (Apify)' if linkedin_jobs else ''))
    print(f"  Other URLs: {other_jobs}" + (' (Crawl4AI)' if other_jobs else ''))

    if linkedin_jobs and not APIFY_TOKEN:
        print("\n  Warning: APIFY_TOKEN not set. LinkedIn URLs will be skipped.")

    if not args.yes:
        print()
        response = input("Proceed with scraping? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Scrape
    results = scrape_all_jobs(companies)

    # Save output alongside input
    output_path = input_path.parent / 'job_descriptions.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    companies_with_desc = sum(
        1 for c in results
        if any(j.get('description') for j in c['jobs'])
    )
    total_descs = sum(
        1 for c in results
        for j in c['jobs']
        if j.get('description')
    )

    print(f"\n{'=' * 70}")
    print("SCRAPE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Companies with descriptions: {companies_with_desc}/{total_companies}")
    print(f"Job descriptions scraped: {total_descs}/{total_jobs}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
