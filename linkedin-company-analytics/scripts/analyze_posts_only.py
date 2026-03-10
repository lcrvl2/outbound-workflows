#!/usr/bin/env python3
"""
Analyze Posts Only — Compute post frequency metrics without follower data.

Outputs a CSV with posting activity classification for sequence personalization.

Usage:
    python scripts/analyze_posts_only.py \
        --posts raw_posts.json \
        --input companies.csv \
        --source NAME \
        --output-dir PATH \
        [--period 90]
"""

import csv
import json
import sys
import re
import argparse
from pathlib import Path
from datetime import date, datetime, timedelta
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
MASTER_DIR = SKILL_DIR / 'master'

# harvestapi field names (nested)
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
                row.get('company_name') or
                ''
            ).strip()
            companies[normalized] = {
                'linkedin_url': url,
                'domain': domain,
                'company_name': row.get('company_name', '').strip(),
            }
    return companies


# =============================================================================
# POST DATA
# =============================================================================

def index_posts(posts_path):
    """Load posts JSON, group by normalized company URL."""
    post_index = defaultdict(list)

    with open(posts_path, 'r', encoding='utf-8') as f:
        posts = json.load(f)

    for post in posts:
        # Extract company URL from nested query.targetUrl
        query_dict = post.get(POST_COMPANY_URL_NESTED[0], {})
        company_url = query_dict.get(POST_COMPANY_URL_NESTED[1], '')

        if not company_url:
            continue

        normalized = normalize_company_url(company_url)
        post_index[normalized].append(post)

    return post_index


def parse_post_timestamp(post):
    """Extract timestamp from harvestapi nested structure."""
    try:
        posted_at_dict = post.get(POST_TIMESTAMP_NESTED[0], {})
        timestamp_str = posted_at_dict.get(POST_TIMESTAMP_NESTED[1], '')

        if not timestamp_str:
            return None

        # ISO format: 2025-12-09T20:25:05.271Z
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.date()
    except Exception:
        return None


def compute_post_metrics(posts, period_days=90):
    """
    Compute posting metrics from list of posts.

    Returns dict with:
        - posts_total: Total posts in period
        - posts_last_30d: Posts in last 30 days
        - posts_last_60d: Posts in last 60 days
        - posts_last_90d: Posts in last 90 days
        - avg_posts_per_week: posts_last_90d / 13
        - days_since_last_post: Days since most recent post (or None)
        - top_post_likes: Max likes on any post
        - posting_range: Classification (0-5, 6 categories)
        - posting_range_label: Human-readable label
    """
    if not posts:
        return {
            'posts_total': 0,
            'posts_last_30d': 0,
            'posts_last_60d': 0,
            'posts_last_90d': 0,
            'avg_posts_per_week': 0.0,
            'days_since_last_post': None,
            'top_post_likes': 0,
            'last_post_date': None,
            'posting_range': 0,
            'posting_range_label': 'Inactive (0 posts/90d)',
        }

    today = date.today()
    cutoff_90 = today - timedelta(days=90)
    cutoff_60 = today - timedelta(days=60)
    cutoff_30 = today - timedelta(days=30)

    valid_posts = []
    for post in posts:
        post_date = parse_post_timestamp(post)
        if post_date and post_date >= cutoff_90:
            valid_posts.append({'date': post_date, 'post': post})

    # Sort by date descending
    valid_posts.sort(key=lambda x: x['date'], reverse=True)

    # Count by period
    posts_last_30d = sum(1 for p in valid_posts if p['date'] >= cutoff_30)
    posts_last_60d = sum(1 for p in valid_posts if p['date'] >= cutoff_60)
    posts_last_90d = len(valid_posts)

    # Days since last post
    if valid_posts:
        last_post_date = valid_posts[0]['date']
        days_since_last_post = (today - last_post_date).days
    else:
        last_post_date = None
        days_since_last_post = None

    # Top likes
    top_likes = 0
    for p in valid_posts:
        engagement = p['post'].get(POST_LIKES_NESTED[0], {})
        likes = engagement.get(POST_LIKES_NESTED[1], 0)
        if likes and likes > top_likes:
            top_likes = likes

    # Average posts per week (last 90 days = ~13 weeks)
    avg_posts_per_week = round(posts_last_90d / 13.0, 2)

    # Posting range classification
    # Based on posts_last_90d (adjust thresholds as needed)
    if posts_last_90d == 0:
        posting_range = 0
        posting_range_label = 'Inactive (0 posts/90d)'
    elif posts_last_90d <= 3:
        posting_range = 1
        posting_range_label = 'Very Low (1-3 posts/90d)'
    elif posts_last_90d <= 10:
        posting_range = 2
        posting_range_label = 'Low (4-10 posts/90d)'
    elif posts_last_90d <= 25:
        posting_range = 3
        posting_range_label = 'Medium (11-25 posts/90d)'
    elif posts_last_90d <= 50:
        posting_range = 4
        posting_range_label = 'High (26-50 posts/90d)'
    else:
        posting_range = 5
        posting_range_label = 'Very High (50+ posts/90d)'

    return {
        'posts_total': posts_last_90d,
        'posts_last_30d': posts_last_30d,
        'posts_last_60d': posts_last_60d,
        'posts_last_90d': posts_last_90d,
        'avg_posts_per_week': avg_posts_per_week,
        'days_since_last_post': days_since_last_post,
        'last_post_date': last_post_date.isoformat() if last_post_date else None,
        'top_post_likes': top_likes,
        'posting_range': posting_range,
        'posting_range_label': posting_range_label,
    }


