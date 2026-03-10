#!/usr/bin/env python3
"""
Run Pipeline - Orchestrate all 5 steps of competitor follower list building.

Pipeline:
1. Extract followers from LinkedIn company pages (Apify)
2. Deduplicate across competitors (master file)
3. Qualify companies by ICP (Apollo native filters)
4. Find 2-3 decision-makers per company (Apollo people search)
5. Enrich contacts + split CSV output (suppression check)

Output: contacts_enriched.csv + contacts_needs_enrichment.csv

Usage:
    python run_pipeline.py \
        --source NAME \
        --competitors "URL1,URL2,URL3" \
        [--max-followers N] \
        [--contacts-per-company N] \
        [--min-employees N] \
        [--max-employees N] \
        [--persona-titles "title1,title2,title3"] \
        [--no-cleanup] \
        [--skip-extract] [--skip-dedupe] [--skip-qualify] [--skip-personas] [--skip-enrich]
"""

import subprocess
import sys
import os
import shutil
import argparse
from pathlib import Path
from datetime import date

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / 'scripts'
GENERATED_DIR = SKILL_DIR / 'generated-outputs'

DEFAULT_MAX_FOLLOWERS = 5000
DEFAULT_CONTACTS_PER_COMPANY = 3
DEFAULT_MIN_EMPLOYEES = 200
DEFAULT_MAX_EMPLOYEES = 2000


# =============================================================================
# HELPERS
# =============================================================================

def run_script(script_name, args, description):
    """Run a Python script and handle errors"""
    print(f"\n{'=' * 70}")
    print(f"STEP: {description}")
    print(f"{'=' * 70}")

    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args

    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=SKILL_DIR)

    if result.returncode != 0:
        print(f"\n✗ Error running {script_name}")
        print(f"  Exit code: {result.returncode}")
        sys.exit(1)

    print(f"\n✓ {description} completed")


def normalize_source_name(source_name):
    """Normalize source name for directory naming"""
    import re
    name = re.sub(r'[^\w\s-]', '', source_name.lower())
    name = re.sub(r'\s+', '_', name)
    return name


def get_run_dir(source_name):
    """Get timestamped output directory for this run"""
    normalized = normalize_source_name(source_name)
    today = date.today().isoformat()
    return GENERATED_DIR / f'{normalized}-{today}'


# =============================================================================
# PIPELINE STEPS
# =============================================================================

def step_1_extract(run_dir, competitors, max_followers):
    """Step 1: Extract followers via Apify"""
    output_json = run_dir / 'followers_raw.json'

    args = [
        str(output_json),
        '--competitors', competitors,
        '--max-followers', str(max_followers),
    ]

    run_script('extract_followers.py', args, 'Extract Followers (Apify)')
    return output_json


def step_2_dedupe(run_dir, input_json, source_name):
    """Step 2: Deduplicate across competitors"""
    output_json = run_dir / 'followers_deduped.json'

    args = [
        str(input_json),
        str(output_json),
        '--source', source_name,
    ]

    run_script('dedupe_followers.py', args, 'Deduplicate Followers (Master File)')
    return output_json


def step_3_qualify(run_dir, input_json, min_employees, max_employees):
    """Step 3: Qualify companies by ICP (Apollo native filters)"""
    output_json = run_dir / 'companies_qualified.json'

    args = [
        str(input_json),
        str(output_json),
        '--min-employees', str(min_employees),
        '--max-employees', str(max_employees),
    ]

    run_script('qualify_companies.py', args, 'Qualify Companies (ICP Filter)')
    return output_json


def step_4_find_personas(run_dir, input_json, contacts_per_company, persona_titles):
    """Step 4: Find decision-makers at qualified companies"""
    output_json = run_dir / 'personas_found.json'

    args = [
        str(input_json),
        str(output_json),
        '--contacts-per-company', str(contacts_per_company),
    ]

    if persona_titles:
        args.extend(['--persona-titles', persona_titles])

    run_script('find_personas.py', args, 'Find Decision-Makers (Personas)')
    return output_json


