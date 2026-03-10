#!/usr/bin/env python3
"""
Fetch Mentions - Pull mentions from Mention.com API

Replaces manual CSV export from Mention.com. Fetches all mentions for a given
alert, extracts company names + reach, and outputs a CSV compatible with
enrich_mentions.py.

Handles source_name resolution for social platforms where the Mention API
doesn't return the field directly:
- web/blogs/forums/linkedin/pinterest/tiktok/youtube: source_name returned by API
- facebook: resolved via page ID redirect (facebook.com/profile.php?id=X)
- instagram: resolved via og:title scraping from post URL (when API doesn't provide it)
- twitter: resolved via metadata user ID (best-effort)
- news/images/videos: falls back to source_url domain

Usage:
    python fetch_mentions.py --alert-id ALERT_ID [--since-date YYYY-MM-DD] [--source NAME] [--data-dir PATH]
"""

import csv
import html
import re
import sys
import os
import time
import argparse
import requests
from pathlib import Path
from datetime import date, datetime
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
# OUTPUT_DIR is now set per-competitor via --data-dir parameter

MENTION_API_BASE = 'https://api.mention.net/api'
MENTION_TOKEN = os.getenv('MENTION_API_TOKEN', '')
MENTION_ACCOUNT_ID = os.getenv('MENTION_ACCOUNT_ID', '')

PAGE_LIMIT = 100  # Max per page from Mention API

# Delay between Facebook page ID lookups (avoid rate limits)
FB_RESOLVE_DELAY = 0.3

# Delay between Instagram page scrapes (avoid rate limits)
IG_RESOLVE_DELAY = 0.5


# =============================================================================
# API FUNCTIONS
# =============================================================================

def get_auth_headers():
    """Create Bearer auth headers for Mention API"""
    return {
        'Authorization': f'Bearer {MENTION_TOKEN}',
        'Accept': 'application/json',
    }


def fetch_mentions_page(alert_id, params=None):
    """Fetch a single page of mentions"""
    url = f'{MENTION_API_BASE}/accounts/{MENTION_ACCOUNT_ID}/alerts/{alert_id}/mentions'
    try:
        response = requests.get(
            url,
            headers=get_auth_headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"  HTTP Error: {e.response.status_code} - {e.response.text[:200]}")
        raise
    except Exception as e:
        print(f"  Request error: {e}")
        raise


