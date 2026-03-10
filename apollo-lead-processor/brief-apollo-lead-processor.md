# Apollo Lead Processor — Operations Brief

## Context

Once a targeting campaign has been built (company list with matched contacts), the last-mile process of enrolling contacts into sequences, syncing to Salesforce, and suppressing worked companies is entirely manual in Apollo. A BDR typically clicks through 5–7 bulk actions per list, repeating the same flow for every new campaign batch. This is error-prone (wrong sequence, missed suppression) and slow (~30 min per list for a careful operator).

## Objective

Automate the full "list → sequence → CRM → suppression" handoff inside Apollo.io, so campaign contacts go from a raw company list to active outreach + Salesforce tracking in a single unattended run. Zero manual clicks after launch.

## Tools required

- **Apollo.io** — source company lists, people lists, sequences, Salesforce sync, suppression lists
- **Chrome DevTools MCP** — browser automation layer (controls Apollo's UI via accessibility tree, no Selenium/Playwright needed)
- **Chrome** — running with `--remote-debugging-port=9222`, logged into Apollo

## Campaign flow

### Step 1 — Select contacts from company list

- Navigate to the source **company list** (e.g. "Companies Hiring Social Media Positions")
- Use Apollo's built-in **"Select 3 contacts per company"** feature (single dropdown action)
- Result: N contacts selected across all companies in the list

### Step 2 — Add to destination people list

- Bulk action → **Add to List**
- Search and select the destination **people list** (e.g. "Final People List — Hiring Social Media Roles")
- Contacts now staged in a clean working list for processing

### Step 3 — Change ownership (by region)

- Navigate to the destination people list
- Select all contacts
- Bulk action → **Change Owner**
- Assign to the appropriate sales rep (region-based: NA, EMEA, APAC)

### Step 4 — Add to email sequence

- Bulk action → **Add to Sequence**
- Search and select the target sequence (e.g. "EN Companies Hiring Social Media Roles Email Sequence")
- Contacts are now enrolled and outreach begins on schedule

### Step 5 — Push to Salesforce

- Bulk action → **Push to Salesforce**
- Async operation — waits for CRM sync confirmation
- Contacts now exist as Leads/Contacts in Salesforce with full attribution

### Step 6 — Add to Salesforce campaign

- Bulk action → **Add to Salesforce Campaign**
- Search and select the tracking campaign (e.g. "Intent Job Hire Campaign")
- Enables campaign-level reporting and ROI tracking in Salesforce

### Step 7 — Suppress worked companies

- Switch to **Companies view** within the same list
- Select all companies
- Bulk action → **Add to List** (suppression company list)
- Prevents these companies from being targeted again in future campaign batches

### Step 8 — Cleanup

- Switch back to **People view**
- Select all contacts → **Remove from List**
- Resets the working people list to empty, ready for the next batch

## Execution modes

| Mode | Behavior | When to use |
|------|----------|-------------|
| **Interactive** | Pauses after each step, takes a snapshot, waits for user confirmation | First 2–3 runs (to discover and validate UI selectors) |
| **Autonomous** | Runs all 8 steps end-to-end, pauses only on errors | After UI patterns are validated |

## Error handling

- **Element not found**: take snapshot → retry once → if still missing, stop and switch to interactive mode
- **UI change detected** (circuit breaker): stop execution, log mismatch, notify user to re-learn patterns
- **Async timeout** (e.g. Salesforce push): snapshot-based verification — confirm toast/notification disappears before proceeding

## Parameters (per run)

| Parameter | Example |
|-----------|---------|
| Source company list | "NEW 2025-09 Growth Squad: Companies Hiring Social Media Positions (DMs)" |
| Destination people list | "NEW 2025-09 Growth Squad: Final People List Companies Hiring Social Media Roles" |
| Owner (sales rep) | Regional rep name |
| Sequence name | "2025-09 Growth Squad: EN Companies Hiring Social Media Roles Email Sequence" |
| Salesforce campaign | "2025 Growth Squad — Intent Job Hire Campaign (Parent)" |
| Suppression company list | "2025-09 Growth Squad — Companies Hiring Social Media Roles List" |

## Next steps

1. **First interactive run** — launch on a real campaign list to discover and document all Apollo UI selectors (button names, dropdown locations, modal flows)
2. **Validate patterns** — run 2–3 more interactive sessions across different campaign types to confirm selectors are stable
3. **Switch to autonomous** — once patterns are validated, run unattended on all new campaign batches
4. **Add regional routing** — extend owner assignment logic to handle NA / EMEA / APAC rep mapping automatically
5. **Schedule** — trigger via n8n workflow or macOS `launchd` on a weekly cadence (or on-demand per new campaign)
