#!/usr/bin/env python3
"""Launch step 1 (scrape_followers) and step 2 (scrape_posts) directly.

Usage:
    python run_steps.py <step> --input <csv> --output-dir <dir> [--yes]

<step> is 1 or 2. Remaining arguments are passed straight through to the
underlying script, so see its --help for the full list.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if len(sys.argv) < 2 or sys.argv[1] not in ('1', '2'):
    sys.exit(__doc__)

step, passthrough = sys.argv[1], sys.argv[2:]

if step == '1':
    sys.argv = ['scrape_followers.py'] + passthrough
    from scripts.scrape_followers import main
else:
    sys.argv = ['scrape_posts.py'] + passthrough
    from scripts.scrape_posts import main

main()
