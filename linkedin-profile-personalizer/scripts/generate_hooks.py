#!/usr/bin/env python3
"""
Generate Hooks - Use Claude Sonnet to write personalized email opening hooks.

For each contact with high/medium confidence intel, generates a 1-2 sentence
personalized hook. Validates against banned phrases with up to 2 retries.

Input: intel_extracted.json
Output: hooks_generated.json

Usage:
    python generate_hooks.py <intel_json> [--yes]
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
SONNET_MODEL = 'claude-sonnet-4-6'

MAX_RETRIES = 2
RATE_LIMIT_DELAY = 0.5


# =============================================================================
# BANNED PHRASE VALIDATOR
# =============================================================================

BANNED_PATTERNS = [
    (re.compile(r'\bwhich means\b', re.IGNORECASE), '"which means"'),
    (re.compile(r'\bthat means\b', re.IGNORECASE), '"that means"'),
    (re.compile(r'\bmost\s+(teams|managers|marketers|agencies|companies|brands|leaders)\b', re.IGNORECASE), '"most [teams/etc]"'),
    (re.compile(r'\bfrom what I\'ve seen\b', re.IGNORECASE), '"from what I\'ve seen"'),
    (re.compile(r'\bbrowser[\s-]*(tabs?|switching)\b', re.IGNORECASE), '"browser tabs/switching"'),
    (re.compile(r'\bplatform[\s-]*hopping\b', re.IGNORECASE), '"platform-hopping"'),
    (re.compile(r'\bdrowning\s+in\b', re.IGNORECASE), '"drowning in"'),
    (re.compile(r'\bjuggling\b', re.IGNORECASE), '"juggling"'),
    (re.compile(r'\bchaos\b', re.IGNORECASE), '"chaos"'),
    (re.compile(r'\boverwhelm', re.IGNORECASE), '"overwhelm"'),
    (re.compile(r'^Hi\s', re.MULTILINE), '"Hi " at start'),
    (re.compile(r'\bthat\'s\s+a\s+lot\b', re.IGNORECASE), '"that\'s a lot"'),
    (re.compile(r'\bthat\'s\s+(hard|tough)\s+when\b', re.IGNORECASE), '"that\'s hard/tough when"'),
    (re.compile(r'\b(one|single|unified)\s+(inbox|place|calendar|view|system|workspace|dashboard|platform|feed|tool)\b', re.IGNORECASE), '"one/single/unified [noun]"'),
    (re.compile(r'\bI\s+(saw|noticed|came\s+across)\s+that\b', re.IGNORECASE), '"I saw/noticed that"'),
    (re.compile(r'\blove\s+what\s+you\'re\s+building\b', re.IGNORECASE), '"love what you\'re building"'),
    (re.compile(r'\bI\s+know\s+you\b', re.IGNORECASE), '"I know you"'),
    (re.compile(r'\byou\s+(struggle|face|deal\s+with)\b', re.IGNORECASE), '"you struggle/face"'),
]


def check_banned_phrases(hook_text):
    """Returns list of (label, matched_text) for any violations"""
    violations = []
    for pattern, label in BANNED_PATTERNS:
        match = pattern.search(hook_text)
        if match:
            violations.append((label, match.group()))
    return violations


def count_question_marks(text):
    return text.count('?')


def count_words(text):
    return len(text.split())


# =============================================================================
# PROMPT LOADING
# =============================================================================

def load_hook_prompt():
    prompt_path = REFERENCES_DIR / 'hook_generation_prompt.md'
    if not prompt_path.exists():
        print(f"Error: hook_generation_prompt.md not found at {prompt_path}")
        sys.exit(1)
    return prompt_path.read_text(encoding='utf-8')


# =============================================================================
# GENERATION
# =============================================================================

def generate_hook_for_contact(client, system_prompt, contact_data, attempt=1):
    """Call Sonnet to generate a personalized hook"""
    intel = contact_data.get('intel', {}) or {}
    profile = contact_data.get('profile', {}) or {}

    user_content = json.dumps({
        'first_name': contact_data.get('first_name', ''),
        'current_company': contact_data.get('company', '') or profile.get('current_company', ''),
        'pain_signal': intel.get('pain_signal', ''),
        'role_context': intel.get('role_context', ''),
        'headline': profile.get('headline', ''),
    }, ensure_ascii=False)

    if attempt > 1:
        user_content += f"\n\n[Attempt {attempt}: previous attempt had banned phrases. Rewrite from scratch.]"

    try:
        response = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=200,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_content}],
        )

        raw_text = response.content[0].text.strip()
        raw_text = re.sub(r'^```(?:json)?\n?', '', raw_text)
        raw_text = re.sub(r'\n?```$', '', raw_text)

        result = json.loads(raw_text)
        hook = result.get('hook', '').strip()
        return hook, None

    except json.JSONDecodeError as e:
        return None, f'json_parse_error: {e}'
    except Exception as e:
        return None, f'error: {str(e)}'


def generate_all_hooks(contacts_with_intel):
    """Generate hooks for all contacts that passed confidence threshold"""
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system_prompt = load_hook_prompt()

    to_generate = [c for c in contacts_with_intel if not c.get('skip_generation')]
    to_skip = [c for c in contacts_with_intel if c.get('skip_generation')]

    total = len(to_generate)
    print(f"\nGenerating hooks for {total} contacts (Sonnet), skipping {len(to_skip)} (low confidence)...")

    results = []
    generated = 0
    failed = 0
    warned = 0

    for i, contact_data in enumerate(to_generate, 1):
        name = f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip()
        display = name or contact_data.get('linkedin_url', f'contact_{i}')

        hook = None
        error = None
        warnings = []

        for attempt in range(1, MAX_RETRIES + 2):
            raw_hook, err = generate_hook_for_contact(client, system_prompt, contact_data, attempt)

            if err:
                error = err
                break

            violations = check_banned_phrases(raw_hook)
            word_count = count_words(raw_hook)
            question_count = count_question_marks(raw_hook)

            if violations and attempt <= MAX_RETRIES:
                violation_labels = ', '.join(v[0] for v in violations)
                print(f"  [{i}/{total}] {display}: banned phrases ({violation_labels}), retry {attempt}/{MAX_RETRIES}")
                time.sleep(RATE_LIMIT_DELAY)
                continue

            if violations:
                warnings = [f"banned phrase: {v[0]}" for v in violations]
                warned += 1

            if word_count > 40:
                warnings.append(f"over 40 words ({word_count})")

            if question_count > 0:
                warnings.append(f"contains question mark ({question_count})")

            hook = raw_hook
            break

        if hook:
            generated += 1
            status = f"✓ ({count_words(hook)} words)"
            if warnings:
                status += f" [WARN: {', '.join(warnings)}]"
            print(f"  [{i}/{total}] {display}: {status}")
            results.append({
                **contact_data,
                'hook': hook,
                'hook_warnings': warnings,
                'hook_error': None,
            })
        else:
            failed += 1
            print(f"  [{i}/{total}] {display}: FAILED ({error})")
            results.append({
                **contact_data,
                'hook': None,
                'hook_warnings': [],
                'hook_error': error,
            })

        time.sleep(RATE_LIMIT_DELAY)

    # Add skipped contacts to output (no hook)
    for contact_data in to_skip:
        results.append({
            **contact_data,
            'hook': None,
            'hook_warnings': [],
            'hook_error': 'skipped_low_confidence',
        })

    print(f"\n  Generated: {generated}, Failed: {failed}, Warned: {warned}, Skipped: {len(to_skip)}")
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate personalized email hooks from extracted intel'
    )
    parser.add_argument('intel_json', help='Path to intel_extracted.json')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')

    args = parser.parse_args()

    print("=" * 70)
    print("LINKEDIN PROFILE PERSONALIZER - STEP 4: GENERATE HOOKS")
    print("=" * 70)

    input_path = Path(args.intel_json)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        contacts = json.load(f)

    to_generate = [c for c in contacts if not c.get('skip_generation')]
    to_skip = len(contacts) - len(to_generate)

    # Cost estimate: ~$0.003 per hook with Sonnet
    est_cost = len(to_generate) * 0.003

    print(f"\nContacts to generate: {len(to_generate)}")
    print(f"Contacts to skip (low confidence): {to_skip}")
    print(f"Model: {SONNET_MODEL}")
    print(f"Estimated cost: ~${est_cost:.4f}")

    if not args.yes:
        print()
        response = input("Proceed with hook generation? [y/N] ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    results = generate_all_hooks(contacts)

    output_dir = input_path.parent
    output_path = output_dir / 'hooks_generated.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    with_hook = sum(1 for r in results if r.get('hook'))
    print(f"\n{'=' * 70}")
    print("GENERATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total contacts: {len(results)}")
    print(f"  With hook: {with_hook}")
    print(f"  Without hook: {len(results) - with_hook}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
