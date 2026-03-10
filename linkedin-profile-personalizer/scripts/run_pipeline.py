#!/usr/bin/env python3
"""
Run Pipeline - End-to-end LinkedIn profile personalization.

Orchestrates the full flow:
1. Load contacts from CSV (LinkedIn URLs + optional metadata)
2. Scrape LinkedIn profiles via Apify
3. Extract pain signals via Claude Haiku
4. Generate personalized hooks via Claude Sonnet
5. Export CSV + optionally push to Apollo

Usage:
    python run_pipeline.py --source NAME --input contacts.csv [options]

Options:
    --input PATH           Input CSV with LinkedIn URLs (required)
    --apollo-field-id ID   Apollo custom field ID to write hook to
    --sequence-id ID       Apollo sequence ID to enroll contacts into
    --col-linkedin COL     CSV column name for LinkedIn URL (if not auto-detected)
    --col-first-name COL   CSV column name for first name
    --col-last-name COL    CSV column name for last name
    --col-email COL        CSV column name for email
    --col-company COL      CSV column name for company
    --col-apollo-id COL    CSV column name for Apollo contact ID
    --yes                  Skip all confirmation prompts
    --skip-scrape          Skip scraping (provide --input-profiles)
    --skip-extract         Skip extraction (provide --input-intel)
    --skip-generate        Skip generation (provide --input-hooks)
    --skip-push            Skip Apollo push step (CSV export still runs)
    --input-profiles PATH  Use existing profiles_scraped.json
    --input-intel PATH     Use existing intel_extracted.json
    --input-hooks PATH     Use existing hooks_generated.json
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


def run_step(script_name, args_list, step_label):
    """Run a pipeline step as a subprocess"""
    print(f"\n{'=' * 70}")
    print(f"STEP: {step_label}")
    print(f"{'=' * 70}")

    cmd = [sys.executable, str(SCRIPTS_DIR / script_name)] + args_list

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nError: {step_label} failed (exit code {result.returncode})")
        sys.exit(result.returncode)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='LinkedIn Profile Personalizer - end-to-end pipeline'
    )
    parser.add_argument('--source', required=True, help='Source name (used for master tracking and output dirs)')
    parser.add_argument('--input', default=None, help='Input CSV path with LinkedIn URLs')

    # Column overrides
    parser.add_argument('--col-linkedin', default=None)
    parser.add_argument('--col-first-name', default=None)
    parser.add_argument('--col-last-name', default=None)
    parser.add_argument('--col-email', default=None)
    parser.add_argument('--col-company', default=None)
    parser.add_argument('--col-apollo-id', default=None)

    # Apollo output
    parser.add_argument('--apollo-field-id', default=None,
                        help='Apollo custom field ID for hook (required for Apollo push)')
    parser.add_argument('--sequence-id', default=None,
                        help='Apollo sequence ID to enroll contacts into')

    # Skip flags
    parser.add_argument('--skip-scrape', action='store_true')
    parser.add_argument('--skip-extract', action='store_true')
    parser.add_argument('--skip-generate', action='store_true')
    parser.add_argument('--skip-push', action='store_true')

    # Input overrides (for resumed/partial runs)
    parser.add_argument('--input-profiles', default=None, help='Use existing profiles_scraped.json')
    parser.add_argument('--input-intel', default=None, help='Use existing intel_extracted.json')
    parser.add_argument('--input-hooks', default=None, help='Use existing hooks_generated.json')

    parser.add_argument('--yes', '-y', action='store_true', help='Skip all confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("LINKEDIN PROFILE PERSONALIZER")
    print("=" * 70)
    print(f"Source: {args.source}")

    # Validate inputs
    if not args.skip_scrape and not args.input and not args.input_profiles:
        print("Error: --input CSV required (or --input-profiles to skip scraping)")
        sys.exit(1)

    # Create output directory
    output_dir = get_output_dir(args.source)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    yes_flag = ['--yes'] if args.yes else []

    # ==========================================================================
    # STEP 1: Load contacts
    # ==========================================================================
    contacts_path = output_dir / 'contacts_to_process.json'

    if not args.skip_scrape or not args.input_profiles:
        if args.input:
            step1_args = [
                str(args.input),
                '--source', args.source,
                '--output-dir', str(output_dir),
            ]
            for flag, val in [
                ('--col-linkedin', args.col_linkedin),
                ('--col-first-name', args.col_first_name),
                ('--col-last-name', args.col_last_name),
                ('--col-email', args.col_email),
                ('--col-company', args.col_company),
                ('--col-apollo-id', args.col_apollo_id),
            ]:
                if val:
                    step1_args += [flag, val]
            step1_args += yes_flag

            run_step('load_contacts.py', step1_args, 'Load Contacts')

            if not contacts_path.exists():
                print(f"Error: contacts_to_process.json not found in {output_dir}")
                sys.exit(1)

    # ==========================================================================
    # STEP 2: Scrape profiles
    # ==========================================================================
    profiles_path = Path(args.input_profiles) if args.input_profiles else output_dir / 'profiles_scraped.json'

    if not args.skip_scrape:
        run_step('scrape_profiles.py', [str(contacts_path)] + yes_flag, 'Scrape LinkedIn Profiles')

        if not profiles_path.exists():
            print(f"Error: profiles_scraped.json not found in {output_dir}")
            sys.exit(1)
    else:
        if not profiles_path.exists():
            print(f"Error: --input-profiles file not found: {profiles_path}")
            sys.exit(1)
        print(f"\n[SKIP] Scrape step — using: {profiles_path}")

    # ==========================================================================
    # STEP 3: Extract intel
    # ==========================================================================
    intel_path = Path(args.input_intel) if args.input_intel else output_dir / 'intel_extracted.json'

    if not args.skip_extract:
        run_step('extract_intel.py', [str(profiles_path)] + yes_flag, 'Extract Pain Signals')

        if not intel_path.exists():
            print(f"Error: intel_extracted.json not found in {output_dir}")
            sys.exit(1)
    else:
        if not intel_path.exists():
            print(f"Error: --input-intel file not found: {intel_path}")
            sys.exit(1)
        print(f"\n[SKIP] Extract step — using: {intel_path}")

    # ==========================================================================
    # STEP 4: Generate hooks
    # ==========================================================================
    hooks_path = Path(args.input_hooks) if args.input_hooks else output_dir / 'hooks_generated.json'

    if not args.skip_generate:
        run_step('generate_hooks.py', [str(intel_path)] + yes_flag, 'Generate Personalized Hooks')

        if not hooks_path.exists():
            print(f"Error: hooks_generated.json not found in {output_dir}")
            sys.exit(1)
    else:
        if not hooks_path.exists():
            print(f"Error: --input-hooks file not found: {hooks_path}")
            sys.exit(1)
        print(f"\n[SKIP] Generate step — using: {hooks_path}")

    # ==========================================================================
    # STEP 5: Push output
    # ==========================================================================
    if not args.skip_push:
        step5_args = [
            str(hooks_path),
            '--source', args.source,
        ]
        if args.apollo_field_id:
            step5_args += ['--apollo-field-id', args.apollo_field_id]
        if args.sequence_id:
            step5_args += ['--sequence-id', args.sequence_id]
        step5_args += yes_flag

        run_step('push_output.py', step5_args, 'Push Output')
    else:
        print(f"\n[SKIP] Push step")

    # ==========================================================================
    # DONE
    # ==========================================================================
    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Output directory: {output_dir}")
    print(f"CSV: {output_dir / 'personalized_hooks.csv'}")
    if args.apollo_field_id:
        print("Apollo: contacts patched with hook")
    if args.sequence_id:
        print(f"Sequence: {args.sequence_id}")


if __name__ == '__main__':
    main()