def fetch_all_mentions(alert_id, since_date=None):
    """
    Fetch all mentions for an alert, paginating through results.
    Returns list of mention dicts.
    """
    all_mentions = []
    params = {
        'limit': PAGE_LIMIT,
    }

    if since_date:
        params['published_after'] = since_date

    page = 1
    url = f'{MENTION_API_BASE}/accounts/{MENTION_ACCOUNT_ID}/alerts/{alert_id}/mentions'
    print(f"\nFetching mentions for alert {alert_id}...")

    while True:
        print(f"  Page {page}...", end=' ')

        try:
            response = requests.get(
                url,
                headers=get_auth_headers(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"request error: {e}")
            break

        mentions = data.get('mentions', [])
        if not mentions:
            print("no more results.")
            break

        all_mentions.extend(mentions)
        print(f"got {len(mentions)} mentions (total: {len(all_mentions)})")

        # Check for next page — _links.more is a dict with 'href' and 'params'
        links = data.get('_links', {})
        more = links.get('more') or links.get('pull')
        if not more:
            break

        if isinstance(more, dict):
            href = more.get('href', '')
            if href.startswith('/'):
                url = MENTION_API_BASE.rsplit('/api', 1)[0] + href
            else:
                url = href
            params = more.get('params', {})
        else:
            url = more
            params = {}

        page += 1

    print(f"\nTotal mentions fetched: {len(all_mentions)}")
    return all_mentions


# =============================================================================
# SOURCE NAME RESOLUTION
# =============================================================================

def resolve_facebook_page_name(page_id, cache):
    """Resolve a Facebook page ID to its page name via redirect."""
    if page_id in cache:
        return cache[page_id]

    from urllib.parse import urlparse, parse_qs, unquote

    fb_url = f'https://www.facebook.com/profile.php?id={page_id}'
    try:
        r = requests.head(
            fb_url,
            allow_redirects=True,
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'},
        )
        final_url = r.url
        parsed = urlparse(final_url)

        # Case 1: Direct vanity URL — facebook.com/PageName
        path = parsed.path.rstrip('/').split('/')[-1]
        if path and 'profile.php' not in path and f'id={page_id}' not in path and 'login' not in parsed.path:
            cache[page_id] = path
            return path

        # Case 2: Login wall redirect — facebook.com/login/?next=https%3A%2F%2Fwww.facebook.com%2FPageName%2F
        if 'login' in parsed.path:
            qs = parse_qs(parsed.query)
            next_url = qs.get('next', [None])[0]
            if next_url:
                next_url = unquote(next_url)
                next_path = urlparse(next_url).path.rstrip('/').split('/')[-1]
                if next_path and 'profile.php' not in next_path:
                    cache[page_id] = next_path
                    return next_path
    except Exception:
        pass

    cache[page_id] = None
    return None


def extract_fb_page_id(unique_id):
    """Extract Facebook page ID from unique_id format: facebook:PAGE_ID_POST_ID"""
    if not unique_id or not unique_id.startswith('facebook:'):
        return None
    parts = unique_id.replace('facebook:', '').split('_')
    return parts[0] if parts else None


def resolve_instagram_source_name(post_url, cache):
    """Resolve Instagram post URL to account name via og:title scraping."""
    if post_url in cache:
        return cache[post_url]

    try:
        r = requests.get(
            post_url,
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'},
        )
        match = re.search(
            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', r.text
        )
        if match:
            title = match.group(1)
            name_match = re.match(r'^(.+?) on Instagram:', title)
            if name_match:
                name = html.unescape(name_match.group(1))
                cache[post_url] = name
                return name
    except Exception:
        pass

    cache[post_url] = None
    return None


def extract_domain_name(url):
    """Extract domain name from URL as fallback source name."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return None


def resolve_source_names(mentions):
    """
    Resolve source_name for mentions that don't have it in the API response.
    Returns a dict mapping mention_id -> resolved_source_name.
    """
    resolved = {}
    fb_cache = {}
    ig_cache = {}

    # Collect mentions that need resolution
    fb_mentions = {}
    ig_mentions = {}
    for m in mentions:
        mid = m.get('id')
        source_type = m.get('source_type', '')

        if m.get('source_name'):
            # Already has source_name (web, blogs, forums, most IG/LinkedIn/etc.)
            resolved[mid] = m['source_name']
            continue

        if source_type == 'facebook':
            page_id = extract_fb_page_id(m.get('unique_id', ''))
            if page_id:
                fb_mentions[mid] = page_id

        elif source_type == 'instagram':
            post_url = m.get('original_url', '')
            if post_url:
                ig_mentions[mid] = post_url

        elif source_type == 'twitter':
            # Twitter: no reliable way to get profile name without X API
            # Use author_influence ID as placeholder
            ai = m.get('author_influence', {})
            if ai and ai.get('id'):
                resolved[mid] = f"twitter_user_{ai['id']}"

        elif source_type in ('news', 'images', 'videos'):
            # Fallback: extract domain from source_url
            source_url = m.get('source_url', '')
            domain = extract_domain_name(source_url)
            if domain:
                resolved[mid] = domain

    # Resolve Facebook page names in batch
    if fb_mentions:
        unique_page_ids = set(fb_mentions.values())
        print(f"\nResolving {len(unique_page_ids)} unique Facebook page IDs...")

        for i, page_id in enumerate(unique_page_ids):
            name = resolve_facebook_page_name(page_id, fb_cache)
            if name:
                print(f"  [{i+1}/{len(unique_page_ids)}] {page_id} -> {name}")
            else:
                print(f"  [{i+1}/{len(unique_page_ids)}] {page_id} -> (unresolved)")
            time.sleep(FB_RESOLVE_DELAY)

        # Map back to mention IDs
        for mid, page_id in fb_mentions.items():
            name = fb_cache.get(page_id)
            if name:
                resolved[mid] = name

        resolved_count = sum(1 for pid in unique_page_ids if fb_cache.get(pid))
        print(f"  Resolved: {resolved_count}/{len(unique_page_ids)} Facebook pages")

    # Resolve Instagram source names in batch
    if ig_mentions:
        unique_urls = set(ig_mentions.values())
        print(f"\nResolving {len(unique_urls)} unique Instagram post URLs...")

        for i, post_url in enumerate(unique_urls):
            name = resolve_instagram_source_name(post_url, ig_cache)
            short = post_url.split('/')[-2] if post_url.endswith('/') else post_url.split('/')[-1]
            if name:
                print(f"  [{i+1}/{len(unique_urls)}] {short} -> {name}")
            else:
                print(f"  [{i+1}/{len(unique_urls)}] {short} -> (unresolved)")
            time.sleep(IG_RESOLVE_DELAY)

        # Map back to mention IDs
        for mid, post_url in ig_mentions.items():
            name = ig_cache.get(post_url)
            if name:
                resolved[mid] = name

        resolved_count = sum(1 for u in unique_urls if ig_cache.get(u))
        print(f"  Resolved: {resolved_count}/{len(unique_urls)} Instagram posts")

    return resolved


# =============================================================================
# DATA EXTRACTION
# =============================================================================

def extract_mention_data(mentions, resolved_names):
    """
    Extract relevant fields from Mention API response objects.
    Returns list of dicts matching the enrichment script's expected CSV format.
    """
    rows = []
    skipped_no_name = 0

    for mention in mentions:
        mid = mention.get('id')

        # Get source_name: from API response or resolved names
        source_name = mention.get('source_name', '').strip()
        if not source_name:
            source_name = resolved_names.get(mid, '').strip()
        if not source_name:
            skipped_no_name += 1
            continue

        # Extract reach - try multiple fields
        cumulative_reach = (
            mention.get('cumulative_reach')
            or mention.get('direct_reach')
            or mention.get('domain_reach')
            or 0
        )
        try:
            cumulative_reach = int(cumulative_reach)
        except (ValueError, TypeError):
            cumulative_reach = 0

        # Extract country
        country = mention.get('country', '')

        # Extract influence score if available
        influence = mention.get('author_influence', {})
        influence_score = influence.get('score', 0) if isinstance(influence, dict) else 0

        rows.append({
            'source_name': source_name,
            'cumulative_reach': cumulative_reach,
            'country': country,
            'influence_score': influence_score,
            'source_url': mention.get('source_url', ''),
            'mention_url': mention.get('original_url', ''),
        })

    if skipped_no_name:
        print(f"  Skipped {skipped_no_name} mentions without source name")

    return rows


# =============================================================================
# OUTPUT
# =============================================================================

def save_csv(rows, source_name, alert_id, data_dir):
    """Save extracted data as CSV compatible with enrich_mentions.py"""
    today = date.today().isoformat()
    source_slug = source_name.lower().replace(' ', '_')
    output_subdir = data_dir / 'generated-outputs' / f'{source_slug}-{today}'
    output_subdir.mkdir(parents=True, exist_ok=True)

    filename = f'mentions_export_{alert_id}_{today}.csv'
    output_path = output_subdir / filename

    fieldnames = ['source_name', 'cumulative_reach', 'country',
                  'influence_score', 'source_url', 'mention_url', 'alert_name']

    # Add alert_name to each row for source detection
    for row in rows:
        row['alert_name'] = source_name

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Fetch mentions from Mention.com API')
    parser.add_argument('--alert-id', required=True, help='Mention.com alert ID')
    parser.add_argument('--since-date', help='Only fetch mentions after this date (YYYY-MM-DD)')
    parser.add_argument('--source', help='Source name override (default: auto-detect from alert)')
    parser.add_argument('--data-dir', help='Data directory for this competitor (e.g., data/hootsuite/)')

    args = parser.parse_args()

    # Set data_dir: use provided value or fall back to old structure
    if args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        # Backward compatibility
        data_dir = SKILL_DIR

    print("=" * 70)
    print("Fetch Mentions - Mention.com API")
    print("=" * 70)

    # Check credentials
    if not MENTION_TOKEN:
        print("Error: MENTION_API_TOKEN not set in environment.")
        sys.exit(1)
    if not MENTION_ACCOUNT_ID:
        print("Error: MENTION_ACCOUNT_ID not set in environment.")
        sys.exit(1)

    # Validate since_date if provided
    since_date = None
    if args.since_date:
        try:
            datetime.strptime(args.since_date, '%Y-%m-%d')
            since_date = args.since_date
            print(f"\nFiltering mentions since: {since_date}")
        except ValueError:
            print(f"Error: Invalid date format '{args.since_date}'. Use YYYY-MM-DD.")
            sys.exit(1)

    # Fetch mentions
    mentions = fetch_all_mentions(args.alert_id, since_date)

    if not mentions:
        print("\nNo mentions found. Exiting.")
        sys.exit(0)

    # Count by source type
    source_types = {}
    for m in mentions:
        st = m.get('source_type', 'unknown')
        source_types[st] = source_types.get(st, 0) + 1
    print(f"\nMentions by source type:")
    for st, count in sorted(source_types.items(), key=lambda x: -x[1]):
        print(f"  {st}: {count}")

    # Resolve source names for social mentions
    print("\nResolving source names...")
    resolved_names = resolve_source_names(mentions)
    api_names = sum(1 for m in mentions if m.get('source_name'))
    resolved_count = len(resolved_names) - api_names
    print(f"  From API: {api_names}")
    print(f"  Resolved: {resolved_count}")

    # Extract data
    print("\nExtracting mention data...")
    rows = extract_mention_data(mentions, resolved_names)
    print(f"  Extracted {len(rows)} rows with source names (out of {len(mentions)} mentions)")

    if not rows:
        print("\nNo rows with valid source names. Exiting.")
        sys.exit(0)

    # Determine source name
    source_name = args.source or f'alert_{args.alert_id}'

    # Save CSV
    output_path = save_csv(rows, source_name, args.alert_id, data_dir)

    print(f"\n{'=' * 70}")
    print(f"EXPORT COMPLETE")
    print(f"{'=' * 70}")
    print(f"Mentions fetched: {len(mentions)}")
    print(f"Rows exported: {len(rows)}")
    print(f"Output: {output_path}")
    print(f"\nNext step: Run enrichment with:")
    print(f"  python enrich_mentions.py {output_path} --source {source_name}")
    print(f"{'=' * 70}")

    return str(output_path)


if __name__ == '__main__':
    main()
