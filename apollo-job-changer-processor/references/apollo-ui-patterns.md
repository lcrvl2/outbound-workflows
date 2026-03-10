# Apollo UI Patterns — Job Changer Workflow

Job-changer-specific selectors. For shared bulk action patterns (Push to SF, Add to Campaign, Remove from List), see `../apollo-lead-processor/references/apollo-ui-patterns.md`.

## Status: LEARNED (EN list run, 2026-02-09)

---

## "Update Available" Badge
**Primary**: `button "Accept update"` — opens the Update Contact popup
**Siblings**: `button "Update available"` (info badge), `button "Dismiss update"` (skip)
**Notes**: 3 inline buttons appear next to each contact with a job change. Only "Accept update" triggers the popup. Badge removal is async after processing.

## Update Contact Pop-up
**Primary**: `document` child of RootWebArea containing `StaticText "Update Contact"`
**Notes**: Modal dialog. Header shows contact name + new company heading. Default radio is "Update existing contact". Shows "Email enrichment" banner with credit usage (1-4/record). "Find data via Waterfall" switch is ON by default.

## Pop-up Elements (in order of interaction)

### 1. "Create New Contact" Option
**Primary**: `radio "Create new contact"`
**Notes**: Radio button. Default selection is `radio "Update existing contact"` — must switch. Selecting "Create new contact" reveals the stage dropdown and "Show More Settings" link.

### 2. Outdated Contact Stage Dropdown
**Primary**: `combobox` → `textbox` child (appears after selecting "Create new contact")
**Options**: New, MQL, Working, Qualified, Nurturing, Unqualified, Nurture - Close, Unqualified - Spam, Unqualified - Bounced, Unqualified - Unsubscribed
**Notes**: Click combobox to open dropdown, click option StaticText to select. Always select "New" for job changers.

### 3. "Show More Settings" Link
**Primary**: `StaticText "Show More Settings"`
**Notes**: Clickable StaticText (not a button in a11y tree). Toggles to "Hide More Settings" when expanded. Must be clicked to reveal Add to Lists and Mark sequences finished options.

### 4. Expanded Settings (visible after "Show More Settings")

#### Set Owner
**Primary**: `radio "Keep existing one"` (default, checked) / `radio "Add new one"`
**Notes**: No action needed — keep default.

#### Add to Sequence
**Primary**: `combobox` after "Add to Sequence:" label → `textbox` child
**Notes**: Optional. Not used in standard job changer flow.

#### Add to Lists
**Primary**: `combobox` after "Add to Lists:" label → `textbox` child
**Search**: Type list name to filter. Dropdown shows tabs (All/My/Team) + "Create new list" option + matching results.
**Target**: "2026-02 Job changers intent - Global (ENRICHED)" — click matching result to select.

#### "Mark Current Sequences as Finished"
**Primary**: `StaticText "Mark current sequences as finished"` (clickable)
**Underlying**: `input[type="checkbox"]` — NOT exposed in a11y tree
**Verification**: Use `evaluate_script` to check `.checked` state on nearest `input[type="checkbox"]`
**Notes**: Click the StaticText to toggle. Default state appears to be unchecked. Always enable for job changers.

### 5. "Yes, Update" Button
**Primary**: `button "Yes, Update"`
**Notes**: Final confirmation. Closes popup on success. Sibling: `button "Cancel"`.

## Email Status Filter
**Primary**: `StaticText "Verified"` under "Email Status" section in Filters sidebar
**Expand filter**: Click `button "Show Filters"` to open filter sidebar, then expand "Email Status" section
**Categories**:
- Safe to send: Verified
- Send with caution: Unverified, User managed
- Do not send: Update required, Unavailable
**Toggle**: "Include catch-all emails" — `switch checked` (ON by default)
**URL param**: `contactEmailStatusV2[]=verified`
**Notes**: Active filter count shown as badge on "Email Status" label. Always filter for "Verified" before pushing to SF.

## Select All / Bulk Action Toolbar
**Select-all**: `checkbox "N rows selected"` in header `columnheader` — toggles all visible rows
**Toolbar**: `dialog` element at bottom of page, appears when contacts are selected
**Buttons**: Clear selection (`button "Clear N selected"`), Save, Email, Sequence, Call, Add to list (`combobox "Select lists"`), Export, Enrich, Research with AI, Salesforce, Open more actions
**Notes**: Selection state is preserved across Salesforce push and campaign assignment operations.

## Push to Salesforce
**Access**: `button "Salesforce"` (expandable, haspopup="menu") in bulk toolbar
**Dropdown**: `menuitem "Push to Salesforce"` and `menuitem "Add to Salesforce Campaign"`
**Push behavior**: Async — shows "Pushing to CRM" / "We are trying to push to your CRM." toast. No explicit success text in a11y tree — toast simply disappears on completion. Also triggers data refresh in the grid.
**Notes**: Detect completion by taking a snapshot and confirming toast absence.

## Add to Salesforce Campaign
**Access**: `menuitem "Add to Salesforce Campaign"` from Salesforce dropdown
**Modal**: Opens a **multi-section bulk action modal** (not just a dropdown). Sections: Add to Lists, Add to Sequence, Add to Salesforce Campaign, Assign Owner, Mobile Numbers, Export as CSV.
**Campaign search**: `searchbox "Search Salesforce Campaign and press Enter"` → type campaign name → **press Enter to trigger search** → results appear in nested `dialog` dropdown → click campaign `StaticText` to select
**Confirm**: `button "Save"` at bottom of modal → changes to "Loading..." (disabled) while processing → modal closes automatically on completion
**Notes**: Only the SF Campaign section needs to be filled. Other sections can be left empty.

## Remove from List (Bulk)
**Access**: `button "Open more actions"` in bulk toolbar → `menuitem "Remove from List"` (with nested `button`)
**Confirmation**: `dialog "Remove from list?"` — text adapts: "this contact" (singular) / "these contacts" (plural)
**Buttons**: `button "Cancel"` / `button "Remove from list"`
**Success**: Toast: "Successfully removed N contact(s) from [list name]". List refreshes to show updated count or empty state.

---

**Last Updated**: 2026-02-09 — Full learning run (Phase 1: EN 3/3, FR 0/2, DACH 0/0 | Phase 2: 14 enriched contacts processed | Phase 3: EN 1 removed, FR 2 removed, DACH 0 empty)
