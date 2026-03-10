#!/usr/bin/env python3
import sys
print("STEP 1: Starting script", flush=True)
sys.path.insert(0, '/Users/lucascarval/Desktop/Agentic Workflows/Outbound/churned-user-detector/scripts')
print("STEP 2: Path set", flush=True)

print("STEP 3: Importing detect_job_changes", flush=True)
import detect_job_changes
print("STEP 4: Import successful", flush=True)

print("STEP 5: Setting sys.argv", flush=True)
sys.argv = [
    'detect_job_changes.py',
    '/Users/lucascarval/Desktop/Agentic Workflows/Outbound/churned-user-detector/generated-outputs/churned-2026-02-24-2026-02-24/removed_users.json',
    '--source', 'churned-2026-02-24',
    '--max-concurrent-batches', '3',
    '--yes'
]
print(f"STEP 6: argv = {sys.argv}", flush=True)

print("STEP 7: Calling main()", flush=True)
detect_job_changes.main()
print("STEP 8: main() completed", flush=True)