# =============================================================================
# ANALYSIS
# =============================================================================

def analyze(companies, post_index, period_days=90):
    """Join companies with post data, compute metrics."""
    rows = []

    for normalized_url, company in companies.items():
        posts = post_index.get(normalized_url, [])
        metrics = compute_post_metrics(posts, period_days)

        row = {
            'linkedin_url': company['linkedin_url'],
            'domain': company['domain'],
            'company_name': company['company_name'],
            'posts_total': metrics['posts_total'],
            'posts_last_30d': metrics['posts_last_30d'],
            'posts_last_60d': metrics['posts_last_60d'],
            'posts_last_90d': metrics['posts_last_90d'],
            'avg_posts_per_week': metrics['avg_posts_per_week'],
            'days_since_last_post': metrics['days_since_last_post'] or '',
            'last_post_date': metrics['last_post_date'] or '',
            'top_post_likes': metrics['top_post_likes'],
            'posting_range': metrics['posting_range'],
            'posting_range_label': metrics['posting_range_label'],
        }

        rows.append(row)

    return rows


# =============================================================================
# OUTPUT
# =============================================================================

def write_csv(output_path, rows):
    """Write enriched CSV."""
    fieldnames = [
        'linkedin_url',
        'domain',
        'company_name',
        'posting_range',
        'posting_range_label',
        'posts_total',
        'posts_last_90d',
        'posts_last_60d',
        'posts_last_30d',
        'avg_posts_per_week',
        'days_since_last_post',
        'last_post_date',
        'top_post_likes',
    ]

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Wrote {len(rows)} companies to: {output_path}")


def print_summary(rows):
    """Print posting range distribution."""
    from collections import Counter

    range_counts = Counter(row['posting_range'] for row in rows)

    print("\nPosting Range Distribution:")
    print("-" * 60)
    for i in range(6):
        count = range_counts.get(i, 0)
        pct = (count / len(rows) * 100) if rows else 0
        label = {
            0: 'Inactive (0)',
            1: 'Very Low (1-3)',
            2: 'Low (4-10)',
            3: 'Medium (11-25)',
            4: 'High (26-50)',
            5: 'Very High (50+)',
        }[i]
        print(f"  Range {i} ({label:25s}): {count:4d} companies ({pct:5.1f}%)")
    print("-" * 60)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Analyze LinkedIn post frequency without follower data'
    )

    parser.add_argument('--posts', required=True, help='Path to raw_posts.json')
    parser.add_argument('--input', required=True, help='CSV with linkedin_url column')
    parser.add_argument('--source', required=True, help='Source name')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--period', type=int, default=90, help='Analysis period in days')

    args = parser.parse_args()

    # Validate
    posts_path = Path(args.posts)
    csv_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not posts_path.exists():
        print(f"Error: posts file not found: {posts_path}")
        sys.exit(1)

    if not csv_path.exists():
        print(f"Error: input CSV not found: {csv_path}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("ANALYZE POST FREQUENCY (posts-only mode)")
    print("=" * 70)
    print(f"Posts:  {posts_path}")
    print(f"Input:  {csv_path}")
    print(f"Period: {args.period} days")
    print(f"Output: {output_dir}")
    print()

    # Load
    print("Loading companies...")
    companies = load_companies(csv_path)
    print(f"✓ Loaded {len(companies)} companies from CSV")

    print("Indexing posts...")
    post_index = index_posts(posts_path)
    total_posts = sum(len(posts) for posts in post_index.values())
    print(f"✓ Indexed {total_posts} posts for {len(post_index)} companies")

    # Analyze
    print("Computing metrics...")
    rows = analyze(companies, post_index, args.period)
    print(f"✓ Analyzed {len(rows)} companies")

    # Write
    output_path = output_dir / 'posts_frequency.csv'
    write_csv(output_path, rows)

    # Summary
    print_summary(rows)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"Output: {output_path}")
    print("=" * 70)


if __name__ == '__main__':
    main()
