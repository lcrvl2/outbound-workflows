#!/bin/bash
# Step 2: scrape recent posts for each company.
# Usage: ./run_step2.sh <input.csv> <output-dir>
set -e
cd "$(dirname "$0")"

INPUT="${1:?usage: $0 <input.csv> <output-dir>}"
OUTPUT_DIR="${2:?usage: $0 <input.csv> <output-dir>}"

python3 scripts/scrape_posts.py \
  --input "$INPUT" \
  --output-dir "$OUTPUT_DIR" \
  --yes
