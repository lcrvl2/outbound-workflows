#!/bin/bash
cd "$(dirname "$0")"
python3 scripts/scrape_posts.py \
  --input "../ABM accounts.csv" \
  --output-dir "generated-outputs/abm_accounts_feb2026-2026-02-18" \
  --yes
