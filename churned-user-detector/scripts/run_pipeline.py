#!/usr/bin/env python3
"""
Run Pipeline - Orchestrate churned user job change detection.

1. Load removed users from CSV (auto-detect Agorapulse export columns)
2. Detect job changes (enrich LinkedIn, scrape, classify, email check)
3. Push job changers to Apollo (update company/title + add to enriched list)

Usage:
    python run_pipeline.py --source NAME --csv PATH [options]

Examples:
    # Full pipeline (detect + push to Apollo)
    python run_pipeline.py --source agorapulse_churned_feb25 --csv removed_users.csv

    # Recurring weekly run (auto-confirm)
    python run_pipeline.py --source agorapulse_weekly_w07 --csv weekly_export.csv --yes

    # Skip CSV loading (already have JSON)
    python run_pipeline.py --source agorapulse_churned_feb25 --skip-load --input-users users.json

    # Detection only, skip Apollo push
    python run_pipeline.py --source agorapulse_churned_feb25 --csv export.csv --skip-apollo
"""

import subprocess
import sys
import argparse
import re
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


# =============================================================================
# HELPERS
# =============================================================================

def normalize_source_name(source_name):
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_output_dir(source):
    source_slug = normalize_source_name(source)
    today = date.today().isoformat()
    return OUTPUT_DIR / f'{source_slug}-{today}'


# =============================================================================
# STEP RUNNERS
# =============================================================================

def run_load_users(csv_path, source, output_dir, col_overrides=None, auto_confirm=False):
    """Step 1: Load removed users from CSV"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: LOAD REMOVED USERS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'load_removed_users.py'),
        csv_path,
        '--source', source,
        '--output-dir', str(output_dir),
    ]

    if col_overrides:
        for flag, value in col_overrides.items():
            if value:
                cmd.extend([flag, value])

    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: load_removed_users.py exited with code {result.returncode}")
        return None

    output = output_dir / 'removed_users.json'
    return str(output) if output.exists() else None


def run_detect(users_json, source, max_concurrent=3, skip_email_check=False, auto_confirm=False):
    """Step 2: Detect job changes"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 2: DETECT JOB CHANGES")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'detect_job_changes.py'),
        users_json,
        '--source', source,
        '--max-concurrent-batches', str(max_concurrent),
    ]

    if skip_email_check:
        cmd.append('--skip-email-check')
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: detect_job_changes.py exited with code {result.returncode}")
        return False

    return True


