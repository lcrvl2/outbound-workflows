#!/usr/bin/env python3
"""
Analyze Metrics — Merge follower + post data, compute engagement metrics, update master.

Joins dev_fusion (followers) and harvestapi (posts) on normalized LinkedIn URL.
Outputs metrics_enriched.csv with all signal fields for sequence personalization.
Appends a snapshot row per company to master/{source}_master.csv for future growth tracking.

Field names confirmed from test_actors.py run on 5 companies:
    - dev_fusion: followerCount, companyName, url (with trailing slash)
    - harvestapi: postedAt.date (nested), engagement.likes (nested), query.targetUrl (nested)

Usage:
    python scripts/analyze_metrics.py \
        --followers raw_followers.json \
        --posts raw_posts.json \
        --input companies.csv \
        --source NAME \
        --output-dir PATH \
        [--period 90]
"""

import csv
import json
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import date, datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# =============================================================================
# CONFIGURATION — Update after running test_actors.py
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
MASTER_DIR = SKILL_DIR / 'master'

# dev_fusion field names (confirmed from test run)
FOLLOWER_FIELD = 'followerCount'
COMPANY_NAME_FIELD = 'companyName'
COMPANY_URL_FIELD = 'url'              # dev_fusion returns URL with trailing slash

# harvestapi field names (confirmed from test run — all nested)
# postedAt is a dict: {'date': '2025-12-09T20:25:05.271Z', ...}
# engagement is a dict: {'likes': 42, ...}
# query is a dict: {'targetUrl': 'https://...', ...}
POST_TIMESTAMP_NESTED = ('postedAt', 'date')
POST_LIKES_NESTED = ('engagement', 'likes')
POST_COMPANY_URL_NESTED = ('query', 'targetUrl')


# =============================================================================
# URL NORMALIZATION
# =============================================================================

def normalize_company_url(url):
    """Normalize LinkedIn company URL to canonical form for join key."""
    if not url:
        return ''
    url = url.lower().strip().rstrip('/')
    if '?' in url:
        url = url.split('?')[0]
    url = re.sub(r'https?://[a-z]{2,3}\.linkedin\.com/', 'https://www.linkedin.com/', url)
    url = re.sub(r'http://(www\.)?linkedin\.com/', 'https://www.linkedin.com/', url)
    if url.startswith('linkedin.com'):
        url = 'https://www.' + url
    return url


# =============================================================================
# CSV LOADING
# =============================================================================

def load_companies(csv_path):
    """Load all companies from input CSV, keyed by normalized linkedin_url."""
    companies = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (
                row.get('linkedin_url') or
                row.get('LinkedIn URL') or
                row.get('Company Linkedin Url') or
                row.get('Company LinkedIn URL') or
                ''
            ).strip()
            if not url:
                continue
            normalized = normalize_company_url(url)
            domain = (
                row.get('domain') or
                row.get('Website') or
                ''
            ).strip()
            companies[normalized] = {
                'linkedin_url': normalized,
                'domain': domain,
            }
    return companies


# =============================================================================
# FOLLOWER DATA — rigelbytes
# =============================================================================

