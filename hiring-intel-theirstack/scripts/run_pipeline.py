#!/usr/bin/env python3
"""
Run Pipeline - Autonomous TheirStack hiring intel automation.

Orchestrates the full flow:
0. Fetch jobs from TheirStack API (incremental since last run)
1. Transform API response to pipeline format
2. Extract structured intel from JDs (Claude Sonnet)
3. Generate 3 complete emails per company (Claude Opus + GTM playbook)
4. Push emails to Apollo contacts with two-tier matching + add to sequence

Fully autonomous: auto-generates source name from date, no manual CSV export,
auto-push to Apollo enabled by default.

Usage:
    python run_pipeline.py --playbook PATH [options]

Options:
    --playbook PATH            GTM playbook markdown file (required for email generation)
    --sequence-id ID           Apollo sequence ID to add contacts to
    --skip-fetch               Skip TheirStack API fetch (provide --input-jobs-raw)
    --skip-transform           Skip transformation (provide --input-descriptions)
    --skip-extract             Skip intel extraction (provide --input-intel)
    --skip-generate            Skip email generation (provide --input-emails)
    --skip-apollo              Skip Apollo push step
    --input-jobs-raw PATH      Use existing jobs_raw.json
    --input-descriptions PATH  Use existing job_descriptions.json
    --input-intel PATH         Use existing intel_extracted.json
    --input-emails PATH        Use existing emails_generated.json
    --no-cleanup               Keep generated-outputs after completion
"""

import subprocess
import sys
import os
import shutil
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


# =============================================================================
# HELPERS
# =============================================================================

def get_source_name():
    """Auto-generate source name from current date"""
    today = date.today().isoformat()
    return f'theirstack_{today}'


def get_output_dir(source):
    """Get output directory for this run"""
    return OUTPUT_DIR / source


def find_output_file(output_subdir, filename):
    """Find an output file in the run directory"""
    path = output_subdir / filename
    if path.exists():
        return str(path)
    return None


# =============================================================================
# STEP RUNNERS
# =============================================================================

def run_fetch_theirstack_jobs(output_dir):
    """Step 0: Fetch jobs from TheirStack API"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 0: FETCH THEIRSTACK JOBS")
    print("=" * 70)

    cmd = [sys.executable, str(SCRIPTS_DIR / 'fetch_theirstack_jobs.py')]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: fetch_theirstack_jobs.py exited with code {result.returncode}")
        return None

    return find_output_file(output_dir, 'jobs_raw.json')


def run_transform_theirstack_data(jobs_raw_json):
    """Step 1: Transform API response to job_descriptions.json"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: TRANSFORM THEIRSTACK DATA")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'transform_theirstack_data.py'),
        jobs_raw_json,
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: transform_theirstack_data.py exited with code {result.returncode}")
        return None

    # Output is saved alongside input
    input_dir = Path(jobs_raw_json).parent
    output = input_dir / 'job_descriptions.json'
    return str(output) if output.exists() else None


def run_extract_intel(descriptions_json):
    """Step 2: Extract structured intel from job descriptions"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 2: EXTRACT INTEL")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'extract_intel.py'),
        descriptions_json,
        '--yes',  # Auto-confirm
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: extract_intel.py exited with code {result.returncode}")
        return None

    input_dir = Path(descriptions_json).parent
    output = input_dir / 'intel_extracted.json'
    return str(output) if output.exists() else None


def run_generate_emails(intel_json, playbook_path):
    """Step 3: Generate 3 emails per company"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 3: GENERATE EMAILS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'generate_emails.py'),
        intel_json,
        '--playbook', str(playbook_path),
        '--yes',  # Auto-confirm
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: generate_emails.py exited with code {result.returncode}")
        return None

    input_dir = Path(intel_json).parent
    output = input_dir / 'emails_generated.json'
    return str(output) if output.exists() else None


