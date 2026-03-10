# Apollo.io Lead Management Automation Plan

## Problem Statement
Automate a repetitive Apollo.io workflow that involves:
1. Selecting contacts from a company list (3 per company)
2. Adding them to a people list
3. Changing ownership by region
4. Adding to email sequence
5. Pushing to Salesforce
6. Adding to SF Campaign
7. Moving companies to a suppression list
8. Cleaning up the people list

---

## Recommended Solution: Chrome DevTools MCP

**Why this is the best approach:**
1. **Already configured** - MCP server is available in your environment
2. **Uses your session** - No login/2FA automation needed
3. **Interactive** - Can handle edge cases in real-time
4. **Visual verification** - Can take snapshots to confirm state
5. **Step-by-step mode** - Can pause after each action for human verification

---

## Key Design Decisions

### 1. Step-by-Step Execution Mode
The skill will support two modes:

**Interactive Mode (default for first runs):**
- Pause after EVERY action
- Take snapshot and show what was done
- Ask user to confirm before proceeding
- Perfect for learning Apollo's UI patterns and building confidence

**Autonomous Mode (after validation):**
- Run full workflow without pauses
- Still take snapshots at checkpoints
- Alert and pause only on errors or unexpected UI

### 2. UI Change Detection & Adaptation
Built-in safeguards:
- **Snapshot-based verification**: Before each action, verify expected elements exist
- **Fallback selectors**: Multiple ways to find each element (by text, aria-label, class patterns)
- **Alert mechanism**: If expected element not found, pause and:
  1. Take screenshot for human review
  2. Ask user to identify the new UI pattern
  3. Update the knowledge file with new pattern
- **Knowledge file** (`apollo-ui-patterns.md`): Stores UI patterns separately, easy to update without changing skill logic

### 3. Generic/Reusable Skill Design
The skill will be **parameterized** so it works for any sequence:

```
/apollo-lead-processor

Parameters (prompted at runtime):
- source_list: "NEW 2025-09 Growth Squad: Companies Hiring Social Media Positions (DMs)"
- destination_people_list: "NEW 2025-09 Growth Squad: Final People List..."
- sequence_name: "2025-09 Growth Squad: EN Companies Hiring Social Media Roles..."
- sf_campaign: "2025 Growth Squad - Intent Job Hire Campaign (Parent)"
- suppression_company_list: "2025-09 Growth Squad - Companies Hiring Social Media Roles List"
- owner_rep: "John Smith" (or region mapping for future)
- mode: "interactive" | "autonomous"
```

This way you invoke the same skill for different campaigns - just provide different list/sequence names.

### 4. Cron Job / Scheduled Execution
**Options for automated scheduling:**

**Option A: Claude Code + launchd (macOS) - Recommended**
```bash
# Create a wrapper script that:
# 1. Opens Chrome with remote debugging
# 2. Navigates to Apollo
# 3. Invokes Claude Code with the skill
# Schedule via launchd plist
```

**Option B: n8n Workflow**
- Trigger on schedule
- Use HTTP Request node to invoke Claude API
- Chrome DevTools MCP connection managed separately

**Option C: Manual trigger with saved config**
- Keep a `.apollo-config.json` with your parameters
- Run `/apollo-lead-processor` - it reads saved config
- Fastest for "same workflow, different week" scenarios

**Note:** Fully autonomous cron requires Chrome session to be pre-authenticated. Best approach is semi-automated: cron triggers the job, you confirm in Slack/notification, then it runs.

---

## Implementation Plan

### Phase 1: Create Skill Scaffold Using /skill-creator
Use `/skill-creator` to create the initial skill structure with:

**Skill location:** `skills/apollo-lead-processor/`

**Structure:**
```
skills/apollo-lead-processor/
├── skill.md                    # Main skill with workflow logic
├── knowledge/
│   ├── apollo-ui-patterns.md   # UI element patterns (easy to update)
│   └── workflow-config.md      # Default parameters, rep mappings
└── examples/
    └── execution-trace.md      # Example run for reference
```

### Phase 2: Interactive Learning Run (Primary Training Method)
1. Open Chrome with remote debugging: `open -a "Google Chrome" --args --remote-debugging-port=9222`
2. Navigate to Apollo.io, ensure you're logged in
3. Connect via Chrome DevTools MCP
4. Walk through the workflow step-by-step together:
   - I take a snapshot at each step
   - You confirm the action looks correct
   - I execute the action
   - We verify the result
5. Document UI patterns as we discover them into `apollo-ui-patterns.md`
6. After full workflow: review and refine the skill

### Phase 3: Workflow Steps (in skill.md)

1. **Navigate to source list**
   - Take snapshot, verify we're on correct list
   - Checkpoint: "Ready to select contacts?"

2. **Select contacts (3 per company)**
   - Use Apollo's "Select 3 contacts per company" feature
   - Checkpoint: "X contacts selected. Add to destination list?"

3. **Add to destination list**
   - Click "Add to List" → select destination
   - Checkpoint: "Contacts added. Navigate to process them?"

4. **Process people list**
   - Select all contacts
   - Change ownership to specified rep
   - Add to email sequence
   - Push to Salesforce
   - Add to SF Campaign
   - Checkpoint after each action in interactive mode

5. **Handle company suppression**
   - Click "View Companies"
   - Select all, add to suppression list
   - Checkpoint: "Companies added to suppression"

6. **Cleanup**
   - Remove contacts from people list
   - Final snapshot for verification

### Phase 4: Autonomous Mode Validation
After 2-3 successful interactive runs:
- Switch to autonomous mode
- Skill runs without pauses
- Alerts only on errors

---

## Files to Create

| File | Purpose |
|------|---------|
| `skills/apollo-lead-processor/skill.md` | Main skill with parameterized workflow |
| `skills/apollo-lead-processor/knowledge/apollo-ui-patterns.md` | UI selectors and patterns (updatable) |
| `skills/apollo-lead-processor/knowledge/workflow-config.md` | Default params, rep mappings |

---

## How to Share/Train the Process

**Chosen approach: Interactive Learning Run**

We'll run together in step-by-step mode:
1. You open Apollo in Chrome with remote debugging enabled
2. I connect via Chrome DevTools MCP
3. We go through each step together - I take snapshots, you confirm actions
4. I learn the UI patterns as we go and document them
5. After 2-3 successful runs, we switch to autonomous mode

---

## Clarified Requirements

1. **Region mapping**: NA only for now (single rep). Config file will support multi-region later.
2. **Contact selection**: Use Apollo's built-in "3 contacts per company" feature.
3. **Error handling**: Pause and notify user on any failure.
4. **Execution mode**: Start interactive, graduate to autonomous.
5. **Reusability**: Parameterized skill works for multiple sequences/campaigns.
