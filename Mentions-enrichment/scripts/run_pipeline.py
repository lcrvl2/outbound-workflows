#!/usr/bin/env python3
"""
Run Pipeline - End-to-end mentions enrichment automation.

Orchestrates the full flow:
1. Fetch mentions from Mention.com API
2. Enrich company domains via DataForSEO
3. Import to Apollo, filter by employee count + exclude current clients
4. Generate unqualified list (had reach but didn't pass Apollo filters)
5. Clean up generated-outputs/

Usage:
    python run_pipeline.py --alert-id ALERT_ID --source NAME --data-dir PATH [options]

Options:
    --since-date YYYY-MM-DD    Only fetch mentions after this date
    --threshold N              Minimum reach threshold (default: 10000)
    --min-employees N          Minimum employee count filter (default: 200)
    --yes                      Skip all confirmation prompts
    --skip-fetch               Skip Mention.com fetch (provide --input-csv instead)
    --skip-apollo              Skip Apollo import/filter step
    --input-csv PATH           Use existing CSV instead of fetching from Mention
"""

import csv
import json
import subprocess
import sys
import os
import shutil
import argparse
from pathlib import Path
from datetime import date, datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent


# =============================================================================
# HELPERS
# =============================================================================

def find_output_csv(data_dir, source, glob_pattern):
    """Find a CSV in today's generated-outputs directory by glob pattern."""
    source_slug = source.lower().replace(' ', '_')
    today = date.today().isoformat()
    output_subdir = data_dir / 'generated-outputs' / f'{source_slug}-{today}'
    if output_subdir.exists():
        csvs = sorted(output_subdir.glob(glob_pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if csvs:
            return str(csvs[0])
    return None


def count_csv_rows(csv_path):
    """Count data rows in a CSV file (excluding header)."""
    if not csv_path or not Path(csv_path).exists():
        return 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        return sum(1 for _ in csv.reader(f)) - 1  # subtract header


# =============================================================================
# STEP RUNNERS
# =============================================================================

def run_fetch_mentions(alert_id, source, data_dir, since_date=None):
    """Step 1: Fetch mentions from Mention.com API"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: FETCH MENTIONS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'fetch_mentions.py'),
        '--alert-id', str(alert_id),
        '--source', source,
        '--data-dir', str(data_dir),
    ]
    if since_date:
        cmd.extend(['--since-date', since_date])

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: fetch_mentions.py exited with code {result.returncode}")
        return None

    # Find the output CSV by glob (reliable — no stdout parsing)
    csv_path = find_output_csv(data_dir, source, 'mentions_export_*.csv')
    if not csv_path:
        print("Error: Could not find fetch output CSV")
    return csv_path


def run_enrichment(input_csv, source, data_dir, threshold, auto_confirm=False):
    """Step 2: Enrich company domains via DataForSEO"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 2: DOMAIN ENRICHMENT")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'enrich_mentions.py'),
        input_csv,
        '--source', source,
        '--data-dir', str(data_dir),
        '--threshold', str(threshold),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: enrich_mentions.py exited with code {result.returncode}")
        return None

    # Find the Apollo import CSV by glob
    csv_path = find_output_csv(data_dir, source, 'apollo_import_*.csv')
    if not csv_path:
        print("Warning: Could not find enrichment output CSV")
    return csv_path