def run_push_to_apollo(emails_json, source, sequence_id=None):
    """Step 4: Push emails to Apollo contacts"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 4: PUSH TO APOLLO")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'push_to_apollo.py'),
        emails_json,
        '--source', source,
        '--yes',  # Auto-push enabled
    ]
    if sequence_id:
        cmd.extend(['--sequence-id', sequence_id])

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: push_to_apollo.py exited with code {result.returncode}")
        return False

    return True


def cleanup_outputs(source):
    """Clean up generated-outputs/ for this run"""
    output_dir = get_output_dir(source)

    if output_dir.exists():
        print(f"\nCleaning up: {output_dir}")
        shutil.rmtree(output_dir)
        print("  Done.")
    else:
        print(f"\nNo output directory to clean: {output_dir}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Autonomous TheirStack hiring intel pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full autonomous pipeline
  python run_pipeline.py --playbook /path/to/playbook.md

  # With Apollo sequence enrollment
  python run_pipeline.py --playbook playbook.md --sequence-id SEQ_ABC123

  # Skip to email generation (already have intel)
  python run_pipeline.py --playbook playbook.md \\
    --skip-fetch --skip-transform --skip-extract --input-intel intel_extracted.json

  # Dry-run mode (fetch & generate only, no Apollo push)
  python run_pipeline.py --playbook playbook.md --skip-apollo
        """,
    )
    parser.add_argument('--playbook', required=True,
                        help='Path to GTM playbook markdown file (required for email generation)')
    parser.add_argument('--sequence-id', default=None,
                        help='Apollo sequence ID to add contacts to')

    # Skip flags
    parser.add_argument('--skip-fetch', action='store_true',
                        help='Skip API fetch (use --input-jobs-raw)')
    parser.add_argument('--skip-transform', action='store_true',
                        help='Skip transformation (use --input-descriptions)')
    parser.add_argument('--skip-extract', action='store_true',
                        help='Skip intel extraction (use --input-intel)')
    parser.add_argument('--skip-generate', action='store_true',
                        help='Skip email generation (use --input-emails)')
    parser.add_argument('--skip-apollo', action='store_true',
                        help='Skip Apollo push step')

    # Input overrides
    parser.add_argument('--input-jobs-raw', help='Path to jobs_raw.json')
    parser.add_argument('--input-descriptions', help='Path to job_descriptions.json')
    parser.add_argument('--input-intel', help='Path to intel_extracted.json')
    parser.add_argument('--input-emails', help='Path to emails_generated.json')

    parser.add_argument('--no-cleanup', action='store_true',
                        help='Keep generated-outputs after completion')

    args = parser.parse_args()

    # Validate
    if not args.skip_generate and not args.playbook:
        print("Error: --playbook is required for email generation")
        sys.exit(1)

    if args.playbook and not Path(args.playbook).exists():
        print(f"Error: Playbook not found: {args.playbook}")
        sys.exit(1)

    print("=" * 70)
    print("HIRING INTEL THEIRSTACK - AUTONOMOUS PIPELINE")
    print("=" * 70)

    steps = []
    if not args.skip_fetch:
        steps.append('Fetch')
    if not args.skip_transform:
        steps.append('Transform')
    if not args.skip_extract:
        steps.append('Extract')
    if not args.skip_generate:
        steps.append('Generate')
    if not args.skip_apollo:
        steps.append('Apollo')

    # Auto-generate source name
    source = get_source_name()

    print(f"\nSource: {source} (auto-generated)")
    print(f"Playbook: {args.playbook}")
    print(f"Steps: {' → '.join(steps)}")
    if args.sequence_id:
        print(f"Sequence ID: {args.sequence_id}")

    # Ensure output directory exists
    output_dir = get_output_dir(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 0: Fetch jobs from TheirStack API
    if args.skip_fetch:
        jobs_raw_json = args.input_jobs_raw
        if jobs_raw_json:
            print(f"\nSkipping fetch. Using: {jobs_raw_json}")
    else:
        jobs_raw_json = run_fetch_theirstack_jobs(output_dir)
        if not jobs_raw_json:
            print("\nPipeline aborted at fetch step.")
            sys.exit(1)

    # Step 1: Transform API response
    if args.skip_transform:
        descriptions_json = args.input_descriptions
        if descriptions_json:
            print(f"\nSkipping transform. Using: {descriptions_json}")
    else:
        if not jobs_raw_json:
            print("Error: No jobs_raw.json available for transformation.")
            sys.exit(1)
        descriptions_json = run_transform_theirstack_data(jobs_raw_json)
        if not descriptions_json:
            print("\nPipeline aborted at transform step.")
            sys.exit(1)

    # Step 2: Extract intel
    if args.skip_extract:
        intel_json = args.input_intel
        if intel_json:
            print(f"\nSkipping extract. Using: {intel_json}")
    else:
        if not descriptions_json:
            print("Error: No job_descriptions.json available for extraction.")
            sys.exit(1)
        intel_json = run_extract_intel(descriptions_json)
        if not intel_json:
            print("\nPipeline aborted at extraction step.")
            sys.exit(1)

    # Step 3: Generate emails
    if args.skip_generate:
        emails_json = args.input_emails
        if emails_json:
            print(f"\nSkipping generate. Using: {emails_json}")
    else:
        if not intel_json:
            print("Error: No intel_extracted.json available for email generation.")
            sys.exit(1)
        emails_json = run_generate_emails(intel_json, args.playbook)
        if not emails_json:
            print("\nPipeline aborted at email generation step.")
            sys.exit(1)

    # Step 4: Push to Apollo
    if not args.skip_apollo:
        if not emails_json:
            print("Error: No emails_generated.json available for Apollo push.")
            sys.exit(1)
        success = run_push_to_apollo(emails_json, source, args.sequence_id)
        if not success:
            print("\nApollo push failed. Generated emails are still in generated-outputs/.")
            sys.exit(1)

    # Cleanup
    if not args.no_cleanup:
        cleanup_outputs(source)

    # Done
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    if not args.skip_apollo:
        print(f"Master updated: master/{source}_hiring_master.csv")
        print("Contacts updated with custom email fields in Apollo.")
        if args.sequence_id:
            print(f"Contacts added to sequence: {args.sequence_id}")
    else:
        print(f"Emails generated. Run Apollo push manually or re-run without --skip-apollo.")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
