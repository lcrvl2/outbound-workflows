---
name: apollo-lead-processor
description: >
  Automate Apollo.io lead management workflows via Chrome DevTools MCP. Use when: (1) Processing
  leads from company lists into sequences, (2) Selecting contacts per company and adding to lists,
  (3) Changing ownership, adding to sequences, pushing to Salesforce, (4) Managing suppression
  lists. Triggers on "process Apollo leads", "run Apollo workflow", "add contacts to sequence",
  or any Apollo list/sequence management task. Requires Chrome with remote debugging enabled.
---

# Apollo Lead Processor

Automates Apollo.io lead management via Chrome DevTools MCP - from company list to sequence enrollment.

## Prerequisites

```bash
# Start Chrome with remote debugging
open -a "Google Chrome" --args --remote-debugging-port=9222
```

Then: Log into Apollo.io in Chrome.

## Execution Modes

| Mode | Behavior | When to Use |
|------|----------|-------------|
| **interactive** | Pause after each action, show snapshot, wait for confirmation | First runs, learning UI |
| **autonomous** | Run full workflow, pause only on errors | After 2-3 successful interactive runs |

## Workflow

```
Source Company List
  → Select 3 contacts per company
    → Add to People List
      → Change ownership (by region)
        → Add to Email Sequence
          → Push to Salesforce
            → Add to SF Campaign
              → View Companies → Add to Suppression List
                → Cleanup: Remove from People List
```

## Step-by-Step Guide

### 1. Navigate to Source List

1. Take snapshot (`mcp__chrome-devtools__take_snapshot`)
2. Verify on correct list or navigate to it
3. **Checkpoint**: "On source list [name]. Ready to select contacts?"

### 2. Select Contacts (3 per Company)

1. Find selection dropdown/checkbox
2. Click "Select 3 contacts per company" (Apollo built-in feature)
3. Wait for selection count to update
4. **Checkpoint**: "X contacts selected. Add to destination list?"

### 3. Add to Destination People List

1. Click bulk action menu → "Add to List"
2. Search for destination list
3. Select and confirm
4. **Checkpoint**: "Contacts added to [list]. Navigate to process?"

### 4. Process People List

Navigate to destination list, then:

| Action | Steps |
|--------|-------|
| **4a. Select All** | Click select all checkbox |
| **4b. Change Owner** | Bulk actions → Change Owner → Search rep → Confirm |
| **4c. Add to Sequence** | Bulk actions → Add to Sequence → Search → Select → Confirm |
| **4d. Push to SF** | Bulk actions → Push to CRM → Confirm |
| **4e. Add to Campaign** | Bulk actions → Add to Campaign → Search → Select → Confirm |

**Checkpoint after each**: Confirm action completed before proceeding.

### 5. Company Suppression

1. Click "View Companies" button (switches view)
2. Select all companies
3. Bulk actions → Add to List → Select suppression list
4. **Checkpoint**: "X companies added to suppression. Cleanup?"

### 6. Cleanup

1. Navigate back to people list
2. Select all → Remove from List (NOT delete)
3. **Done**: Report summary

## Parameters

Collect at workflow start:

```
source_list:              # Company list to pull from
destination_people_list:  # People list to add contacts to
owner_rep:                # Sales rep name for ownership
sequence_name:            # Email sequence name
sf_campaign:              # Salesforce campaign name
suppression_company_list: # Company suppression list
mode:                     # "interactive" or "autonomous"
```

## Error Handling

If element not found or action fails:

1. Take screenshot immediately
2. Pause and show error to user
3. Ask user to identify correct UI pattern
4. Update [references/apollo-ui-patterns.md](references/apollo-ui-patterns.md)
5. Retry or abort per user input

## References

- **UI Patterns**: [references/apollo-ui-patterns.md](references/apollo-ui-patterns.md) - Element selectors learned during interactive runs
- **Saved Configs**: [references/workflow-configs.md](references/workflow-configs.md) - Parameter presets for different campaigns
- **Implementation Plan**: [references/implementation-plan.md](references/implementation-plan.md) - Full design decisions and rationale
