# Apollo Job Changer Processor — Operations Brief

## Context

Apollo.io detects when contacts in your "Current Users" lists change jobs — a new company, a new title. These job changes surface as "Update available" badges on each contact, but accepting them is a per-contact manual process: open the popup, choose "Create new contact", set the stage, expand hidden settings, add to an enriched list, mark old sequences as finished, confirm. At scale across 3 regional lists (EN / FR / DACH), this takes 1–2 hours of repetitive clicking per weekly batch.

## Objective

Automate the full job changer enrichment pipeline: accept updates across all regional lists, consolidate into a single enriched list, push verified contacts to Salesforce + campaign, and reset all lists for the next cycle. One command, three phases, zero manual clicks.

## Tools required

- **Apollo.io** — source regional lists (Current Users), enriched destination list, Salesforce sync, campaign assignment
- **Chrome DevTools MCP** — browser automation layer (controls Apollo's UI via accessibility tree, no Selenium/Playwright needed)
- **Chrome** — running with `--remote-debugging-port=9222`, logged into Apollo

## Campaign flow

### Phase 1 — Enrich job changers (per-contact, across 3 regional lists)

Process each regional list sequentially: EN → FR → DACH.

For each contact showing an "Update available" badge:

1. Click **"Accept update"** — opens the Update Contact popup
2. Select **"Create new contact"** — creates a fresh record for the new job (keeps the old one intact)
3. Set outdated contact stage to **"New"** via the stage dropdown
4. Click **"Show More Settings"** — reveals hidden fields (Add to Lists, Mark sequences finished)
5. In **"Add to Lists"** — search and select the global enriched list
6. Enable **"Mark current sequences as finished"** — stops old sequences on the outdated contact (hidden checkbox, must verify via JavaScript)
7. Click **"Yes, Update"** — confirms and closes the popup
8. Repeat until no more "Update available" badges remain on the list

Move to the next regional list. Repeat.

**Output**: All job changers consolidated into one global enriched list.

### Phase 2 — Process enriched list (bulk actions)

Navigate to the global enriched list, then:

1. **Filter for verified emails only** — open Filters sidebar → select "Verified" under Email Status (don't send to unverified/catch-all)
2. **Select all** filtered contacts
3. **Push to Salesforce** — async operation, wait for CRM sync confirmation (toast-based verification)
4. **Add to Salesforce Campaign** — search campaign name, press Enter to trigger search, select from results, save
5. **Remove from list** — cleans the enriched list back to zero, ready for the next cycle

**Output**: Verified contacts synced to Salesforce with campaign attribution.

### Phase 3 — Clean regional source lists (reset for next cycle)

For each regional list (EN → FR → DACH):

1. Navigate to the list
2. If contacts remain (Phase 1's "Create new contact" removes some but not all), select all → **Remove from List**
3. Verify 0 records remaining

**Output**: All 3 regional lists empty and ready for the next batch of job change updates.

## Execution modes

| Mode | Behavior | When to use |
|------|----------|-------------|
| **Interactive** | Pauses after each contact (Phase 1) or each bulk action (Phase 2–3), shows snapshot | First run — to discover and validate UI selectors |
| **Autonomous** | Runs all 3 phases end-to-end, pauses only on errors | After UI patterns are validated (current mode since 2026-02-09) |

## Error handling

- **UI circuit breaker**: before each phase, verify critical UI elements exist (e.g. "Accept update" button, "Show Filters" button, bulk toolbar). If any assertion fails → stop, switch to interactive mode, notify user
- **Hidden checkbox verification**: "Mark sequences finished" checkbox is not in the accessibility tree — use `evaluate_script` to verify `checked=true` after clicking the label
- **Async operations** (Salesforce push): snapshot-based verification — confirm toast disappears before proceeding
- **Empty lists**: if a regional list has 0 contacts with update badges, skip to the next list (not a failure)

## Parameters (per run)

| Parameter | Example |
|-----------|---------|
| EN source list | "2025-09 Growth Squad — Current Users Who Change Jobs" |
| FR source list | "2025-09 Growth Squad — Current Users Who Change Jobs (FR)" |
| DACH source list | "2025-09 Growth Squad — Current Users Who Change Jobs (DACH)" |
| Enriched destination list | "2026-02 Job changers intent — Global (ENRICHED)" |
| Salesforce campaign | "2025 Growth Squad — Intent Job Changers Campaign (Parent)" |
| Outdated contact stage | "New" |
| Mark sequences finished | Always enabled |
| Regions to process | ["EN", "FR", "DACH"] (configurable subset) |

## Key gotchas

- **Phase 1 is per-contact, not bulk** — no way around it, Apollo doesn't offer bulk enrichment for job changers. Large batches take proportionally longer.
- **"Show More Settings" must be clicked before "Add to Lists"** — the combobox only appears after expanding. Skipping this step = contacts not added to the enriched list.
- **Campaign search requires pressing Enter** — typing alone won't trigger results. Miss this and the modal hangs with no results.
- **Phase 3 cleanup is mandatory** — Phase 1 auto-removes some old contacts but not all. Skipping Phase 3 leaves stale records that pollute the next cycle.

## Next steps

1. **Continue weekly runs** — autonomous mode validated since 2026-02-09, run whenever job change updates accumulate
2. **Monitor for UI changes** — if any circuit breaker assertion fails, switch back to interactive to re-learn selectors
3. **Add Slack notification** — n8n workflow to alert when a run completes (contacts processed, contacts pushed to SF)
4. **Track volume trends** — log processed counts per region per week to spot patterns (e.g. Q1 job change spikes)