def run_apollo_pipeline(enriched_csv, source, data_dir, min_employees, auto_confirm=False):
    """Step 3: Import to Apollo, filter, save"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 3: APOLLO IMPORT & FILTER")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'apollo_pipeline.py'),
        enriched_csv,
        '--source', source,
        '--data-dir', str(data_dir),
        '--min-employees', str(min_employees),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: apollo_pipeline.py exited with code {result.returncode}")
        return False

    return True


def run_generate_unqualified(source, data_dir, auto_confirm=False):
    """Step 4: Generate unqualified list (had reach but didn't pass Apollo filters)"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 4: GENERATE UNQUALIFIED LIST")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'generate_unqualified.py'),
        '--source', source,
        '--data-dir', str(data_dir),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Warning: generate_unqualified.py exited with code {result.returncode}")
        return False

    return True


def cleanup_outputs(source, data_dir):
    """Step 5: Clean up generated-outputs/ for this run"""
    source_slug = source.lower().replace(' ', '_')
    today = date.today().isoformat()
    output_subdir = data_dir / 'generated-outputs' / f'{source_slug}-{today}'

    if output_subdir.exists():
        print(f"\nCleaning up: {output_subdir}")
        shutil.rmtree(output_subdir)
        print("  Done.")
    else:
        print(f"\nNo output directory to clean: {output_subdir}")


# =============================================================================
# RUN STATS
# =============================================================================

def save_run_stats(source, data_dir, stats):
    """Append run stats to logs/run_history.jsonl (one JSON line per run)."""
    logs_dir = SKILL_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)
    stats_file = logs_dir / 'run_history.jsonl'

    entry = {
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'data_dir': str(data_dir),
        **stats,
    }

    with open(stats_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')

    print(f"\nRun stats saved to: {stats_file}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='End-to-end mentions enrichment pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline with an alert
  python run_pipeline.py --alert-id 12345 --source hootsuite --data-dir data/hootsuite/

  # Skip fetch, use existing CSV
  python run_pipeline.py --skip-fetch --input-csv export.csv --source hootsuite --data-dir data/hootsuite/

  # Skip Apollo step (enrichment only)
  python run_pipeline.py --alert-id 12345 --source hootsuite --data-dir data/hootsuite/ --skip-apollo

  # Auto-confirm for cron (no interactive prompts)
  python run_pipeline.py --alert-id 12345 --source hootsuite --data-dir data/hootsuite/ --yes
        """,
    )
    parser.add_argument('--alert-id', help='Mention.com alert ID (required unless --skip-fetch)')
    parser.add_argument('--source', required=True, help='Source name (e.g., hootsuite)')
    parser.add_argument('--data-dir', required=True, help='Data directory for this competitor (e.g., data/hootsuite/)')
    parser.add_argument('--since-date', help='Only fetch mentions after this date (YYYY-MM-DD)')
    parser.add_argument('--threshold', type=int, default=10000,
                        help='Minimum reach threshold (default: 10000)')
    parser.add_argument('--min-employees', type=int, default=200,
                        help='Minimum employee count for Apollo filter (default: 200)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip all confirmation prompts')
    parser.add_argument('--skip-fetch', action='store_true',
                        help='Skip Mention.com fetch (use --input-csv)')
    parser.add_argument('--skip-apollo', action='store_true',
                        help='Skip Apollo import/filter step')
    parser.add_argument('--input-csv', help='Input CSV path (use with --skip-fetch)')
    parser.add_argument('--no-cleanup', action='store_true',
                        help='Do not delete generated-outputs after completion')

    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    run_stats = {'since_date': args.since_date, 'threshold': args.threshold, 'min_employees': args.min_employees}

    # Validate args
    if not args.skip_fetch and not args.alert_id:
        print("Error: --alert-id is required unless using --skip-fetch")
        sys.exit(1)
    if args.skip_fetch and not args.input_csv:
        print("Error: --input-csv is required when using --skip-fetch")
        sys.exit(1)

    print("=" * 70)
    print("MENTIONS ENRICHMENT PIPELINE")
    print("=" * 70)
    print(f"\nSource: {args.source}")
    print(f"Data directory: {data_dir}")
    print(f"Alert ID: {args.alert_id or '(skipped)'}")
    print(f"Reach threshold: {args.threshold:,}")
    print(f"Min employees: {args.min_employees}")
    steps = f"{'Fetch → ' if not args.skip_fetch else ''}Enrich"
    if not args.skip_apollo:
        steps += ' → Apollo → Unqualified'
    print(f"Steps: {steps}")

    # Step 1: Fetch mentions
    if args.skip_fetch:
        mentions_csv = args.input_csv
        print(f"\nSkipping fetch. Using: {mentions_csv}")
        if not Path(mentions_csv).exists():
            print(f"Error: File not found: {mentions_csv}")
            sys.exit(1)
    else:
        mentions_csv = run_fetch_mentions(args.alert_id, args.source, data_dir, args.since_date)
        if not mentions_csv:
            print("\nPipeline aborted at fetch step.")
            sys.exit(1)

    run_stats['mentions_fetched'] = count_csv_rows(mentions_csv)

    # Step 2: Enrich domains
    enriched_csv = run_enrichment(mentions_csv, args.source, data_dir, args.threshold, args.yes)

    if not enriched_csv:
        print("\nPipeline stopped after enrichment (no output or user aborted).")
        if not args.skip_apollo:
            print("Re-run with --skip-fetch --input-csv to resume from enrichment.")
        run_stats['status'] = 'stopped_after_enrichment'
        save_run_stats(args.source, data_dir, run_stats)
        sys.exit(0)

    run_stats['companies_enriched'] = count_csv_rows(enriched_csv)

    # Step 3: Apollo pipeline
    if not args.skip_apollo:
        success = run_apollo_pipeline(enriched_csv, args.source, data_dir, args.min_employees, args.yes)
        if not success:
            print("\nApollo pipeline failed. Results are still in generated-outputs/.")
            run_stats['status'] = 'apollo_failed'
            save_run_stats(args.source, data_dir, run_stats)
            sys.exit(1)

        # Count qualified accounts
        apollo_file = data_dir / 'apollo-accounts' / f'{args.source}_apollo.csv'
        run_stats['qualified_accounts'] = count_csv_rows(str(apollo_file))

    # Step 4: Generate unqualified list
    if not args.skip_apollo:
        run_generate_unqualified(args.source, data_dir, args.yes)

        # Count master total
        master_file = data_dir / 'master' / f'{args.source}_master.csv'
        run_stats['master_total'] = count_csv_rows(str(master_file))

    # Step 5: Cleanup (remove generated-outputs/)
    if not args.no_cleanup and not args.skip_apollo:
        cleanup_outputs(args.source, data_dir)

    # Done
    run_stats['status'] = 'complete'
    save_run_stats(args.source, data_dir, run_stats)

    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    if not args.skip_apollo:
        apollo_file = data_dir / 'apollo-accounts' / f'{args.source}_apollo.csv'
        print(f"Qualified accounts: {apollo_file}")
        print(f"  → {run_stats.get('qualified_accounts', '?')} accounts (>{args.min_employees} employees)")
        print(f"  → Master total: {run_stats.get('master_total', '?')} companies")
    else:
        print("Enrichment complete. Run Apollo step manually or re-run without --skip-apollo.")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
