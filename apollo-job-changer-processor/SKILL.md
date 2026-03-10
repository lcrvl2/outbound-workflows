---
name: apollo-job-changer-processor
description: >
  Automate Apollo.io job changer enrichment workflow via Chrome DevTools MCP. Use when: (1) Processing
  job change updates from Current Users lists, (2) Accepting contact updates and creating new contacts
  in Apollo, (3) Enriching job changers across EN/FR/DACH lists into a global enriched list,
  (4) Pushing enriched contacts to Salesforce and campaigns. Triggers on "process job changers",
  "run job changer workflow", "enrich job changes", or any Apollo job changer management task.
  Requires Chrome with remote debugging enabled.
---

# Apollo Job Changer Processor

Automates Apollo.io job changer enrichment — from accepting job change updates across regional lists to pushing enriched contacts to Salesforce.

## Prerequisites

```bash
open -a "Google Chrome" --args --remote-debugging-port=9222
```

Log into Apollo.io in Chrome.

## Workflow

Load parameters from [references/workflow-configs.md](references/workflow-configs.md) at workflow start.

### Phase 1: Enrich Job Changers

Process each regional list sequentially (EN → FR → DACH).

For each list:

1. Navigate to the regional list URL → take snapshot
2. Scan for contacts with `button "Accept update"` badges. If none → skip to next list.
3. For each contact showing "update available":
   - Click `button "Accept update"` → Update Contact pop-up appears
   - In the pop-up, follow this exact sequence:

| Step | Action | Critical Notes |
|------|--------|----------------|
| a | Click `radio "Create new contact"` | Creates new record for the new job. Reveals stage dropdown. |
| b | Set outdated contact stage → click `combobox` → select "New" | |
| c | Click `StaticText "Show More Settings"` | **Must happen before step d — "Add to Lists" only appears after expanding** |
| d | Click "Add to Lists" `combobox` → type enriched list name → select from dropdown | |
| e | Click `StaticText "Mark current sequences as finished"` → verify via `evaluate_script` that checkbox `checked=true` | Hidden checkbox — not exposed in a11y tree |
| f | Click `button "Yes, Update"` | Final confirmation. Popup closes on success. |

4. Repeat until no `button "Accept update"` contacts remain
5. Track count of processed contacts per list

**Key constraint**: "Update available" is per-contact — there is no bulk action for this. Each contact must be processed individually.

### Phase 2: Process Enriched List

Navigate to the enriched list URL from config.

1. Check for any `button "Accept update"` badges in the enriched list itself — process them first using the Phase 1 flow
2. Click `button "Show Filters"` → expand "Email Status" → click `StaticText "Verified"` to filter for verified emails only
3. Click header `checkbox` to select all filtered contacts
4. In bulk toolbar: click `button "Salesforce"` → `menuitem "Push to Salesforce"` → wait for "Pushing to CRM" toast to disappear (take snapshot to confirm)
5. Re-open `button "Salesforce"` → `menuitem "Add to Salesforce Campaign"` → in modal, find `searchbox` → type campaign name → press Enter → select from dropdown → click `button "Save"`
6. Click `button "Open more actions"` → `menuitem "Remove from List"` → confirm in dialog → verify removal via success toast

### Phase 3: Clean Individual Lists

Remove all remaining contacts from each regional source list to reset for the next cycle.

For each list (EN → FR → DACH):

1. Navigate to the regional list URL → take snapshot
2. If list shows 0 records → skip
3. Click header `checkbox` to select all contacts
4. Click `button "Open more actions"` → `menuitem "Remove from List"` → confirm in dialog
5. Verify success toast and 0 records remaining

**Note**: "Create new contact" in Phase 1 auto-removes *some* OLD contacts from the source list, but not all. Always run Phase 3 to ensure complete cleanup.

## UI Validation (Circuit Breaker)

Before each phase, take a snapshot and verify that critical UI elements still exist. If any assertion fails, **STOP execution immediately** — Apollo's UI may have changed.

### Assertions by Phase

**Phase 1 — On any regional list with contacts:**
- `button "Accept update"` OR list shows 0 records (no badges = nothing to process, not a UI change)
- After clicking Accept: `radio "Create new contact"` exists in pop-up
- After selecting Create new contact: `StaticText "Show More Settings"` exists
- After expanding: `combobox` for "Add to Lists" exists

**Phase 2 — On enriched list:**
- `button "Show Filters"` exists
- After filtering + selecting: bulk toolbar `dialog` appears with `button "Salesforce"` and `button "Open more actions"`
- Salesforce dropdown contains `menuitem "Push to Salesforce"` and `menuitem "Add to Salesforce Campaign"`

**Phase 3 — On any list with contacts:**
- Header `checkbox` for select-all exists
- Bulk toolbar `dialog` appears with `button "Open more actions"`
- Dropdown contains `menuitem "Remove from List"`

### On Failure

If any assertion fails after 1 retry (take a fresh snapshot before retrying):

1. **STOP** — do not proceed with the current phase or any subsequent phase
2. **Log** — record which element was expected vs. what was found in the snapshot
3. **Switch mode** — update `mode` to `"interactive"` in [references/workflow-configs.md](references/workflow-configs.md)
4. **Notify user** — report the mismatch and recommend an interactive re-learning run to update [references/apollo-ui-patterns.md](references/apollo-ui-patterns.md)

This prevents the workflow from clicking wrong elements or silently failing when Apollo ships UI changes.

## Parameter Schema

Parameters are stored in [references/workflow-configs.md](references/workflow-configs.md). Required fields:

| Parameter | Description |
|-----------|-------------|
| `source_lists` | Regional list URLs (EN, FR, DACH) |
| `enriched_list` / `enriched_list_url` | Global destination for all enriched contacts |
| `sf_campaign` | Salesforce campaign name |
| `regions_to_process` | Which regions to run (default: all) |
| `mode` | "interactive" or "autonomous" |
| `ui_validation` | `true` (default) — run circuit breaker checks before each phase. Set `false` to skip. |

## Error Handling

- **Element not found**: Take snapshot → retry once → if still missing, log the issue and ask user.
- **No "update available" badges**: List has no job changes — skip and move to next list.
- **Chrome DevTools MCP "browser already running"**: Run `pkill -f "chrome-devtools-mcp/chrome-profile"` → MCP reconnects on next tool call.
- **`wait_for` timeout**: Take a snapshot instead to verify page state — toasts and async operations may not match expected text exactly.
- **"Mark sequences finished" checkbox**: Not exposed in a11y tree — always use `evaluate_script` to verify `checked=true` after clicking.

## References

- **UI Patterns**: [references/apollo-ui-patterns.md](references/apollo-ui-patterns.md) — job-changer-specific selectors (update badge, pop-up elements)
- **Shared UI Patterns**: [../apollo-lead-processor/references/apollo-ui-patterns.md](../apollo-lead-processor/references/apollo-ui-patterns.md) — shared bulk action selectors (Push to SF, Add to Campaign, etc.)
- **Saved Configs**: [references/workflow-configs.md](references/workflow-configs.md) — parameter presets