def index_followers(followers_path):
    """
    Index rigelbytes items by normalized LinkedIn URL.
    Returns dict: {normalized_url: item}
    """
    if not followers_path.exists():
        print(f"  Warning: {followers_path} not found — follower data will be empty.")
        return {}

    with open(followers_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    index = {}
    for item in items:
        # Try multiple common URL field names
        raw_url = (
            item.get(COMPANY_URL_FIELD) or
            item.get('url') or
            item.get('companyUrl') or
            item.get('linkedinUrl') or
            item.get('profileUrl') or
            ''
        )
        if raw_url:
            normalized = normalize_company_url(raw_url)
            index[normalized] = item

    print(f"  Followers indexed: {len(index)} companies")
    return index


def get_follower_count(item):
    """Extract follower count from a rigelbytes item."""
    if not item:
        return None
    # Try multiple common field names — update FOLLOWER_FIELD after test_actors.py
    for field in [FOLLOWER_FIELD, 'followersCount', 'followerCount', 'followers',
                  'numberOfFollowers', 'follower_count']:
        val = item.get(field)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return None


def get_company_name(item):
    """Extract company name from a rigelbytes item."""
    if not item:
        return ''
    for field in [COMPANY_NAME_FIELD, 'name', 'companyName', 'organizationName', 'title']:
        val = item.get(field)
        if val:
            return str(val).strip()
    return ''


# =============================================================================
# POST DATA — harvestapi
# =============================================================================

def index_posts(posts_path):
    """
    Index harvestapi post items by normalized company URL.
    Returns dict: {normalized_url: [post, post, ...]}
    """
    if not posts_path.exists():
        print(f"  Warning: {posts_path} not found — post data will be empty.")
        return {}

    with open(posts_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    index = {}
    for post in items:
        # query.targetUrl is the confirmed field (nested dict)
        query = post.get('query') or {}
        raw_url = (
            query.get('targetUrl') or
            post.get('companyUrl') or
            post.get('authorUrl') or
            post.get('companyLinkedInUrl') or
            ''
        )
        if raw_url:
            normalized = normalize_company_url(raw_url)
            index.setdefault(normalized, []).append(post)

    company_count = len(index)
    total_posts = sum(len(v) for v in index.values())
    print(f"  Posts indexed: {total_posts} posts across {company_count} companies")
    return index


def parse_post_timestamp(post):
    """Parse post timestamp from harvestapi item. Returns datetime or None."""
    # postedAt is a nested dict: {'date': '2025-12-09T20:25:05.271Z', ...}
    posted_at = post.get('postedAt') or {}
    raw = (
        posted_at.get('date') or
        post.get('publishedAt') or
        post.get('createdAt') or
        post.get('date') or
        ''
    )
    if not raw:
        return None

    s = str(raw).strip()

    # ISO format with milliseconds and Z suffix: 2025-12-09T20:25:05.271Z
    # Strip Z and pad microseconds to 6 digits for %f
    if 'T' in s:
        s_clean = s.rstrip('Z').rstrip('+00:00')
        if '.' in s_clean:
            parts = s_clean.split('.')
            s_padded = parts[0] + '.' + parts[1].ljust(6, '0')
            try:
                return datetime.strptime(s_padded, '%Y-%m-%dT%H:%M:%S.%f')
            except (ValueError, TypeError):
                pass
        try:
            return datetime.strptime(s_clean[:19], '%Y-%m-%dT%H:%M:%S')
        except (ValueError, TypeError):
            pass

    # Plain date
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d')
    except (ValueError, TypeError):
        pass

    # Unix timestamp (milliseconds)
    try:
        ts = int(s)
        if ts > 1e10:  # milliseconds
            ts //= 1000
        return datetime.fromtimestamp(ts)
    except (ValueError, TypeError):
        pass

    return None


def compute_post_metrics(posts, period_days=90):
    """
    Compute post frequency metrics for a company's posts.
    Returns dict of metrics.
    """
    if not posts:
        return {
            'posts_last_30d': 0,
            'posts_last_90d': 0,
            'avg_posts_per_week': 0.0,
            'posting_frequency': 'inactive (0 posts/90d)',
            'last_post_date': None,
            'days_since_last_post': None,
            'top_post_likes': None,
        }

    today = date.today()
    cutoff_30d = datetime.combine(today - timedelta(days=30), datetime.min.time())
    cutoff_90d = datetime.combine(today - timedelta(days=90), datetime.min.time())

    posts_30d = 0
    posts_90d = 0
    last_post_dt = None
    max_likes = None

    for post in posts:
        dt = parse_post_timestamp(post)

        if dt:
            if dt >= cutoff_90d:
                posts_90d += 1
            if dt >= cutoff_30d:
                posts_30d += 1
            if last_post_dt is None or dt > last_post_dt:
                last_post_dt = dt

        # Likes — engagement.likes is confirmed nested field
        engagement = post.get('engagement') or {}
        val = (
            engagement.get('likes') or
            post.get('likesCount') or
            post.get('likes') or
            post.get('reactions')
        )
        if val is not None:
            try:
                likes = int(val)
                if max_likes is None or likes > max_likes:
                    max_likes = likes
            except (ValueError, TypeError):
                pass

    avg_per_week = round(posts_90d / 13.0, 2)  # 90 days ≈ 13 weeks
    last_post_date = last_post_dt.date().isoformat() if last_post_dt else None
    days_since = (today - last_post_dt.date()).days if last_post_dt else None

    if posts_90d == 0:
        posting_frequency = 'inactive (0 posts/90d)'
    elif avg_per_week < 0.5:
        posting_frequency = 'rare (<0.5/wk)'
    elif avg_per_week < 1.0:
        posting_frequency = 'occasional (0.5-1/wk)'
    elif avg_per_week < 2.0:
        posting_frequency = 'regular (1-2/wk)'
    elif avg_per_week < 4.0:
        posting_frequency = 'active (2-4/wk)'
    else:
        posting_frequency = 'very active (4+/wk)'

    return {
        'posts_last_30d': posts_30d,
        'posts_last_90d': posts_90d,
        'avg_posts_per_week': avg_per_week,
        'posting_frequency': posting_frequency,
        'last_post_date': last_post_date,
        'days_since_last_post': days_since,
        'top_post_likes': max_likes,
    }


# =============================================================================
# MASTER FILE
# =============================================================================

def get_master_path(source):
    normalized = re.sub(r'[^\w\s-]', '', source.lower())
    normalized = re.sub(r'\s+', '_', normalized)
    return MASTER_DIR / f'{normalized}_master.csv'


MASTER_FIELDS = [
    'linkedin_url', 'domain', 'company_name', 'follower_count',
    'posts_last_30d', 'posts_last_90d', 'avg_posts_per_week', 'snapshot_date',
]


def load_master(source):
    """
    Load master file, return:
    - existing_rows: list of all historical rows
    - prev_followers: dict {linkedin_url: follower_count} from most recent snapshot
    """
    master_path = get_master_path(source)
    existing_rows = []
    prev_followers = {}

    if not master_path.exists():
        return existing_rows, prev_followers

    with open(master_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)

    # Build prev_followers from the most recent snapshot per URL
    by_url = {}
    for row in existing_rows:
        url = row.get('linkedin_url', '')
        snap_date = row.get('snapshot_date', '')
        if url:
            if url not in by_url or snap_date > by_url[url]['snapshot_date']:
                by_url[url] = row

    for url, row in by_url.items():
        try:
            prev_followers[url] = int(row['follower_count'])
        except (ValueError, TypeError, KeyError):
            pass

    return existing_rows, prev_followers


def update_master(source, new_rows, existing_rows):
    """
    Append new snapshot rows to master file.
    Replaces any existing row with same (linkedin_url, snapshot_date).
    """
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    master_path = get_master_path(source)
    today = date.today().isoformat()

    # Remove today's existing rows (re-run same day)
    today_urls = {r['linkedin_url'] for r in new_rows}
    filtered = [
        r for r in existing_rows
        if not (r.get('snapshot_date') == today and r.get('linkedin_url') in today_urls)
    ]

    all_rows = filtered + new_rows

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    return master_path


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def analyze(companies, follower_index, post_index, prev_followers, period_days=90):
    """
    Merge follower + post data for each company and compute all metrics.
    Returns (enriched_rows, master_rows).
    """
    today = date.today().isoformat()
    enriched_rows = []
    master_rows = []

    for url, company in companies.items():
        domain = company['domain']

        # Follower data from rigelbytes
        follower_item = follower_index.get(url)
        follower_count = get_follower_count(follower_item)
        company_name = get_company_name(follower_item)

        # Post data from harvestapi
        posts = post_index.get(url, [])
        metrics = compute_post_metrics(posts, period_days=period_days)

        # Growth vs previous snapshot
        prev = prev_followers.get(url)
        if prev is not None and follower_count is not None:
            follower_growth = follower_count - prev
            follower_growth_pct = round(follower_growth / prev * 100, 2) if prev > 0 else None
        else:
            follower_growth = None
            follower_growth_pct = None

        enriched_rows.append({
            'linkedin_url': url,
            'domain': domain,
            'company_name': company_name,
            'follower_count': follower_count if follower_count is not None else '',
            'posts_last_30d': metrics['posts_last_30d'],
            'posts_last_90d': metrics['posts_last_90d'],
            'avg_posts_per_week': metrics['avg_posts_per_week'],
            'posting_frequency': metrics['posting_frequency'],
            'last_post_date': metrics['last_post_date'] or '',
            'days_since_last_post': metrics['days_since_last_post'] if metrics['days_since_last_post'] is not None else '',
            'top_post_likes': metrics['top_post_likes'] if metrics['top_post_likes'] is not None else '',
            'follower_count_prev': prev if prev is not None else '',
            'follower_growth': follower_growth if follower_growth is not None else '',
            'follower_growth_pct': follower_growth_pct if follower_growth_pct is not None else '',
            'snapshot_date': today,
        })

        master_rows.append({
            'linkedin_url': url,
            'domain': domain,
            'company_name': company_name,
            'follower_count': follower_count if follower_count is not None else '',
            'posts_last_30d': metrics['posts_last_30d'],
            'posts_last_90d': metrics['posts_last_90d'],
            'avg_posts_per_week': metrics['avg_posts_per_week'],
            'snapshot_date': today,
        })

    return enriched_rows, master_rows


ENRICHED_FIELDS = [
    'linkedin_url', 'domain', 'company_name',
    'follower_count', 'follower_count_prev', 'follower_growth', 'follower_growth_pct',
    'posts_last_30d', 'posts_last_90d', 'avg_posts_per_week', 'posting_frequency',
    'last_post_date', 'days_since_last_post', 'top_post_likes',
    'snapshot_date',
]


def write_enriched_csv(output_path, rows):
    """Write enriched metrics CSV."""
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=ENRICHED_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Merge follower + post data, compute metrics, update master'
    )
    parser.add_argument('--followers', required=True, help='Path to raw_followers.json')
    parser.add_argument('--posts', required=True, help='Path to raw_posts.json')
    parser.add_argument('--input', required=True, help='Original input CSV (linkedin_url + domain)')
    parser.add_argument('--source', required=True, help='Source name for master file')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--period', type=int, default=90,
                        help='Analysis period in days (default: 90)')
    args = parser.parse_args()

    print("=" * 70)
    print("ANALYZE METRICS")
    print("=" * 70)

    followers_path = Path(args.followers)
    posts_path = Path(args.posts)
    csv_path = Path(args.input)
    output_dir = Path(args.output_dir)

    for p in [csv_path]:
        if not p.exists():
            print(f"Error: File not found: {p}")
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'metrics_enriched.csv'

    # Load
    print("\nLoading data...")
    companies = load_companies(str(csv_path))
    print(f"  Companies in input CSV: {len(companies)}")

    follower_index = index_followers(followers_path)
    post_index = index_posts(posts_path)

    existing_master_rows, prev_followers = load_master(args.source)
    if prev_followers:
        print(f"  Previous snapshot found: {len(prev_followers)} companies with prior follower counts")
    else:
        print(f"  No previous snapshot — this is the baseline run (growth fields will be empty)")

    # Analyze
    print(f"\nComputing metrics (period: {args.period} days)...")
    enriched_rows, master_rows = analyze(
        companies, follower_index, post_index, prev_followers, period_days=args.period
    )

    # Write output
    write_enriched_csv(output_path, enriched_rows)
    print(f"\nWrote: {output_path} ({len(enriched_rows)} rows)")

    # Update master
    master_path = update_master(args.source, master_rows, existing_master_rows)
    print(f"Updated master: {master_path}")

    # Summary
    with_followers = sum(1 for r in enriched_rows if r['follower_count'] != '')
    with_posts = sum(1 for r in enriched_rows if r['posts_last_90d'] > 0)
    no_data = sum(1 for r in enriched_rows if r['follower_count'] == '' and r['posts_last_90d'] == 0)

    print(f"\n{'=' * 70}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total companies:      {len(enriched_rows)}")
    print(f"With follower count:  {with_followers}")
    print(f"With posts (90d):     {with_posts}")
    print(f"No data at all:       {no_data}")
    print(f"Output:               {output_path}")

    if no_data > 0:
        print(f"\nNote: {no_data} companies had no data from either actor.")
        print("  Check that linkedin_url values in your CSV match what the actors expect.")
        print("  Run test_actors.py to inspect raw output field names.")

    if not prev_followers:
        print(f"\nBaseline snapshot saved to master.")
        print(f"Run again later to get follower_growth and follower_growth_pct.")


if __name__ == '__main__':
    main()
