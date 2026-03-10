#!/usr/bin/env python3
"""
Run Pipeline - End-to-end hiring intel automation.

Orchestrates the full flow:
1. Find companies hiring for social media roles (Apollo)
2. Scrape full job descriptions from posting URLs
3. Extract structured intel from JDs (Claude Sonnet)
4. Generate 3 complete emails per company (Claude Opus + GTM playbook)
5. Push emails to Apollo contacts + add to sequence

Usage:
    python run_pipeline.py --source NAME --playbook PATH [options]

Options:
    --min-employees N      Minimum employee count (default: none)
    --max-employees N      Maximum employee count (default: none)
    --geo GEO              Geographic filter (e.g., "United States")
    --max-pages N          Max search pages per keyword (default: 5)
    --sequence-id ID       Apollo sequence ID to add contacts to
    --yes                  Skip all confirmation prompts
    --skip-find            Skip company discovery (provide --input-companies)
    --skip-scrape          Skip JD scraping (provide --input-descriptions)
    --skip-extract         Skip intel extraction (provide --input-intel)
    --skip-generate        Skip email generation (provide --input-emails)
    --skip-apollo          Skip Apollo push step
    --input-companies PATH Use existing companies_with_jobs.json
    --input-descriptions PATH  Use existing job_descriptions.json
    --input-intel PATH     Use existing intel_extracted.json
    --input-emails PATH    Use existing emails_generated.json
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

def normalize_source_name(source_name):
    import re
    if not source_name:
        return 'unknown_source'
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_output_dir(source):
    source_slug = normalize_source_name(source)
    today = date.today().isoformat()
    return OUTPUT_DIR / f'{source_slug}-{today}'


def find_output_file(output_subdir, filename):
    """Find an output file in the run directory"""
    path = output_subdir / filename
    if path.exists():
        return str(path)
    return None


# =============================================================================
# STEP RUNNERS
# =============================================================================

def run_find_companies(source, output_dir, max_pages=5, min_employees=None,
                       max_employees=None, geo=None, list_id=None,
                       auto_confirm=False):
    """Step 1: Find companies hiring for social media roles"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: FIND COMPANIES")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'find_companies.py'),
        '--source', source,
        '--max-pages', str(max_pages),
    ]
    if list_id:
        cmd.extend(['--list-id', list_id])
    if min_employees:
        cmd.extend(['--min-employees', str(min_employees)])
    if max_employees:
        cmd.extend(['--max-employees', str(max_employees)])
    if geo:
        cmd.extend(['--geo', geo])
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: find_companies.py exited with code {result.returncode}")
        return None

    return find_output_file(output_dir, 'companies_with_jobs.json')


def run_scrape_descriptions(companies_json, auto_confirm=False):
    """Step 2: Scrape job descriptions from posting URLs"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 2: SCRAPE JOB DESCRIPTIONS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'scrape_descriptions.py'),
        companies_json,
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: scrape_descriptions.py exited with code {result.returncode}")
        return None

    # Output is saved alongside input
    input_dir = Path(companies_json).parent
    output = input_dir / 'job_descriptions.json'
    return str(output) if output.exists() else None


def run_extract_intel(descriptions_json, auto_confirm=False):
    """Step 3: Extract structured intel from job descriptions"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 3: EXTRACT INTEL")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'extract_intel.py'),
        descriptions_json,
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: extract_intel.py exited with code {result.returncode}")
        return None

    input_dir = Path(descriptions_json).parent
    output = input_dir / 'intel_extracted.json'
    return str(output) if output.exists() else None


