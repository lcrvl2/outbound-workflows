#!/usr/bin/env python3
"""Launch step 1 (scrape_followers) and step 2 (scrape_posts) directly."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

INPUT_CSV = '/Users/lucascarval/Desktop/Agentic Workflows/Outbound/ABM accounts.csv'
OUTPUT_DIR = '/Users/lucascarval/Desktop/Agentic Workflows/Outbound/linkedin-company-analytics/generated-outputs/abm_accounts_feb2026-2026-02-18'

step = sys.argv[1] if len(sys.argv) > 1 else '1'

if step == '1':
    sys.argv = [
        'scrape_followers.py',
        '--input', INPUT_CSV,
        '--output-dir', OUTPUT_DIR,
        '--yes',
    ]
    from scripts.scrape_followers import main
    main()
elif step == '2':
    sys.argv = [
        'scrape_posts.py',
        '--input', INPUT_CSV,
        '--output-dir', OUTPUT_DIR,
        '--yes',
    ]
    from scripts.scrape_posts import main
    main()
