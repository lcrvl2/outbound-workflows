#!/usr/bin/env python3
"""
Run Pipeline — Orchestrate LinkedIn company analytics (followers + posts + metrics).

Steps:
  1. scrape_followers.py — rigelbytes actor, follower counts ($0.01/company, fixed)
  2. scrape_posts.py     — harvestapi actor, 3-month post history (~$0.002/post, variable)
  3. analyze_metrics.py  — merge, compute metrics, update master file

Usage:
    python scripts/run_pipeline.py \
        --input companies.csv \
        --source "q1-2026" \
        [--period 90] \
        [--batch-size 50] \
        [--skip-followers] [--input-followers PATH] \
        [--skip-posts] [--input-posts PATH] \
        [--yes]

Examples:
    # Full run
    python scripts/run_pipeline.py --input companies.csv --source li_analytics_q1_2026

    # Test on 5 companies first (run test_actors.py instead for field audit)
    python scripts/run_pipeline.py --input test_5.csv --source test_5

    # Resume after followers done (skip re-spending)
    python scripts/run_pipeline.py --input companies.csv --source q1 \\
        --skip-followers --input-followers generated-outputs/q1-2026-02-18/raw_followers.json

    # Auto-confirm (for scheduled runs)
    python scripts/run_pipeline.py --input companies.csv --source q1 --yes
"""

import subprocess
import sys
import re
import argparse
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
SCRIPTS_DIR = Path(__file__).parent
OUTPUT_DIR = SKILL_DIR / 'generated-outputs'

COST_PER_COMPANY_FOLLOWERS = 0.01
COST_PER_POST = 0.002
POSTS_LOW = 3
POSTS_HIGH = 10


# =============================================================================
# HELPERS
# =============================================================================

def normalize_source_name(source):
    if not source:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_output_dir(source):
    source_slug = normalize_source_name(source)
    today = date.today().isoformat()
    return OUTPUT_DIR / f'{source_slug}-{today}'


def count_companies(csv_path):
    """Count rows with a linkedin_url in the input CSV."""
    count = 0
    try:
        import csv
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = (row.get('linkedin_url') or row.get('LinkedIn URL') or '').strip()
                if url:
                    count += 1
    except Exception:
        pass
    return count


# =============================================================================
# STEP RUNNERS
# =============================================================================

def run_scrape_followers(csv_path, output_dir, batch_size, auto_confirm):
    """Step 1: Scrape follower counts via rigelbytes."""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: SCRAPE FOLLOWERS (rigelbytes)")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'scrape_followers.py'),
        '--input', csv_path,
        '--output-dir', str(output_dir),
        '--batch-size', str(batch_size),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error: scrape_followers.py exited with code {result.returncode}")
        return None

    output = output_dir / 'raw_followers.json'
    return str(output) if output.exists() else None


def run_scrape_posts(csv_path, output_dir, batch_size, auto_confirm):
    """Step 2: Scrape posts via harvestapi."""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 2: SCRAPE POSTS (harvestapi)")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'scrape_posts.py'),
        '--input', csv_path,
        '--output-dir', str(output_dir),
        '--batch-size', str(batch_size),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error: scrape_posts.py exited with code {result.returncode}")
        return None

    output = output_dir / 'raw_posts.json'
    return str(output) if output.exists() else None


