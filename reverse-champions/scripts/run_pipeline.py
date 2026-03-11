#!/usr/bin/env python3
"""
Run Pipeline - End-to-end reverse champions outbound automation.

Orchestrates the full flow:
1. Load champions from CSV (auto-detect columns or manual mapping)
2. Enrich missing LinkedIn URLs via Apollo
3. Scrape LinkedIn profiles for work history (Apify)
4. Filter roles (regex + Haiku for ambiguous titles)
5. Validate target companies against ICP (Apollo + competitor exclusion)
6. Find personas at validated companies (Apollo People Search)
7. Generate champion-angle emails (Claude Sonnet, hybrid personalization)
8. Push emails to Apollo contacts + add to sequence

Usage:
    python run_pipeline.py --source NAME --csv PATH --playbook PATH [options]

Options:
    --col-name COL         Column name for contact name
    --col-email COL        Column name for contact email
    --col-company COL      Column name for company name
    --col-linkedin COL     Column name for LinkedIn URL
    --min-employees N      Minimum employee count filter
    --max-employees N      Maximum employee count filter
    --geo GEO              Geographic filter (e.g., "United States")
    --sequence-id ID       Apollo sequence ID to add contacts to
    --yes                  Skip all confirmation prompts
    --skip-load            Skip CSV loading (use --input-champions)
    --skip-enrich          Skip LinkedIn URL enrichment
    --skip-scrape          Skip LinkedIn profile scraping (use --input-history)
    --skip-filter          Skip role filtering (use --input-roles)
    --skip-validate        Skip company validation (use --input-companies)
    --skip-personas        Skip persona finding (use --input-personas)
    --skip-generate        Skip email generation (use --input-emails)
    --skip-apollo          Skip Apollo push step
"""

import subprocess
import sys
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


def find_output_file(output_dir, filename):
    """Find an output file in the run directory"""
    path = output_dir / filename
    if path.exists():
        return str(path)
    return None


# =============================================================================
# STEP RUNNERS
# =============================================================================

def run_fetch_from_apollo(source, output_dir, days=7, auto_confirm=False):
    """Step 1 (production): Fetch champions from Apollo by Became Paid Date"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: FETCH FROM APOLLO")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'fetch_from_apollo.py'),
        '--source', source,
        '--days', str(days),
        '--output-dir', str(output_dir),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: fetch_from_apollo.py exited with code {result.returncode}")
        return None

    return find_output_file(output_dir, 'champions_to_scrape.json')


def run_load_champions(csv_path, source, output_dir, col_name=None, col_email=None,
                       col_company=None, col_linkedin=None, auto_confirm=False):
    """Step 1: Load champions from CSV"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: LOAD CHAMPIONS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'load_champions.py'),
        csv_path,
        '--source', source,
        '--output-dir', str(output_dir),
    ]
    if col_name:
        cmd.extend(['--col-name', col_name])
    if col_email:
        cmd.extend(['--col-email', col_email])
    if col_company:
        cmd.extend(['--col-company', col_company])
    if col_linkedin:
        cmd.extend(['--col-linkedin', col_linkedin])
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: load_champions.py exited with code {result.returncode}")
        return None

    return find_output_file(output_dir, 'champions_to_scrape.json')


def run_enrich_linkedin(champions_json, auto_confirm=False):
    """Step 2: Enrich missing LinkedIn URLs via Apollo"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 2: ENRICH LINKEDIN URLS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'enrich_linkedin_urls.py'),
        champions_json,
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: enrich_linkedin_urls.py exited with code {result.returncode}")
        return None

    # Enrichment updates the file in-place
    return champions_json


def run_scrape_work_history(champions_json, auto_confirm=False):
    """Step 3: Scrape LinkedIn profiles for work history"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 3: SCRAPE WORK HISTORY")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'scrape_work_history.py'),
        champions_json,
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: scrape_work_history.py exited with code {result.returncode}")
        return None

    input_dir = Path(champions_json).parent
    output = input_dir / 'work_history_scraped.json'
    return str(output) if output.exists() else None


