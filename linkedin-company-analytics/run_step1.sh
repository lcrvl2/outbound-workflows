#!/bin/bash
# Step 1: scrape follower counts for each company.
# Usage: ./run_step1.sh <input.csv> <output-dir>
set -e
cd "$(dirname "$0")"

INPUT="${1:?usage: $0 <input.csv> <output-dir>}"
OUTPUT_DIR="${2:?usage: $0 <input.csv> <output-dir>}"

python3 scripts/scrape_followers.py \
  --input "$INPUT" \
  --output-dir "$OUTPUT_DIR" \
  --yes
