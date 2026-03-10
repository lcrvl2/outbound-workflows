#!/usr/bin/env python3
"""
Extract Intel - Use Claude Haiku to infer pain signals from LinkedIn profiles.

For each scraped profile, infers:
- pain_signal: the implied pain this person is hired to solve
- role_context: their situation with specificity
- seniority: junior/mid/senior/lead/director/vp/c-level
- confidence: high/medium/low

Contacts with confidence=low are flagged but NOT dropped (included in output
as skipped_low_confidence for transparency).

Input: profiles_scraped.json
Output: intel_extracted.json

Usage:
    python extract_intel.py <profiles_json> [--yes]
"""

import json
import sys
import os
import re
import time
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
REFERENCES_DIR = SKILL_DIR / 'references'

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
HAIKU_MODEL = 'claude-haiku-4-5-20251001'

BATCH_SIZE = 10
RATE_LIMIT_DELAY = 0.3


# =============================================================================
# PROMPT LOADING
# =============================================================================

def load_extraction_prompt():
    prompt_path = REFERENCES_DIR / 'extraction_prompt.md'
    if not prompt_path.exists():
        print(f"Error: extraction_prompt.md not found at {prompt_path}")
        sys.exit(1)
    return prompt_path.read_text(encoding='utf-8')


# =============================================================================
# EXTRACTION
# =============================================================================

def extract_intel_for_profile(client, system_prompt, profile_data):
    """Call Haiku to extract pain signal from a single profile"""
    profile = profile_data.get('profile', {})

    user_content = json.dumps({
        'headline': profile.get('headline', ''),
        'current_title': profile.get('current_title', ''),
        'current_company': profile_data.get('company', '') or profile.get('current_company', ''),
        'skills': profile.get('skills', []),
        'summary': profile.get('summary', ''),
    }, ensure_ascii=False)

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_content}],
        )

        raw_text = response.content[0].text.strip()

        # Strip markdown code fences if present
        raw_text = re.sub(r'^```(?:json)?\n?', '', raw_text)
        raw_text = re.sub(r'\n?```$', '', raw_text)

        intel = json.loads(raw_text)

        # Validate required fields
        for field in ('pain_signal', 'role_context', 'seniority', 'confidence'):
            if field not in intel:
                intel[field] = ''

        valid_confidences = ('high', 'medium', 'low')
        if intel.get('confidence') not in valid_confidences:
            intel['confidence'] = 'low'

        valid_seniorities = ('junior', 'mid', 'senior', 'lead', 'director', 'vp', 'c-level')
        if intel.get('seniority') not in valid_seniorities:
            intel['seniority'] = 'mid'

        return intel, None

    except json.JSONDecodeError as e:
        return None, f'json_parse_error: {e}'
    except Exception as e:
        return None, f'error: {str(e)}'


def extract_all_intel(profiles):
    """Extract pain signals for all profiles using Haiku"""
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system_prompt = load_extraction_prompt()

    results = []
    total = len(profiles)
    high_confidence = 0
    medium_confidence = 0
    low_confidence = 0
    errors = 0

    print(f"\nExtracting pain signals for {total} profiles (Haiku)...")

    for i, profile_data in enumerate(profiles, 1):
        name = f"{profile_data.get('first_name', '')} {profile_data.get('last_name', '')}".strip()
        display = name or profile_data.get('linkedin_url', f'contact_{i}')

        intel, error = extract_intel_for_profile(client, system_prompt, profile_data)

        if error:
            errors += 1
            print(f"  [{i}/{total}] {display}: extraction error ({error})")
            results.append({
                **profile_data,
                'intel': None,
                'extraction_error': error,
                'skip_generation': True,
            })
        else:
            confidence = intel.get('confidence', 'low')
            skip = confidence == 'low'

            if confidence == 'high':
                high_confidence += 1
            elif confidence == 'medium':
                medium_confidence += 1
            else:
                low_confidence += 1

            status = f"[{confidence}]" + (" SKIP" if skip else "")
            print(f"  [{i}/{total}] {display}: {status} — {intel.get('pain_signal', '')[:80]}")

            results.append({
                **profile_data,
                'intel': intel,
                'extraction_error': None,
                'skip_generation': skip,
            })

        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    print(f"\n  Confidence breakdown: {high_confidence} high, {medium_confidence} medium, {low_confidence} low (skipped), {errors} errors")
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Extract pain signals from scraped LinkedIn profiles'
    )
    parser.add_argument('profiles_json', help='Path to profiles_scraped.json')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("LINKEDIN PROFILE PERSONALIZER - STEP 3: EXTRACT INTEL")
    print("=" * 70)

    input_path = Path(args.profiles_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)

    # Cost estimate: ~$0.0003 per profile with Haiku
    est_cost = len(profiles) * 0.0003

    print(f"\nProfiles to process: {len(profiles)}")
    print(f"Model: {HAIKU_MODEL}")
    print(f"Estimated cost: ~${est_cost:.4f}")

    if not args.yes:
        print()
        response = input("Proceed with pain signal extraction? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    results = extract_all_intel(profiles)

    output_dir = input_path.parent
    output_path = output_dir / 'intel_extracted.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    will_generate = sum(1 for r in results if not r.get('skip_generation'))
    will_skip = len(results) - will_generate

    print(f"\n{'=' * 70}")
    print("EXTRACTION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total: {len(results)}")
    print(f"  Will generate hook: {will_generate}")
    print(f"  Will skip (low confidence / error): {will_skip}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
