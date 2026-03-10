#!/usr/bin/env python3
"""
Enrich Master — Add derived fields to master CSV.

Adds:
  - posting_frequency_category: "Infrequent" (0-2) or "Frequent" (3-5) based on posting_range

Usage:
    python scripts/enrich_master.py --master master/abm_accounts_master.csv
"""

import csv
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass


# =============================================================================
# ENRICHMENT
# =============================================================================

def enrich_row(row):
    """Add derived fields to a single row."""
    enriched = row.copy()

    # posting_frequency_category based on posting_range
    posting_range = row.get('posting_range', '').strip()

    if posting_range == '':
        # No posting data available
        enriched['posting_frequency_category'] = ''
    else:
        try:
            range_value = int(posting_range)
            if range_value <= 2:
                enriched['posting_frequency_category'] = 'Infrequent'
            else:
                enriched['posting_frequency_category'] = 'Frequent'
        except (ValueError, TypeError):
            enriched['posting_frequency_category'] = ''

    return enriched


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Enrich master CSV with derived fields')
    parser.add_argument('--master', required=True, help='Path to master CSV')

    args = parser.parse_args()

    master_path = Path(args.master)

    if not master_path.exists():
        print(f"Error: Master file not found: {master_path}")
        sys.exit(1)

    print("=" * 70)
    print("ENRICH MASTER CSV")
    print("=" * 70)
    print(f"Master: {master_path}")
    print()

    # Load and enrich
    rows = []
    with open(master_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        original_fieldnames = reader.fieldnames

        for row in reader:
            enriched = enrich_row(row)
            rows.append(enriched)

    print(f"✓ Loaded {len(rows)} companies")

    # Count categories
    infrequent = sum(1 for r in rows if r.get('posting_frequency_category') == 'Infrequent')
    frequent = sum(1 for r in rows if r.get('posting_frequency_category') == 'Frequent')
    no_data = sum(1 for r in rows if r.get('posting_frequency_category') == '')

    print(f"\nPosting Frequency Distribution:")
    print(f"  Infrequent (0-2): {infrequent:4d} companies ({infrequent/len(rows)*100:5.1f}%)")
    print(f"  Frequent (3-5):   {frequent:4d} companies ({frequent/len(rows)*100:5.1f}%)")
    print(f"  No data:          {no_data:4d} companies ({no_data/len(rows)*100:5.1f}%)")

    # Write enriched file
    new_fieldnames = list(original_fieldnames)

    # Insert posting_frequency_category after posting_range_label
    if 'posting_range_label' in new_fieldnames:
        insert_idx = new_fieldnames.index('posting_range_label') + 1
        new_fieldnames.insert(insert_idx, 'posting_frequency_category')
    else:
        new_fieldnames.append('posting_frequency_category')

    with open(master_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ Wrote enriched master to: {master_path}")

    print()
    print("=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print("New fields added:")
    print("  - posting_frequency_category (Infrequent/Frequent)")
    print("=" * 70)


if __name__ == '__main__':
    main()