def run_generate_emails(intel_json, playbook_path, auto_confirm=False):
    """Step 4: Generate 3 emails per company"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 4: GENERATE EMAILS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'generate_emails.py'),
        intel_json,
        '--playbook', str(playbook_path),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: generate_emails.py exited with code {result.returncode}")
        return None

    input_dir = Path(intel_json).parent
    output = input_dir / 'emails_generated.json'
    return str(output) if output.exists() else None


def run_push_to_apollo(emails_json, source, sequence_id=None, auto_confirm=False):
    """Step 5: Push emails to Apollo contacts"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 5: PUSH TO APOLLO")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'push_to_apollo.py'),
        emails_json,
        '--source', source,
    ]
    if sequence_id:
        cmd.extend(['--sequence-id', sequence_id])
    if auto_confirm:
        cmd.append('--yes')

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
        description='End-to-end hiring intel pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python run_pipeline.py --source weekly_feb02 --playbook /path/to/playbook.md

  # With filters
  python run_pipeline.py --source weekly_feb02 --playbook playbook.md \\
    --min-employees 50 --max-employees 1000 --geo "United States"

  # Skip to email generation (already have intel)
  python run_pipeline.py --source weekly_feb02 --playbook playbook.md \\
    --skip-find --skip-scrape --skip-extract --input-intel intel_extracted.json

  # Generate emails only, don't push to Apollo
  python run_pipeline.py --source weekly_feb02 --playbook playbook.md --skip-apollo
        """,
    )
    parser.add_argument('--source', required=True, help='Source name for this run')
    parser.add_argument('--playbook', required=True,
                        help='Path to GTM playbook markdown file (required for email generation)')
    parser.add_argument('--min-employees', type=int, default=None,
                        help='Minimum employee count filter')
    parser.add_argument('--max-employees', type=int, default=None,
                        help='Maximum employee count filter')
    parser.add_argument('--geo', default=None,
                        help='Geographic filter (e.g., "United States")')
    parser.add_argument('--max-pages', type=int, default=5,
                        help='Max pages per search keyword (default: 5)')
    parser.add_argument('--list-id', default=None,
                        help='Apollo People List ID (use "list" to discover)')
    parser.add_argument('--sequence-id', default=None,
                        help='Apollo sequence ID to add contacts to')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip all confirmation prompts')

    # Skip flags
    parser.add_argument('--skip-find', action='store_true',
                        help='Skip company discovery (use --input-companies)')
    parser.add_argument('--skip-scrape', action='store_true',
                        help='Skip JD scraping (use --input-descriptions)')
    parser.add_argument('--skip-extract', action='store_true',
                        help='Skip intel extraction (use --input-intel)')
    parser.add_argument('--skip-generate', action='store_true',
                        help='Skip email generation (use --input-emails)')
    parser.add_argument('--skip-apollo', action='store_true',
                        help='Skip Apollo push step')

    # Input overrides
    parser.add_argument('--input-companies', help='Path to companies_with_jobs.json')
    parser.add_argument('--input-descriptions', help='Path to job_descriptions.json')
    parser.add_argument('--input-intel', help='Path to intel_extracted.json')
    parser.add_argument('--input-emails', help='Path to emails_generated.json')

    parser.add_argument('--no-cleanup', action='store_true',
                        help='Keep generated-outputs after completion')

    args = parser.parse_args()

    # Validate
    if args.skip_find and not args.input_companies:
        if not (args.skip_scrape and args.input_descriptions):
            if not (args.skip_extract and args.input_intel):
                if not (args.skip_generate and args.input_emails):
                    print("Error: --input-companies required when using --skip-find")
                    sys.exit(1)

    if not args.skip_generate and not args.playbook:
        print("Error: --playbook is required for email generation")
        sys.exit(1)

    if args.playbook and not Path(args.playbook).exists():
        print(f"Error: Playbook not found: {args.playbook}")
        sys.exit(1)

    print("=" * 70)
    print("HIRING INTEL PIPELINE")
    print("=" * 70)

    steps = []
    if not args.skip_find:
        steps.append('Find')
    if not args.skip_scrape:
        steps.append('Scrape')
    if not args.skip_extract:
        steps.append('Extract')
    if not args.skip_generate:
        steps.append('Generate')
    if not args.skip_apollo:
        steps.append('Apollo')

    print(f"\nSource: {args.source}")
    print(f"Playbook: {args.playbook}")
    print(f"Steps: {' -> '.join(steps)}")
    if args.min_employees or args.max_employees:
        print(f"Employee filter: {args.min_employees or 'any'} - {args.max_employees or 'any'}")
    if args.geo:
        print(f"Geo: {args.geo}")
    if args.list_id:
        print(f"List ID: {args.list_id}")
    if args.sequence_id:
        print(f"Sequence ID: {args.sequence_id}")

    # Ensure output directory exists
    output_dir = get_output_dir(args.source)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Find companies
    if args.skip_find:
        companies_json = args.input_companies
        if companies_json:
            print(f"\nSkipping find. Using: {companies_json}")
    else:
        companies_json = run_find_companies(
            args.source, output_dir,
            max_pages=args.max_pages,
            min_employees=args.min_employees,
            max_employees=args.max_employees,
            geo=args.geo,
            list_id=args.list_id,
            auto_confirm=args.yes,
        )
        if not companies_json:
            print("\nPipeline aborted at find step.")
            sys.exit(1)

    # Step 2: Scrape descriptions
    if args.skip_scrape:
        descriptions_json = args.input_descriptions
        if descriptions_json:
            print(f"\nSkipping scrape. Using: {descriptions_json}")
    else:
        if not companies_json:
            print("Error: No companies JSON available for scraping.")
            sys.exit(1)
        descriptions_json = run_scrape_descriptions(companies_json, args.yes)
        if not descriptions_json:
            print("\nPipeline aborted at scrape step.")
            sys.exit(1)

    # Step 3: Extract intel
    if args.skip_extract:
        intel_json = args.input_intel
        if intel_json:
            print(f"\nSkipping extract. Using: {intel_json}")
    else:
        if not descriptions_json:
            print("Error: No descriptions JSON available for extraction.")
            sys.exit(1)
        intel_json = run_extract_intel(descriptions_json, args.yes)
        if not intel_json:
            print("\nPipeline aborted at extraction step.")
            sys.exit(1)

    # Step 4: Generate emails
    if args.skip_generate:
        emails_json = args.input_emails
        if emails_json:
            print(f"\nSkipping generate. Using: {emails_json}")
    else:
        if not intel_json:
            print("Error: No intel JSON available for email generation.")
            sys.exit(1)
        emails_json = run_generate_emails(intel_json, args.playbook, args.yes)
        if not emails_json:
            print("\nPipeline aborted at email generation step.")
            sys.exit(1)

    # Step 5: Push to Apollo
    if not args.skip_apollo:
        if not emails_json:
            print("Error: No emails JSON available for Apollo push.")
            sys.exit(1)
        success = run_push_to_apollo(
            emails_json, args.source, args.sequence_id, args.yes,
        )
        if not success:
            print("\nApollo push failed. Generated emails are still in generated-outputs/.")
            sys.exit(1)

    # Cleanup
    if not args.no_cleanup:
        cleanup_outputs(args.source)

    # Done
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    if not args.skip_apollo:
        source_slug = normalize_source_name(args.source)
        print(f"Master updated: master/{source_slug}_hiring_master.csv")
        print("Contacts updated with custom email fields in Apollo.")
        if args.sequence_id:
            print(f"Contacts added to sequence: {args.sequence_id}")
    else:
        print(f"Emails generated. Run Apollo push manually or re-run without --skip-apollo.")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