def step_5_enrich(run_dir, input_json):
    """Step 5: Enrich contacts + CSV output"""
    args = [
        str(input_json),
        str(run_dir),
    ]

    run_script('enrich_contacts.py', args, 'Enrich Contacts + CSV Output')

    enriched_csv = run_dir / 'contacts_enriched.csv'
    needs_enrichment_csv = run_dir / 'contacts_needs_enrichment.csv'

    return enriched_csv, needs_enrichment_csv


# =============================================================================
# CLEANUP
# =============================================================================

def cleanup_intermediates(run_dir):
    """Remove intermediate JSON files (keep only final CSVs)"""
    intermediates = [
        'followers_raw.json',
        'followers_deduped.json',
        'companies_qualified.json',
        'personas_found.json',
    ]

    print(f"\n{'=' * 70}")
    print("CLEANUP")
    print(f"{'=' * 70}")

    for filename in intermediates:
        file_path = run_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"  Removed: {filename}")

    print("\n✓ Cleanup complete (kept only CSV files)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Run complete competitor follower list building pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pilot run (1k followers from Hootsuite)
  python run_pipeline.py \\
    --source "hootsuite_pilot_feb_2026" \\
    --competitors "https://www.linkedin.com/company/hootsuite/" \\
    --max-followers 1000

  # Full extraction (5 competitors, no cap)
  python run_pipeline.py \\
    --source "competitor_followers_full_feb_2026" \\
    --competitors "https://www.linkedin.com/company/hootsuite/,https://www.linkedin.com/company/sprout-social-inc/,https://www.linkedin.com/company/sprinklr/" \\
    --max-followers 0 \\
    --contacts-per-company 3

  # Resume from checkpoint (skip extraction)
  python run_pipeline.py \\
    --source "hootsuite_pilot_feb_2026" \\
    --skip-extract \\
    --input-followers generated-outputs/hootsuite_pilot_feb_2026-2026-02-13/followers_raw.json
        """
    )

    # Required
    parser.add_argument('--source', required=True, help='Source identifier (e.g., "hootsuite_pilot_feb_2026")')

    # Extraction
    parser.add_argument('--competitors', help='Comma-separated LinkedIn company URLs (required unless --skip-extract)')
    parser.add_argument('--max-followers', type=int, default=DEFAULT_MAX_FOLLOWERS,
                        help=f'Max followers per competitor (default: {DEFAULT_MAX_FOLLOWERS}, 0 = unlimited)')

    # ICP filters
    parser.add_argument('--min-employees', type=int, default=DEFAULT_MIN_EMPLOYEES,
                        help=f'Minimum employee count (default: {DEFAULT_MIN_EMPLOYEES})')
    parser.add_argument('--max-employees', type=int, default=DEFAULT_MAX_EMPLOYEES,
                        help=f'Maximum employee count (default: {DEFAULT_MAX_EMPLOYEES})')

    # Persona search
    parser.add_argument('--contacts-per-company', type=int, default=DEFAULT_CONTACTS_PER_COMPANY,
                        help=f'Decision-makers per company (default: {DEFAULT_CONTACTS_PER_COMPANY})')
    parser.add_argument('--persona-titles', default=None,
                        help='Comma-separated target titles (overrides defaults)')

    # Flags
    parser.add_argument('--no-cleanup', action='store_true',
                        help='Keep intermediate JSON files (default: remove after completion)')

    # Skip flags (for partial runs)
    parser.add_argument('--skip-extract', action='store_true', help='Skip follower extraction')
    parser.add_argument('--skip-dedupe', action='store_true', help='Skip deduplication')
    parser.add_argument('--skip-qualify', action='store_true', help='Skip ICP qualification')
    parser.add_argument('--skip-personas', action='store_true', help='Skip persona search')
    parser.add_argument('--skip-enrich', action='store_true', help='Skip enrichment')

    # Input overrides (for partial runs)
    parser.add_argument('--input-followers', help='Input for dedupe (if --skip-extract)')
    parser.add_argument('--input-deduped', help='Input for qualify (if --skip-dedupe)')
    parser.add_argument('--input-companies', help='Input for personas (if --skip-qualify)')
    parser.add_argument('--input-personas', help='Input for enrich (if --skip-personas)')

    args = parser.parse_args()

    # Validation
    if not args.skip_extract and not args.competitors:
        print("Error: --competitors required unless --skip-extract is used")
        sys.exit(1)

    print("=" * 70)
    print("COMPETITOR FOLLOWER LIST BUILDER")
    print("=" * 70)
    print(f"\nSource: {args.source}")
    print(f"Max followers per competitor: {args.max_followers if args.max_followers > 0 else 'UNLIMITED'}")
    print(f"ICP: {args.min_employees:,} - {args.max_employees:,} employees")
    print(f"Contacts per company: {args.contacts_per_company}")

    # Create run directory
    run_dir = get_run_dir(args.source)
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {run_dir}")

    # Pipeline execution
    current_output = None

    # Step 1: Extract
    if not args.skip_extract:
        current_output = step_1_extract(run_dir, args.competitors, args.max_followers)
    else:
        if not args.input_followers:
            print("Error: --input-followers required when --skip-extract is used")
            sys.exit(1)
        current_output = Path(args.input_followers)
        print(f"\n✓ Skipping extraction (using: {current_output})")

    # Step 2: Dedupe
    if not args.skip_dedupe:
        current_output = step_2_dedupe(run_dir, current_output, args.source)
    else:
        if not args.input_deduped:
            print("Error: --input-deduped required when --skip-dedupe is used")
            sys.exit(1)
        current_output = Path(args.input_deduped)
        print(f"\n✓ Skipping deduplication (using: {current_output})")

    # Step 3: Qualify
    if not args.skip_qualify:
        current_output = step_3_qualify(run_dir, current_output, args.min_employees, args.max_employees)
    else:
        if not args.input_companies:
            print("Error: --input-companies required when --skip-qualify is used")
            sys.exit(1)
        current_output = Path(args.input_companies)
        print(f"\n✓ Skipping qualification (using: {current_output})")

    # Step 4: Find Personas
    if not args.skip_personas:
        current_output = step_4_find_personas(run_dir, current_output, args.contacts_per_company, args.persona_titles)
    else:
        if not args.input_personas:
            print("Error: --input-personas required when --skip-personas is used")
            sys.exit(1)
        current_output = Path(args.input_personas)
        print(f"\n✓ Skipping persona search (using: {current_output})")

    # Step 5: Enrich
    if not args.skip_enrich:
        enriched_csv, needs_enrichment_csv = step_5_enrich(run_dir, current_output)
    else:
        print(f"\n✓ Skipping enrichment")
        enriched_csv = run_dir / 'contacts_enriched.csv'
        needs_enrichment_csv = run_dir / 'contacts_needs_enrichment.csv'

    # Cleanup
    if not args.no_cleanup:
        cleanup_intermediates(run_dir)

    # Final summary
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print("\nOutput files:")
    if enriched_csv.exists():
        print(f"  ✓ {enriched_csv.name} (ready for outreach)")
    if needs_enrichment_csv.exists():
        print(f"  ✓ {needs_enrichment_csv.name} (needs manual enrichment)")
    print(f"\nLocation: {run_dir}")
    print("\nNext steps:")
    print("1. Review contacts_enriched.csv")
    print("2. Import to Apollo/Instantly for sequence enrollment")
    print("3. (Optional) Manually enrich contacts_needs_enrichment.csv")


if __name__ == '__main__':
    main()