def run_push_to_apollo(job_changers_csv, source, list_id=None, auto_confirm=False):
    """Step 3: Push job changers to Apollo (update company/title + add to list)"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 3: PUSH TO APOLLO")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'push_to_apollo.py'),
        job_changers_csv,
        '--source', source,
    ]

    if list_id:
        cmd.extend(['--list-id', list_id])
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: push_to_apollo.py exited with code {result.returncode}")
        return False

    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Churned user job change detection pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python run_pipeline.py --source agorapulse_churned_feb25 \\
    --csv removed_users.csv

  # Weekly recurring (auto-confirm)
  python run_pipeline.py --source agorapulse_weekly_w07 \\
    --csv weekly_export.csv --yes

  # Custom column mapping
  python run_pipeline.py --source agorapulse_churned_feb25 \\
    --csv export.csv --col-name "User Name" --col-email "Email Address"

  # Skip to detection (already have JSON)
  python run_pipeline.py --source agorapulse_churned_feb25 \\
    --skip-load --input-users generated-outputs/removed_users.json
        """,
    )

    parser.add_argument('--source', required=True,
                        help='Source name for this run (e.g., agorapulse_churned_feb25)')
    parser.add_argument('--csv', default=None,
                        help='Path to input CSV (Agorapulse admin export)')

    # Column mapping
    parser.add_argument('--col-name', default=None, help='CSV column for user name')
    parser.add_argument('--col-email', default=None, help='CSV column for email')
    parser.add_argument('--col-company', default=None, help='CSV column for company')
    parser.add_argument('--col-mrr', default=None, help='CSV column for MRR')
    parser.add_argument('--col-country', default=None, help='CSV column for country')
    parser.add_argument('--col-plan', default=None, help='CSV column for plan')

    # Control
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip all confirmation prompts')
    parser.add_argument('--max-concurrent-batches', type=int, default=3,
                        help='Max parallel Apify batches (default: 3)')
    parser.add_argument('--skip-email-check', action='store_true',
                        help='Skip SMTP email validation')

    # Skip flags
    parser.add_argument('--skip-load', action='store_true',
                        help='Skip CSV loading (use --input-users)')
    parser.add_argument('--skip-apollo', action='store_true',
                        help='Skip Apollo push (detection only)')
    parser.add_argument('--input-users', default=None,
                        help='Path to removed_users.json (when using --skip-load)')

    # Apollo push
    parser.add_argument('--list-id', default=None,
                        help='Apollo list ID for enriched list (default: built-in)')

    args = parser.parse_args()

    # Validate
    if not args.skip_load and not args.csv:
        print("Error: --csv is required (or use --skip-load with --input-users)")
        sys.exit(1)

    if args.csv and not Path(args.csv).exists():
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)

    if args.skip_load and not args.input_users:
        print("Error: --input-users is required when using --skip-load")
        sys.exit(1)

    if args.input_users and not Path(args.input_users).exists():
        print(f"Error: Users JSON not found: {args.input_users}")
        sys.exit(1)

    # Header
    print("=" * 70)
    print("CHURNED USER JOB CHANGE DETECTION PIPELINE")
    print("=" * 70)

    steps = []
    if not args.skip_load:
        steps.append('Load CSV')
    steps.append('Detect (Enrich → Scrape → Classify → Email Check)')
    if not args.skip_apollo:
        steps.append('Push to Apollo')

    print(f"\nSource: {args.source}")
    if args.csv:
        print(f"CSV: {args.csv}")
    print(f"Steps: {' → '.join(steps)}")
    print(f"Apify concurrency: {args.max_concurrent_batches}")
    print(f"Email check: {'disabled' if args.skip_email_check else 'enabled'}")
    print(f"Apollo push: {'disabled' if args.skip_apollo else 'enabled'}")

    # Ensure output directory
    output_dir = get_output_dir(args.source)
    output_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Step 1: Load removed users from CSV
    # =========================================================================
    if args.skip_load:
        users_json = args.input_users
        print(f"\nSkipping load. Using: {users_json}")
    else:
        col_overrides = {
            '--col-name': args.col_name,
            '--col-email': args.col_email,
            '--col-company': args.col_company,
            '--col-mrr': args.col_mrr,
            '--col-country': args.col_country,
            '--col-plan': args.col_plan,
        }
        col_overrides = {k: v for k, v in col_overrides.items() if v}

        users_json = run_load_users(
            args.csv, args.source, output_dir,
            col_overrides=col_overrides,
            auto_confirm=args.yes,
        )
        if not users_json:
            print("\nPipeline aborted at load step.")
            sys.exit(1)

    # =========================================================================
    # Step 2: Detect job changes
    # =========================================================================
    success = run_detect(
        users_json, args.source,
        max_concurrent=args.max_concurrent_batches,
        skip_email_check=args.skip_email_check,
        auto_confirm=args.yes,
    )

    if not success:
        print("\nPipeline aborted at detection step.")
        sys.exit(1)

    # =========================================================================
    # Step 3: Push job changers to Apollo
    # =========================================================================
    if args.skip_apollo:
        print("\nSkipping Apollo push (--skip-apollo).")
    else:
        job_changers_csv = str(output_dir / 'job_changers.csv')
        if not Path(job_changers_csv).exists():
            print(f"\nNo job_changers.csv found — nothing to push to Apollo.")
        else:
            apollo_ok = run_push_to_apollo(
                job_changers_csv, args.source,
                list_id=args.list_id,
                auto_confirm=args.yes,
            )
            if not apollo_ok:
                print("\nApollo push failed (detection results still saved).")

    # Done
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Output directory: {output_dir}")
    print(f"  job_changers.csv      — BDR-ready for Salesforce campaign")
    print(f"  in_between_jobs.csv   — Follow up later")
    print(f"  detection_failures.csv — No LinkedIn / scrape failed")
    if not args.skip_apollo:
        print(f"  Apollo push master    — master/{normalize_source_name(args.source)}_apollo_push_master.csv")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