def run_analyze(followers_path, posts_path, csv_path, source, output_dir, period):
    """Step 3: Analyze and compute metrics."""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 3: ANALYZE METRICS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'analyze_metrics.py'),
        '--followers', followers_path,
        '--posts', posts_path,
        '--input', csv_path,
        '--source', source,
        '--output-dir', str(output_dir),
        '--period', str(period),
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error: analyze_metrics.py exited with code {result.returncode}")
        return False

    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='LinkedIn company analytics pipeline (followers + posts + metrics)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python scripts/run_pipeline.py --input companies.csv --source li_analytics_q1_2026

  # Resume: followers already done, skip re-spending
  python scripts/run_pipeline.py --input companies.csv --source q1 \\
      --skip-followers --input-followers generated-outputs/q1-2026-02-18/raw_followers.json

  # Skip posts too (only re-run analysis)
  python scripts/run_pipeline.py --input companies.csv --source q1 \\
      --skip-followers --input-followers PATH \\
      --skip-posts --input-posts PATH
        """,
    )

    parser.add_argument('--input', required=True, help='CSV with linkedin_url column')
    parser.add_argument('--source', required=True,
                        help='Source name for this run (e.g., li_analytics_q1_2026)')
    parser.add_argument('--period', type=int, default=90,
                        help='Analysis period in days (default: 90)')
    parser.add_argument('--batch-size', type=int, default=50,
                        help='URLs per actor run (default: 50)')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip all confirmation prompts')

    # Skip flags
    parser.add_argument('--skip-followers', action='store_true',
                        help='Skip follower scraping (use --input-followers)')
    parser.add_argument('--skip-posts', action='store_true',
                        help='Skip post scraping (use --input-posts)')
    parser.add_argument('--input-followers', default=None,
                        help='Path to existing raw_followers.json (with --skip-followers)')
    parser.add_argument('--input-posts', default=None,
                        help='Path to existing raw_posts.json (with --skip-posts)')

    args = parser.parse_args()

    # Validate
    csv_path = Path(args.input)
    if not csv_path.exists():
        print(f"Error: Input CSV not found: {csv_path}")
        sys.exit(1)

    if args.skip_followers and not args.input_followers:
        print("Error: --input-followers is required when using --skip-followers")
        sys.exit(1)

    if args.skip_posts and not args.input_posts:
        print("Error: --input-posts is required when using --skip-posts")
        sys.exit(1)

    if args.input_followers and not Path(args.input_followers).exists():
        print(f"Error: raw_followers.json not found: {args.input_followers}")
        sys.exit(1)

    if args.input_posts and not Path(args.input_posts).exists():
        print(f"Error: raw_posts.json not found: {args.input_posts}")
        sys.exit(1)

    # Count companies for cost preview
    n_companies = count_companies(str(csv_path))

    # Output dir
    output_dir = get_output_dir(args.source)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ==========================================================================
    # Dry-run Preview
    # ==========================================================================
    print("=" * 70)
    print("LINKEDIN COMPANY ANALYTICS PIPELINE")
    print("=" * 70)
    print(f"\nSource:    {args.source}")
    print(f"Input:     {csv_path} ({n_companies} companies)")
    print(f"Period:    {args.period} days")
    print(f"Output:    {output_dir}")

    steps = []
    if not args.skip_followers:
        steps.append('Scrape followers (rigelbytes)')
    if not args.skip_posts:
        steps.append('Scrape posts (harvestapi)')
    steps.append('Analyze metrics')
    print(f"Steps:     {' → '.join(steps)}")

    print(f"\nCOST ESTIMATE")
    if not args.skip_followers:
        cost_followers = n_companies * COST_PER_COMPANY_FOLLOWERS
        print(f"  rigelbytes (follower count):")
        print(f"    {n_companies} × ${COST_PER_COMPANY_FOLLOWERS} = ${cost_followers:.2f} (fixed)")
    else:
        print(f"  rigelbytes: SKIPPED (using {args.input_followers})")

    if not args.skip_posts:
        cost_low = n_companies * POSTS_LOW * COST_PER_POST
        cost_high = n_companies * POSTS_HIGH * COST_PER_POST
        print(f"  harvestapi (posts, {args.period} days):")
        print(f"    {n_companies} companies × {POSTS_LOW}–{POSTS_HIGH} posts × ${COST_PER_POST}/post")
        print(f"    Low estimate: ${cost_low:.2f} | High estimate: ${cost_high:.2f}")
        print(f"    (active companies cost more — exact cost known after run)")
    else:
        print(f"  harvestapi: SKIPPED (using {args.input_posts})")

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    # ==========================================================================
    # Step 1: Scrape followers
    # ==========================================================================
    if args.skip_followers:
        followers_path = args.input_followers
        print(f"\nSkipping follower scraping. Using: {followers_path}")
    else:
        followers_path = run_scrape_followers(
            str(csv_path), output_dir, args.batch_size, args.yes
        )
        if not followers_path:
            print("\nPipeline aborted at follower scraping step.")
            sys.exit(1)

    # ==========================================================================
    # Step 2: Scrape posts
    # ==========================================================================
    if args.skip_posts:
        posts_path = args.input_posts
        print(f"\nSkipping post scraping. Using: {posts_path}")
    else:
        posts_path = run_scrape_posts(
            str(csv_path), output_dir, args.batch_size, args.yes
        )
        if not posts_path:
            print("\nPipeline aborted at post scraping step.")
            sys.exit(1)

    # ==========================================================================
    # Step 3: Analyze metrics
    # ==========================================================================
    success = run_analyze(
        followers_path, posts_path,
        str(csv_path), args.source, output_dir, args.period
    )

    if not success:
        print("\nPipeline aborted at analysis step.")
        sys.exit(1)

    # ==========================================================================
    # Done
    # ==========================================================================
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Output directory: {output_dir}")
    print(f"  raw_followers.json    — rigelbytes raw output")
    print(f"  raw_posts.json        — harvestapi raw output")
    print(f"  metrics_enriched.csv  — final deliverable (follower count + post metrics)")
    print(f"Master: master/{normalize_source_name(args.source)}_master.csv")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
