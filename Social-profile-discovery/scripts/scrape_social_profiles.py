#!/usr/bin/env python3
"""
Social Media Profile Discovery — Multi-layer scraping system.

Discovers ALL social media profiles for companies from their websites.

Layers:
  1. Crawl4AI (batch headless browser) — homepage, /about, /contact + hreflang pages
  2. Playwright (targeted fallback) — for companies where Layer 1 found nothing
  3. DataForSEO SERP (final fallback) — site:platform.com "company name"

Usage:
    python scrape_social_profiles.py <input_csv> --source NAME [options]

Options:
    --output-dir PATH    Output directory (default: generated-outputs/)
    --skip-serp          Skip Layer 3 (SERP fallback) entirely
    --concurrency N      Max concurrent browser sessions (default: 5)
    --yes                Skip confirmation prompt
"""

import csv
import json
import re
import sys
import asyncio
import argparse
import time
import base64
import requests
from pathlib import Path
from datetime import date
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import html as html_mod
import os

from social_platform_patterns import (
    PLATFORMS,
    classify_url,
    classify_profile_type,
    normalize_social_url,
    is_share_or_intent_url,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
OUTPUT_DIR = SKILL_DIR / 'generated-outputs'

# DataForSEO API (reused from enrich_mentions.py)
DFS_LOGIN = os.getenv('DATAFORSEO_USERNAME') or os.getenv('DATAFORSEO_LOGIN', '')
DFS_PASSWORD = os.getenv('DATAFORSEO_PASSWORD', '')
DFS_BASE = 'https://api.dataforseo.com'
DFS_TASK_POST = f'{DFS_BASE}/v3/serp/google/organic/task_post'
DFS_TASKS_READY = f'{DFS_BASE}/v3/serp/google/organic/tasks_ready'
DFS_TASK_GET = f'{DFS_BASE}/v3/serp/google/organic/task_get/advanced'
DFS_BALANCE = f'{DFS_BASE}/v3/appendix/user_data'
DFS_BATCH_SIZE = 100
DFS_POLL_INTERVAL = 5
DFS_MAX_WAIT = 600
DFS_COST_PER_QUERY = 0.0006

# Browser settings
DEFAULT_CONCURRENCY = 5
PAGE_TIMEOUT = 30000  # ms

# Pages to check per domain (beyond homepage)
EXTRA_PATHS = ['/about', '/about-us', '/contact', '/contact-us']

# Column aliases for input CSV
COLUMN_ALIASES = {
    'website': ['website', 'Website', 'domain', 'Domain', 'url', 'URL', 'company_website'],
    'company_name': ['Company Name', 'company_name', 'company', 'name', 'source_name', 'Name'],
}

# Platforms to query via SERP (Layer 3)
SERP_PLATFORM_QUERIES = {
    'linkedin': 'site:linkedin.com/company "{name}"',
    'twitter': 'site:twitter.com "{name}" OR site:x.com "{name}"',
    'facebook': 'site:facebook.com "{name}"',
    'instagram': 'site:instagram.com "{name}"',
    'youtube': 'site:youtube.com "{name}"',
    'tiktok': 'site:tiktok.com "@{name}"',
    'pinterest': 'site:pinterest.com "{name}"',
    'threads': 'site:threads.net "{name}"',
    'bluesky': 'site:bsky.app "{name}"',
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SocialProfile:
    platform: str
    url: str
    handle: str
    profile_type: str = 'main'  # main, regional, category
    discovery_method: str = 'website_scrape'  # website_scrape, structured_data, serp_search
    confidence: str = 'high'  # high, medium, low


@dataclass
class CompanyResult:
    company_name: str
    website: str
    profiles: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    layers_used: list = field(default_factory=list)


# =============================================================================
# HELPERS
# =============================================================================

def detect_column(headers, field_type):
    """Detect column by alias matching."""
    aliases = COLUMN_ALIASES.get(field_type, [])
    for alias in aliases:
        if alias in headers:
            return alias
        for h in headers:
            if h.lower() == alias.lower():
                return h
    return None


def get_dfs_auth_header():
    """Create Basic Auth header for DataForSEO API."""
    credentials = f"{DFS_LOGIN}:{DFS_PASSWORD}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}


def check_dfs_balance():
    """Check DataForSEO account balance."""
    try:
        response = requests.get(DFS_BALANCE, headers=get_dfs_auth_header(), timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get('status_code') == 20000:
            tasks = data.get('tasks', [])
            if tasks and tasks[0].get('result'):
                return tasks[0]['result'][0].get('money', {}).get('balance', 0)
        return None
    except Exception:
        return None


# =============================================================================
# EXTRACTION LOGIC (shared across layers)
# =============================================================================

def extract_social_profiles_from_html(html: str, base_url: str, company_name: str,
                                      method: str = 'website_scrape') -> list:
    """
    Extract social media profiles from raw HTML.

    Parses:
    1. <a> tags with href attributes
    2. <link rel="me"> tags
    3. JSON-LD sameAs arrays
    4. twitter:site and twitter:creator meta tags
    5. og:see_also meta tags
    6. data-href attributes

    Returns: list of SocialProfile
    """
    profiles = []
    seen_urls = set()

    def _add_profile(url, discovery=method, conf='high'):
        # Decode HTML entities (e.g. &amp; → &) that leak from raw HTML parsing
        url = html_mod.unescape(url)
        # Reject URLs with spaces or obviously broken fragments
        if ' ' in url or '\n' in url or '\t' in url:
            return
        result = classify_url(url)
        if result is None:
            return
        platform, normalized, handle = result
        if normalized in seen_urls:
            return
        seen_urls.add(normalized)
        ptype = classify_profile_type(handle, company_name)
        profiles.append(SocialProfile(
            platform=platform,
            url=normalized,
            handle=handle,
            profile_type=ptype,
            discovery_method=discovery,
            confidence=conf,
        ))

    # 1. Extract all href attributes from <a> tags
    for match in re.finditer(r'<a\s[^>]*?href=["\']([^"\']+)["\']', html, re.IGNORECASE):
        href = match.group(1).strip()
        if href.startswith(('http://', 'https://')):
            _add_profile(href)
        elif href.startswith('//'):
            _add_profile('https:' + href)

    # 2. <link rel="me"> tags (IndieWeb/Mastodon convention)
    for match in re.finditer(r'<link\s[^>]*?rel=["\']me["\'][^>]*?href=["\']([^"\']+)["\']',
                             html, re.IGNORECASE):
        _add_profile(match.group(1).strip())
    # Also match href before rel
    for match in re.finditer(r'<link\s[^>]*?href=["\']([^"\']+)["\'][^>]*?rel=["\']me["\']',
                             html, re.IGNORECASE):
        _add_profile(match.group(1).strip())

    # 3. JSON-LD sameAs
    for match in re.finditer(
        r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.IGNORECASE | re.DOTALL
    ):
        try:
            ld_data = json.loads(match.group(1))
            # Handle both single objects and arrays
            items = ld_data if isinstance(ld_data, list) else [ld_data]
            for item in items:
                same_as = item.get('sameAs', [])
                if isinstance(same_as, str):
                    same_as = [same_as]
                for url in same_as:
                    _add_profile(url, discovery='structured_data', conf='high')

                # Also check nested @graph
                graph = item.get('@graph', [])
                for node in graph:
                    same_as = node.get('sameAs', [])
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    for url in same_as:
                        _add_profile(url, discovery='structured_data', conf='high')
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # 4. twitter:site and twitter:creator meta tags
    for match in re.finditer(
        r'<meta\s[^>]*?(?:name|property)=["\']twitter:(site|creator)["\'][^>]*?content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    ):
        handle = match.group(2).strip().lstrip('@')
        if handle:
            _add_profile(f'https://twitter.com/{handle}', discovery='structured_data', conf='high')
    # Also match content before name
    for match in re.finditer(
        r'<meta\s[^>]*?content=["\']([^"\']+)["\'][^>]*?(?:name|property)=["\']twitter:(site|creator)["\']',
        html, re.IGNORECASE
    ):
        handle = match.group(1).strip().lstrip('@')
        if handle:
            _add_profile(f'https://twitter.com/{handle}', discovery='structured_data', conf='high')

    # 5. og:see_also meta tags
    for match in re.finditer(
        r'<meta\s[^>]*?property=["\']og:see_also["\'][^>]*?content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    ):
        _add_profile(match.group(1).strip(), discovery='structured_data', conf='medium')

    # 6. data-href attributes (some sites use these)
    for match in re.finditer(r'data-href=["\']([^"\']+)["\']', html, re.IGNORECASE):
        url = match.group(1).strip()
        if url.startswith(('http://', 'https://')):
            _add_profile(url, conf='medium')

    return profiles


def extract_hreflang_urls(html: str, base_url: str) -> list:
    """
    Extract hreflang alternate URLs from HTML.

    Returns: list of (url, lang) tuples
    """
    hreflangs = []
    seen = set()

    for match in re.finditer(
        r'<link\s[^>]*?rel=["\']alternate["\'][^>]*?hreflang=["\']([^"\']+)["\'][^>]*?href=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    ):
        lang = match.group(1).strip()
        url = match.group(2).strip()
        if url not in seen and lang != 'x-default':
            seen.add(url)
            # Resolve relative URLs
            if not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)
            hreflangs.append((url, lang))

    # Also match href before hreflang
    for match in re.finditer(
        r'<link\s[^>]*?href=["\']([^"\']+)["\'][^>]*?hreflang=["\']([^"\']+)["\'][^>]*?rel=["\']alternate["\']',
        html, re.IGNORECASE
    ):
        url = match.group(1).strip()
        lang = match.group(2).strip()
        if url not in seen and lang != 'x-default':
            seen.add(url)
            if not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)
            hreflangs.append((url, lang))

    return hreflangs


# =============================================================================
# LAYER 1: CRAWL4AI
# =============================================================================

async def layer1_crawl4ai(companies: list, concurrency: int = DEFAULT_CONCURRENCY) -> dict:
    """
    Layer 1: Crawl company websites using Crawl4AI.

    Args:
        companies: list of dicts with 'company_name' and 'website' keys
        concurrency: max concurrent browser sessions

    Returns: dict of domain -> CompanyResult
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

    results = {}
    total = len(companies)

    print(f"\n  Layer 1 (Crawl4AI): Processing {total} companies...")

    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
    )

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=PAGE_TIMEOUT,
        wait_until="domcontentloaded",
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, company in enumerate(companies):
            name = company['company_name']
            website = company['website'].strip().rstrip('/')

            # Ensure protocol
            if not website.startswith(('http://', 'https://')):
                website = f'https://{website}'

            result = CompanyResult(company_name=name, website=website)
            result.layers_used.append('crawl4ai')

            all_profiles = []
            hreflang_urls = []

            # Crawl homepage + extra paths
            pages_to_crawl = [website]
            for path in EXTRA_PATHS:
                pages_to_crawl.append(f'{website}{path}')

            for page_url in pages_to_crawl:
                try:
                    crawl_result = await crawler.arun(url=page_url, config=run_config)

                    if crawl_result and crawl_result.html:
                        # Extract social profiles
                        profiles = extract_social_profiles_from_html(
                            crawl_result.html, page_url, name
                        )
                        all_profiles.extend(profiles)

                        # Extract hreflang URLs from homepage only
                        if page_url == website:
                            hreflang_urls = extract_hreflang_urls(crawl_result.html, page_url)

                except Exception as e:
                    result.errors.append(f"Crawl4AI error on {page_url}: {str(e)[:100]}")
                    continue

            # Crawl hreflang pages
            if hreflang_urls:
                for hreflang_url, lang in hreflang_urls:
                    try:
                        crawl_result = await crawler.arun(url=hreflang_url, config=run_config)
                        if crawl_result and crawl_result.html:
                            profiles = extract_social_profiles_from_html(
                                crawl_result.html, hreflang_url, name
                            )
                            all_profiles.extend(profiles)
                    except Exception:
                        continue

            # Deduplicate profiles
            result.profiles = _deduplicate_profiles(all_profiles)

            status = f"found {len(result.profiles)} profiles" if result.profiles else "no profiles"
            hreflang_msg = f" (+{len(hreflang_urls)} locales)" if hreflang_urls else ""
            print(f"  [{i+1}/{total}] {name}: {status}{hreflang_msg}")

            results[website] = result

    return results


# =============================================================================
# LAYER 2: PLAYWRIGHT FALLBACK
# =============================================================================

async def layer2_playwright(companies: list, concurrency: int = DEFAULT_CONCURRENCY) -> dict:
    """
    Layer 2: Targeted Playwright fallback for companies with zero profiles from Layer 1.

    Uses more aggressive settings: stealth UA, longer timeouts, scroll-to-bottom.
    """
    from playwright.async_api import async_playwright

    results = {}
    total = len(companies)

    if total == 0:
        return results

    print(f"\n  Layer 2 (Playwright): Processing {total} companies...")

    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
        )

        async def process_company(i, company):
            name = company['company_name']
            website = company['website'].strip().rstrip('/')
            if not website.startswith(('http://', 'https://')):
                website = f'https://{website}'

            result = CompanyResult(company_name=name, website=website)
            result.layers_used.append('playwright')
            all_profiles = []
            hreflang_urls = []

            async with semaphore:
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    ignore_https_errors=True,
                )
                page = await context.new_page()

                pages_to_crawl = [website]
                for path in EXTRA_PATHS:
                    pages_to_crawl.append(f'{website}{path}')

                for page_url in pages_to_crawl:
                    try:
                        await page.goto(page_url, wait_until='domcontentloaded', timeout=30000)
                        # Scroll to bottom to trigger lazy-loaded footers
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await page.wait_for_timeout(1500)

                        html = await page.content()
                        profiles = extract_social_profiles_from_html(html, page_url, name)
                        all_profiles.extend(profiles)

                        # Hreflang from homepage
                        if page_url == website:
                            hreflang_urls = extract_hreflang_urls(html, page_url)

                    except Exception as e:
                        result.errors.append(f"Playwright error on {page_url}: {str(e)[:100]}")
                        continue

                # Crawl hreflang pages
                for hreflang_url, lang in hreflang_urls:
                    try:
                        await page.goto(hreflang_url, wait_until='domcontentloaded', timeout=30000)
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await page.wait_for_timeout(1000)
                        html = await page.content()
                        profiles = extract_social_profiles_from_html(html, hreflang_url, name)
                        all_profiles.extend(profiles)
                    except Exception:
                        continue

                await context.close()

            result.profiles = _deduplicate_profiles(all_profiles)
            status = f"found {len(result.profiles)} profiles" if result.profiles else "no profiles"
            print(f"  [{i+1}/{total}] {name}: {status}")

            results[website] = result

        tasks = [process_company(i, c) for i, c in enumerate(companies)]
        await asyncio.gather(*tasks, return_exceptions=True)

        await browser.close()

    return results


# =============================================================================
# LAYER 3: DATAFORSEO SERP FALLBACK
# =============================================================================

def layer3_serp(companies: list) -> dict:
    """
    Layer 3: DataForSEO SERP search for companies with zero profiles.

    Posts batch queries like site:linkedin.com/company "CompanyName" etc.
    """
    results = {}
    total = len(companies)

    if total == 0:
        return results

    print(f"\n  Layer 3 (SERP): Processing {total} companies...")

    # Build all queries
    all_tasks = []  # (company_dict, platform, query)
    for company in companies:
        name = company['company_name']
        for platform, query_template in SERP_PLATFORM_QUERIES.items():
            query = query_template.format(name=name)
            all_tasks.append((company, platform, query))

    # Batch POST
    headers = get_dfs_auth_header()
    task_mapping = {}  # task_id -> (company, platform)
    num_batches = (len(all_tasks) + DFS_BATCH_SIZE - 1) // DFS_BATCH_SIZE

    for batch_num in range(num_batches):
        start = batch_num * DFS_BATCH_SIZE
        end = min(start + DFS_BATCH_SIZE, len(all_tasks))
        batch = all_tasks[start:end]

        post_data = []
        for company, platform, query in batch:
            post_data.append({
                'keyword': query,
                'location_name': 'United States',
                'language_code': 'en',
                'depth': 5,
                'tag': f"{company['company_name']}||{platform}",
            })

        try:
            response = requests.post(DFS_TASK_POST, headers=headers, json=post_data, timeout=60)
            response.raise_for_status()
            data = response.json()

            if data.get('status_code') == 20000:
                for task_info in data.get('tasks', []):
                    task_id = task_info.get('id')
                    tag = task_info.get('data', {}).get('tag', '')
                    parts = tag.split('||')
                    if task_id and len(parts) == 2:
                        company_name, platform = parts
                        # Find company dict
                        comp = next((c for c in companies if c['company_name'] == company_name), None)
                        if comp:
                            task_mapping[task_id] = (comp, platform)

            print(f"    Batch {batch_num + 1}/{num_batches}: {len(batch)} queries posted")
        except Exception as e:
            print(f"    Batch {batch_num + 1} error: {str(e)[:100]}")

        if batch_num < num_batches - 1:
            time.sleep(0.5)

    # Poll for results
    print(f"    Waiting for {len(task_mapping)} results...")
    retrieved = set()
    company_profiles = defaultdict(list)  # website -> list of SocialProfile
    start_time = time.time()

    while len(retrieved) < len(task_mapping):
        elapsed = time.time() - start_time
        if elapsed > DFS_MAX_WAIT:
            print(f"    Timeout after {DFS_MAX_WAIT}s. Got {len(retrieved)}/{len(task_mapping)}")
            break

        try:
            response = requests.get(DFS_TASKS_READY, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            ready_ids = []
            if data.get('status_code') == 20000:
                for task in data.get('tasks', []):
                    for item in (task.get('result') or []):
                        tid = item.get('id')
                        if tid and tid in task_mapping and tid not in retrieved:
                            ready_ids.append(tid)

            for task_id in ready_ids:
                company, platform = task_mapping[task_id]
                website = company['website'].strip().rstrip('/')
                if not website.startswith(('http://', 'https://')):
                    website = f'https://{website}'

                try:
                    url = f"{DFS_TASK_GET}/{task_id}"
                    resp = requests.get(url, headers=headers, timeout=30)
                    resp.raise_for_status()
                    task_data = resp.json()

                    if task_data.get('status_code') == 20000:
                        tasks_list = task_data.get('tasks', [])
                        if tasks_list:
                            items = (tasks_list[0].get('result') or [{}])[0].get('items', [])
                            for item in items:
                                if item.get('type') == 'organic':
                                    result_url = item.get('url', '')
                                    classified = classify_url(result_url)
                                    if classified and classified[0] == platform:
                                        _, normalized, handle = classified
                                        ptype = classify_profile_type(handle, company['company_name'])
                                        company_profiles[website].append(SocialProfile(
                                            platform=platform,
                                            url=normalized,
                                            handle=handle,
                                            profile_type=ptype,
                                            discovery_method='serp_search',
                                            confidence='medium',
                                        ))
                                        break  # Take first matching result per platform

                except Exception:
                    pass

                retrieved.add(task_id)

        except Exception:
            pass

        if len(retrieved) < len(task_mapping):
            progress = len(retrieved) / len(task_mapping) * 100
            print(f"    Progress: {len(retrieved)}/{len(task_mapping)} ({progress:.0f}%)")
            time.sleep(DFS_POLL_INTERVAL)

    # Build CompanyResult objects
    for company in companies:
        website = company['website'].strip().rstrip('/')
        if not website.startswith(('http://', 'https://')):
            website = f'https://{website}'

        result = CompanyResult(
            company_name=company['company_name'],
            website=website,
            profiles=_deduplicate_profiles(company_profiles.get(website, [])),
        )
        result.layers_used.append('serp_search')

        status = f"found {len(result.profiles)} profiles" if result.profiles else "no profiles"
        print(f"    {company['company_name']}: {status}")

        results[website] = result

    return results


# =============================================================================
# DEDUPLICATION
# =============================================================================

def _deduplicate_profiles(profiles: list) -> list:
    """
    Deduplicate profiles by normalized URL.
    Keeps the entry with highest confidence: structured_data > website_scrape > serp_search.
    """
    CONFIDENCE_ORDER = {'high': 3, 'medium': 2, 'low': 1}
    best = {}

    for p in profiles:
        key = p.url  # Already normalized
        existing = best.get(key)
        if existing is None:
            best[key] = p
        else:
            # Keep higher confidence
            if CONFIDENCE_ORDER.get(p.confidence, 0) > CONFIDENCE_ORDER.get(existing.confidence, 0):
                best[key] = p

    return list(best.values())


# =============================================================================
# CSV I/O
# =============================================================================

def read_input_csv(input_path: str) -> list:
    """
    Read input CSV and return list of company dicts.

    Returns: list of {'company_name': str, 'website': str}
    """
    companies = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        website_col = detect_column(headers, 'website')
        name_col = detect_column(headers, 'company_name')

        if not website_col:
            raise ValueError(f"Could not detect website column. Headers: {headers}")

        for row in reader:
            website = (row.get(website_col) or '').strip()
            if not website:
                continue

            name = ''
            if name_col:
                name = (row.get(name_col) or '').strip()
            if not name:
                # Derive name from domain
                try:
                    parsed = urlparse(website if '://' in website else f'https://{website}')
                    name = (parsed.hostname or website).replace('www.', '').split('.')[0].title()
                except Exception:
                    name = website

            companies.append({'company_name': name, 'website': website})

    # Deduplicate by normalized domain
    seen = set()
    unique = []
    for c in companies:
        domain = c['website'].lower().replace('https://', '').replace('http://', '').rstrip('/')
        if domain not in seen:
            seen.add(domain)
            unique.append(c)

    return unique


def write_pivot_csv(results: dict, output_path: str):
    """
    Write pivot CSV: one row per company with profile counts and pipe-delimited URLs.
    """
    platform_order = ['facebook', 'instagram', 'twitter', 'linkedin', 'tiktok',
                       'youtube', 'pinterest', 'threads', 'bluesky']

    fieldnames = ['Company Name', 'Website', 'Total Profiles']
    for p in platform_order:
        fieldnames.append(f'{p.title()} (count)')
        fieldnames.append(f'{p.title()} (URLs)')
    fieldnames.append('Discovery Layers Used')

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for website, result in sorted(results.items(), key=lambda x: len(x[1].profiles), reverse=True):
            row = {
                'Company Name': result.company_name,
                'Website': result.website,
                'Total Profiles': len(result.profiles),
                'Discovery Layers Used': ', '.join(result.layers_used),
            }

            # Group profiles by platform
            by_platform = defaultdict(list)
            for p in result.profiles:
                by_platform[p.platform].append(p)

            for platform in platform_order:
                profiles = by_platform.get(platform, [])
                row[f'{platform.title()} (count)'] = len(profiles)
                row[f'{platform.title()} (URLs)'] = ' | '.join(p.url for p in profiles)

            writer.writerow(row)

    print(f"\n  Output: {output_path}")
    print(f"  Companies: {len(results)}")
    total_profiles = sum(len(r.profiles) for r in results.values())
    print(f"  Total profiles discovered: {total_profiles}")


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

async def run_discovery(companies: list, skip_serp: bool = False,
                        concurrency: int = DEFAULT_CONCURRENCY) -> dict:
    """
    Run the three-layer discovery cascade.

    Returns: dict of website -> CompanyResult (merged across all layers)
    """
    all_results = {}

    # === LAYER 1: Crawl4AI ===
    print("\n" + "-" * 50)
    print("LAYER 1: Crawl4AI (batch scraping)")
    print("-" * 50)

    l1_results = await layer1_crawl4ai(companies, concurrency)
    all_results.update(l1_results)

    # Find companies with zero profiles
    l1_failures = []
    l1_success = 0
    for company in companies:
        website = company['website'].strip().rstrip('/')
        if not website.startswith(('http://', 'https://')):
            website = f'https://{website}'
        result = l1_results.get(website)
        if result and result.profiles:
            l1_success += 1
        else:
            l1_failures.append(company)

    print(f"\n  Layer 1 summary: {l1_success}/{len(companies)} companies found profiles")
    print(f"  Remaining for Layer 2: {len(l1_failures)} companies")

    # === LAYER 2: Playwright ===
    if l1_failures:
        print("\n" + "-" * 50)
        print("LAYER 2: Playwright (targeted fallback)")
        print("-" * 50)

        l2_results = await layer2_playwright(l1_failures, concurrency)

        # Merge Layer 2 results
        l2_success = 0
        l2_still_failed = []
        for company in l1_failures:
            website = company['website'].strip().rstrip('/')
            if not website.startswith(('http://', 'https://')):
                website = f'https://{website}'

            l2_result = l2_results.get(website)
            if l2_result and l2_result.profiles:
                l2_success += 1
                # Merge into all_results
                existing = all_results.get(website)
                if existing:
                    existing.profiles = _deduplicate_profiles(existing.profiles + l2_result.profiles)
                    existing.layers_used.extend(l2_result.layers_used)
                else:
                    all_results[website] = l2_result
            else:
                l2_still_failed.append(company)
                # Still update layers_used
                if website in all_results:
                    all_results[website].layers_used.append('playwright')

        print(f"\n  Layer 2 summary: {l2_success}/{len(l1_failures)} companies found profiles")
        print(f"  Remaining for Layer 3: {len(l2_still_failed)} companies")
    else:
        l2_still_failed = []

    # === LAYER 3: SERP ===
    if l2_still_failed and not skip_serp:
        print("\n" + "-" * 50)
        print("LAYER 3: DataForSEO SERP (final fallback)")
        print("-" * 50)

        l3_results = layer3_serp(l2_still_failed)

        # Merge Layer 3 results
        l3_success = 0
        for company in l2_still_failed:
            website = company['website'].strip().rstrip('/')
            if not website.startswith(('http://', 'https://')):
                website = f'https://{website}'

            l3_result = l3_results.get(website)
            if l3_result and l3_result.profiles:
                l3_success += 1

            existing = all_results.get(website)
            if existing and l3_result:
                existing.profiles = _deduplicate_profiles(existing.profiles + l3_result.profiles)
                existing.layers_used.extend(l3_result.layers_used)
            elif l3_result:
                all_results[website] = l3_result

        print(f"\n  Layer 3 summary: {l3_success}/{len(l2_still_failed)} companies found profiles")
    elif l2_still_failed and skip_serp:
        print(f"\n  Skipping Layer 3 (SERP) — {len(l2_still_failed)} companies have no profiles")

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description='Discover social media profiles for companies from their websites',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python scrape_social_profiles.py companies.csv --source competitor_list

  # Skip SERP fallback (faster, no API cost)
  python scrape_social_profiles.py companies.csv --source test --skip-serp

  # Higher concurrency for large batches
  python scrape_social_profiles.py companies.csv --source batch --concurrency 10 --yes
        """,
    )
    parser.add_argument('input_csv', help='Path to input CSV with Website column')
    parser.add_argument('--source', required=True, help='Source name for output file naming')
    parser.add_argument('--output-dir', help='Output directory (default: generated-outputs/)')
    parser.add_argument('--skip-serp', action='store_true', help='Skip Layer 3 (SERP fallback)')
    parser.add_argument('--concurrency', type=int, default=DEFAULT_CONCURRENCY,
                        help=f'Max concurrent browser sessions (default: {DEFAULT_CONCURRENCY})')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print("=" * 70)
    print("Social Media Profile Discovery")
    print("=" * 70)

    # Read input
    print(f"\nReading: {input_path.name}...")
    companies = read_input_csv(str(input_path))
    print(f"  Found {len(companies)} unique companies with websites")

    if not companies:
        print("\nNo companies with websites found. Exiting.")
        sys.exit(0)

    # Estimate costs
    # Worst case: all companies fail L1+L2, need SERP
    serp_cost = len(companies) * len(SERP_PLATFORM_QUERIES) * DFS_COST_PER_QUERY
    avg_serp_cost = serp_cost * 0.05  # Assume ~5% need SERP

    # Dry run
    print("\n" + "=" * 70)
    print("DRY RUN PREVIEW")
    print("=" * 70)
    print(f"\nSource: {args.source}")
    print(f"Companies: {len(companies)}")
    print(f"Concurrency: {args.concurrency}")
    print(f"SERP fallback: {'disabled' if args.skip_serp else 'enabled'}")
    print(f"\nLayers:")
    print(f"  1. Crawl4AI (all {len(companies)} companies)")
    print(f"  2. Playwright (estimated ~{int(len(companies) * 0.1)} companies)")
    if not args.skip_serp:
        print(f"  3. SERP (estimated ~{int(len(companies) * 0.03)} companies)")
        print(f"\nEstimated SERP cost: ~${avg_serp_cost:.2f} (worst case: ${serp_cost:.2f})")
        balance = check_dfs_balance()
        if balance is not None:
            print(f"DataForSEO balance: ${balance:.2f}")

    print(f"\nFirst 10 companies:")
    for i, c in enumerate(companies[:10], 1):
        print(f"  {i}. {c['company_name']} ({c['website']})")
    if len(companies) > 10:
        print(f"  ... and {len(companies) - 10} more")

    # Confirm
    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # Run discovery
    print("\n" + "=" * 70)
    print("RUNNING DISCOVERY")
    print("=" * 70)

    start_time = time.time()
    all_results = asyncio.run(
        run_discovery(companies, skip_serp=args.skip_serp, concurrency=args.concurrency)
    )
    elapsed = time.time() - start_time

    # Write output
    print("\n" + "=" * 70)
    print("SAVING OUTPUT")
    print("=" * 70)

    today = date.today().isoformat()
    source_slug = re.sub(r'[^\w-]', '_', args.source.lower())
    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR / f'{source_slug}-{today}'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f'social_profiles_{today}.csv'
    write_pivot_csv(all_results, str(output_path))

    # Final summary
    total_companies = len(all_results)
    companies_with_profiles = sum(1 for r in all_results.values() if r.profiles)
    total_profiles = sum(len(r.profiles) for r in all_results.values())

    # Profile type breakdown
    type_counts = defaultdict(int)
    platform_counts = defaultdict(int)
    for r in all_results.values():
        for p in r.profiles:
            type_counts[p.profile_type] += 1
            platform_counts[p.platform] += 1

    print(f"\n{'=' * 70}")
    print("DISCOVERY COMPLETE")
    print(f"{'=' * 70}")
    print(f"Companies processed: {total_companies}")
    print(f"Companies with profiles: {companies_with_profiles} ({companies_with_profiles/max(total_companies,1)*100:.1f}%)")
    print(f"Total profiles found: {total_profiles}")
    print(f"Avg profiles per company: {total_profiles/max(total_companies,1):.1f}")
    print(f"Time: {elapsed:.0f}s ({elapsed/max(total_companies,1):.1f}s per company)")

    if type_counts:
        print(f"\nBy type:")
        for ptype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {ptype}: {count}")

    if platform_counts:
        print(f"\nBy platform:")
        for platform, count in sorted(platform_counts.items(), key=lambda x: -x[1]):
            print(f"  {platform}: {count}")

    print(f"\nOutput: {output_path}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