def run_filter_roles(history_json, auto_confirm=False):
    """Step 4: Filter roles using regex + Haiku"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 4: FILTER ROLES")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'filter_roles.py'),
        history_json,
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: filter_roles.py exited with code {result.returncode}")
        return None

    input_dir = Path(history_json).parent
    output = input_dir / 'roles_filtered.json'
    return str(output) if output.exists() else None


def run_validate_companies(roles_json, min_employees=None, max_employees=None,
                           geo=None, auto_confirm=False):
    """Step 5: Validate target companies against ICP"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 5: VALIDATE COMPANIES")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'validate_companies.py'),
        roles_json,
    ]
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
        print(f"Error: validate_companies.py exited with code {result.returncode}")
        return None

    input_dir = Path(roles_json).parent
    output = input_dir / 'companies_validated.json'
    return str(output) if output.exists() else None


def run_find_personas(companies_json, auto_confirm=False):
    """Step 6: Find target contacts at validated companies"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 6: FIND PERSONAS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'find_personas.py'),
        companies_json,
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: find_personas.py exited with code {result.returncode}")
        return None

    input_dir = Path(companies_json).parent
    output = input_dir / 'personas_found.json'
    return str(output) if output.exists() else None


def run_generate_emails(personas_json, playbook_path, auto_confirm=False):
    """Step 7: Generate champion-angle emails"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 7: GENERATE EMAILS")
    print("=" * 70)

    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'generate_emails.py'),
        personas_json,
        '--playbook', str(playbook_path),
    ]
    if auto_confirm:
        cmd.append('--yes')

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Error: generate_emails.py exited with code {result.returncode}")
        return None

    input_dir = Path(personas_json).parent
    output = input_dir / 'emails_generated.json'
    return str(output) if output.exists() else None


