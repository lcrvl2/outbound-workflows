#!/bin/bash
# Hootsuite (ow.ly) weekly tracking
# Runs Monday 7:00 AM

set -e

SKILL_DIR="/Users/lucascarval/Desktop/Agentic Workflows/Outbound/Mentions-enrichment"
cd "$SKILL_DIR"

COMPETITOR="hootsuite"
DATA_DIR="data/$COMPETITOR"
ALERT_ID="2718028"  # ow.ly mentions alert
SOURCE="hootsuite"

# Calculate since-date (7 days ago)
SINCE_DATE=$(date -v-7d +%Y-%m-%d)

echo "=== Weekly $COMPETITOR tracking ==="
echo "Since date: $SINCE_DATE"

# Run pipeline (--yes skips all confirmation prompts for cron)
python3 scripts/run_pipeline.py \
  --alert-id "$ALERT_ID" \
  --source "$SOURCE" \
  --data-dir "$DATA_DIR" \
  --since-date "$SINCE_DATE" \
  --threshold 10000 \
  --min-employees 200 \
  --yes

echo "=== $COMPETITOR tracking complete ==="