def run_push_to_apollo(emails_json, source, sequence_id=None, auto_confirm=False):
    """Step 8: Push emails to Apollo contacts + sequence"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 8: PUSH TO APOLLO")
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
        description='End-to-end reverse champions outbound pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Weekly production run (Apollo source, last 7 days)
  python run_pipeline.py --source cw_weekly \\
    --from-apollo --sequence-id 698f40f00ef2f30021af248d --skip-generate

  # Apollo source with custom lookback
  python run_pipeline.py --source cw_weekly \\
    --from-apollo --days 14 --sequence-id 698f40f00ef2f30021af248d --skip-generate

  # One-time CSV run (pilot or backfill)
  python run_pipeline.py --source cw_2025 \\
    --csv /path/to/export.csv --sequence-id 698f40f00ef2f30021af248d --skip-generate

  # Custom column mapping for CSV
  python run_pipeline.py --source cw_2025 \\
    --csv export.csv --sequence-id 698f40f00ef2f30021af248d --skip-generate \\
    --col-name "Full Name" --col-email "Work Email" --col-company "Account"
        """,
    )
    parser.add_argument('--source', required=True,
                        help='Source name for this run (e.g., q1_2025_champions)')
    parser.add_argument('--from-apollo', action='store_true',
                        help='Fetch champions from Apollo (Became Paid Date filter) instead of CSV')
    parser.add_argument('--days', type=int, default=7,
                        help='Days lookback for --from-apollo (default: 7)')
    parser.add_argument('--csv', default=None,
                        help='Path to input CSV with champion contacts')
    parser.add_argument('--playbook', default=None,
                        help='Path to GTM playbook markdown file (required only if generating emails)')

    # Column mapping
    parser.add_argument('--col-name', default=None,
                        help='CSV column name for contact name')
    parser.add_argument('--col-email', default=None,
                        help='CSV column name for contact email')
    parser.add_argument('--col-company', default=None,
                        help='CSV column name for company name')
    parser.add_argument('--col-linkedin', default=None,
                        help='CSV column name for LinkedIn URL')

    # ICP filters
    parser.add_argument('--min-employees', type=int, default=None,
                        help='Minimum employee count filter')
    parser.add_argument('--max-employees', type=int, default=None,
                        help='Maximum employee count filter')
    parser.add_argument('--geo', default=None,
                        help='Geographic filter (e.g., "United States")')

    # Apollo
    parser.add_argument('--sequence-id', default=None,
                        help='Apollo sequence ID to add contacts to')

    # Control
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip all confirmation prompts')

    # Skip flags
    parser.add_argument('--skip-load', action='store_true',
                        help='Skip CSV loading (use --input-champions)')
    parser.add_argument('--skip-enrich', action='store_true',
                        help='Skip LinkedIn URL enrichment')
    parser.add_argument('--skip-scrape', action='store_true',
                        help='Skip LinkedIn profile scraping (use --input-history)')
    parser.add_argument('--skip-filter', action='store_true',
                        help='Skip role filtering (use --input-roles)')
    parser.add_argument('--skip-validate', action='store_true',
                        help='Skip company validation (use --input-companies)')
    parser.add_argument('--skip-personas', action='store_true',
                        help='Skip persona finding (use --input-personas)')
    parser.add_argument('--skip-generate', action='store_true',
                        help='Skip email generation (use --input-emails)')
    parser.add_argument('--skip-apollo', action='store_true',
                        help='Skip Apollo push step')

    # Input overrides
    parser.add_argument('--input-champions', help='Path to champions_to_scrape.json')
    parser.add_argument('--input-history', help='Path to work_history_scraped.json')
    parser.add_argument('--input-roles', help='Path to roles_filtered.json')
    parser.add_argument('--input-companies', help='Path to companies_validated.json')
    parser.add_argument('--input-personas', help='Path to personas_found.json')
    parser.add_argument('--input-emails', help='Path to emails_generated.json')

    parser.add_argument('--no-cleanup', action='store_true',
                        help='Keep generated-outputs after completion')

    args = parser.parse_args()

    # Validate required inputs
    if not args.skip_load and not args.csv and not args.from_apollo:
        print("Error: --csv or --from-apollo is required (or use --skip-load with --input-champions)")
        sys.exit(1)

    if args.csv and not Path(args.csv).exists():
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)

    if not args.skip_generate and args.playbook and not Path(args.playbook).exists():
        print(f"Error: Playbook not found: {args.playbook}")
        sys.exit(1)

    # Header
    print("=" * 70)
    print("REVERSE CHAMPIONS PIPELINE")
    print("=" * 70)

    steps = []
    if not args.skip_load:
        steps.append('Load')
    if not args.skip_enrich:
        steps.append('Enrich')
    if not args.skip_scrape:
        steps.append('Scrape')
    if not args.skip_filter:
        steps.append('Filter')
    if not args.skip_validate:
        steps.append('Validate')
    if not args.skip_personas:
        steps.append('Personas')
    if not args.skip_generate:
        steps.append('Emails')
    if not args.skip_apollo:
        steps.append('Apollo')

    print(f"\nSource: {args.source}")
    if args.csv:
        print(f"CSV: {args.csv}")
    print(f"Playbook: {args.playbook}")
    print(f"Steps: {' -> '.join(steps)}")
    if args.min_employees or args.max_employees:
        print(f"Employee filter: {args.min_employees or 'any'} - {args.max_employees or 'any'}")
    if args.geo:
        print(f"Geo: {args.geo}")
    if args.sequence_id:
        print(f"Sequence ID: {args.sequence_id}")

    # Ensure output directory exists
    output_dir = get_output_dir(args.source)
    output_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Step 1: Load champions (from Apollo or CSV)
    # =========================================================================
    if args.skip_load:
        champions_json = args.input_champions
        if champions_json:
            print(f"\nSkipping load. Using: {champions_json}")
    elif args.from_apollo:
        champions_json = run_fetch_from_apollo(
            args.source, output_dir, days=args.days, auto_confirm=args.yes,
        )
        if not champions_json:
            print("\nPipeline aborted at fetch step.")
            sys.exit(1)
    else:
        champions_json = run_load_champions(
            args.csv, args.source, output_dir,
            col_name=args.col_name,
            col_email=args.col_email,
            col_company=args.col_company,
            col_linkedin=args.col_linkedin,
            auto_confirm=args.yes,
        )
        if not champions_json:
            print("\nPipeline aborted at load step.")
            sys.exit(1)

    # =========================================================================
    # Step 2: Enrich LinkedIn URLs
    # =========================================================================
    if args.skip_enrich:
        print(f"\nSkipping LinkedIn enrichment.")
    else:
        if not champions_json:
            print("Error: No champions JSON available for enrichment.")
            sys.exit(1)
        champions_json = run_enrich_linkedin(champions_json, args.yes)
        if not champions_json:
            print("\nPipeline aborted at enrichment step.")
            sys.exit(1)

    # =========================================================================
    # Step 3: Scrape work history
    # =========================================================================
    if args.skip_scrape:
        history_json = args.input_history
        if history_json:
            print(f"\nSkipping scrape. Using: {history_json}")
    else:
        if not champions_json:
            print("Error: No champions JSON available for scraping.")
            sys.exit(1)
        history_json = run_scrape_work_history(champions_json, args.yes)
        if not history_json:
            print("\nPipeline aborted at scrape step.")
            sys.exit(1)

    # =========================================================================
    # Step 4: Filter roles
    # =========================================================================
    if args.skip_filter:
        roles_json = args.input_roles
        if roles_json:
            print(f"\nSkipping filter. Using: {roles_json}")
    else:
        if not history_json:
            print("Error: No work history JSON available for filtering.")
            sys.exit(1)
        roles_json = run_filter_roles(history_json, args.yes)
        if not roles_json:
            print("\nPipeline aborted at filter step.")
            sys.exit(1)

    # =========================================================================
    # Step 5: Validate companies
    # =========================================================================
    if args.skip_validate:
        companies_json_validated = args.input_companies
        if companies_json_validated:
            print(f"\nSkipping validate. Using: {companies_json_validated}")
    else:
        if not roles_json:
            print("Error: No roles JSON available for company validation.")
            sys.exit(1)
        companies_json_validated = run_validate_companies(
            roles_json,
            min_employees=args.min_employees,
            max_employees=args.max_employees,
            geo=args.geo,
            auto_confirm=args.yes,
        )
        if not companies_json_validated:
            print("\nPipeline aborted at validation step.")
            sys.exit(1)

    # =========================================================================
    # Step 6: Find personas
    # =========================================================================
    if args.skip_personas:
        personas_json = args.input_personas
        if personas_json:
            print(f"\nSkipping personas. Using: {personas_json}")
    else:
        if not companies_json_validated:
            print("Error: No validated companies JSON available for persona search.")
            sys.exit(1)
        personas_json = run_find_personas(companies_json_validated, args.yes)
        if not personas_json:
            print("\nPipeline aborted at persona search step.")
            sys.exit(1)

    # =========================================================================
    # Step 7: Generate emails
    # =========================================================================
    if args.skip_generate:
        emails_json = args.input_emails
        if emails_json:
            print(f"\nSkipping generate. Using: {emails_json}")
    else:
        if not personas_json:
            print("Error: No personas JSON available for email generation.")
            sys.exit(1)
        emails_json = run_generate_emails(personas_json, args.playbook, args.yes)
        if not emails_json:
            print("\nPipeline aborted at email generation step.")
            sys.exit(1)

    # =========================================================================
    # Step 8: Push to Apollo
    # =========================================================================
    if not args.skip_apollo:
        # Use emails_json if generated, otherwise fall back to personas_json
        apollo_input = emails_json if (emails_json and not args.skip_generate) else personas_json
        if not apollo_input:
            print("Error: No personas or emails JSON available for Apollo push.")
            sys.exit(1)
        success = run_push_to_apollo(
            apollo_input, args.source, args.sequence_id, args.yes,
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
        print(f"Master updated: master/{source_slug}_champions_master.csv")
        print("Contacts updated with champion email fields in Apollo.")
        if args.sequence_id:
            print(f"Contacts added to sequence: {args.sequence_id}")
    else:
        print("Emails generated. Run Apollo push manually or re-run without --skip-apollo.")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
