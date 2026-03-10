# Execution Log — Interactive Learning Run #1

**Date**: 2026-02-09
**Mode**: Interactive
**Purpose**: Learn UI patterns, document selectors, validate workflow steps

---

## Phase 1: Enrich Job Changers

### EN List

**URL**: https://app.apollo.io/#/lists/68a3d3b1d927eb000d5975c8
**List name**: "2025-09 Growth Squad - Job Changers - Current Users OLD Job"
**Total records**: 3

#### Step 1.1 — Navigate to EN list
- **Action**: Opened new tab via Chrome DevTools MCP, navigated to list URL
- **Result**: Page loaded showing 3 records
- **UI Notes**: List title in `heading[level=1]`. Record count shown as StaticText "3 records" below heading.

#### Step 1.2 — Identify "update available" contacts
- **Action**: Took a11y snapshot to identify contacts with job changes
- **Result**: 3 contacts found with "Update available" badges:
  1. Chelsea Brooks — Cosmetologist at outdoor network
  2. Sarah Bierschwale — Web and Digital Specialist at University of Maine at Farmington
  3. Mel Smith — Marketing Specialist at Brock University
- **UI Notes**: Each contact with an update shows 3 buttons inline: `button "Update available"` (info badge), `button "Accept update"` (action trigger), `button "Dismiss update"`. The "Accept update" button opens the Update Contact popup.

#### Step 1.3 — Process first contact: Chelsea Brooks
- **a. Click "Accept update"**: Clicked `button "Accept update"` next to Chelsea Brooks. Popup opened showing: "Mel Smith" → heading with new company name. Default is "Update existing contact" (radio, checked).
- **b. Create new contact**: Clicked `radio "Create new contact"`. This revealed the stage dropdown and "Show More Settings" link.
- **c. Set stage to "New"**: Clicked `combobox` (stage dropdown) to open it. Options appeared as StaticText elements: New, MQL, Working, Qualified, Nurturing, Unqualified, Nurture - Close, Unqualified - Spam, Unqualified - Bounced, Unqualified - Unsubscribed. Clicked "New".
- **d. Click "Show More Settings"**: Clicked StaticText "Show More Settings". Expanded to reveal: Set Owner (radio: Keep existing one / Add new one), Add to Sequence (combobox), Add to Lists (combobox), Mark current sequences as finished (checkbox).
- **e. Add to enriched list**: Clicked "Add to Lists" combobox textbox, typed "Job changers intent". Dropdown showed options including "2026-02 Job changers intent - Global (ENRICHED)". Selected it.
- **f. Mark sequences finished**: Clicked `StaticText "Mark current sequences as finished"`. Verified via `evaluate_script` that the underlying checkbox `checked=true`.
- **g. Click "Yes, Update"**: Clicked `button "Yes, Update"`. Popup closed, returned to list view.
- **UI Notes**: Chelsea Brooks' "Update available" badge disappeared after processing.

#### Step 1.4 — Process contact #2: Sarah Bierschwale
- **Job change**: University of Maine at Farmington → Xanterra Travel Collection (Web and Digital Specialist)
- **Flow**: Accept update → Create new contact → Stage "New" → Show More Settings → Add to "2026-02 Job changers intent - Global (ENRICHED)" → Mark sequences finished (verified checked=true) → Yes, Update
- **Result**: Popup closed successfully. Badge removal async.

#### Step 1.5 — Process contact #3: Mel Smith
- **Job change**: Brock University → Goodman School of Business at Brock University (Owner)
- **Flow**: Accept update → Create new contact → Stage "New" → Show More Settings → Add to "2026-02 Job changers intent - Global (ENRICHED)" → Mark sequences finished (verified checked=true) → Yes, Update
- **Result**: Popup closed successfully. Badge removal async.

**EN List Summary**: 3/3 contacts processed successfully.

---

### FR List

**URL**: https://app.apollo.io/#/lists/68f9fd6aa4287600018c367d
**List name**: "2025-09 Growth Squad - FR Job Changers - Current Users OLD Job list."
**Total records**: 2

#### Step 1.1 — Navigate to FR list
- **Action**: Navigated to FR list URL via Chrome DevTools MCP
- **Result**: Page loaded showing 2 records: Simon Raulin (Chargé de Communication, les chuchoteuses) and François Benoiton (Chef de Projet Affaires Institutionnelles Et Sport, REALITES)

#### Step 1.2 — Identify "update available" contacts
- **Action**: Took a11y snapshot to scan for "Update available" / "Accept update" buttons
- **Result**: **0 contacts with job changes**. Neither contact has an "Update available" badge.
- **UI Notes**: Standard list view with no update badges. Both contacts show normal action buttons (phone-icon, lists-button, Manage sequences, Salesforce actions, More-button).

**FR List Summary**: 0/2 contacts had job changes — nothing to process.

---

### DACH List

**URL**: https://app.apollo.io/#/lists/68f80e37de28c80011bb2d51
**List name**: "2025-09 Growth Squad - DACH Job Changers - Current Users OLD Job list"
**Total records**: 0

#### Step 1.1 — Navigate to DACH list
- **Action**: Navigated to DACH list URL via Chrome DevTools MCP
- **Result**: Page loaded showing "No records" empty state. Message: "No saved people yet! Add people to this list to get started."

**DACH List Summary**: Empty list — 0 records, nothing to process.

---

## Phase 2: Process Enriched List

**URL**: https://app.apollo.io/#/lists/698217a1703af3002135f177

#### Step 2.0 — Navigate to enriched list
- **Action**: Navigated to enriched list URL via Chrome DevTools MCP
- **Result**: Page loaded showing 53 total records. List name: "2026-02 Job changers intent - Global (ENRICHED)"
- **UI Notes**: Standard list view with filter sidebar on the left.

#### Step 2.0b — Process individual update (Arjun Shah)
- **Action**: Arjun Shah had an "Update available" badge (The Influencer Marketing Factory → Tailify, Head of Paid Social). Processed via same Phase 1 flow: Accept update → Create new contact → Stage "New" → Show More Settings → Add to enriched list → Mark sequences finished → Yes, Update.
- **Result**: Update processed successfully. New contact created at Tailify.
- **UI Notes**: Same UI patterns as Phase 1. Individual updates can appear in the enriched list too.

#### Step 2.1 — Filter for verified emails
- **Action**: Expanded "Email Status" filter in left sidebar. Clicked `StaticText "Verified"` under "Safe to send" category.
- **Result**: List filtered from 53 to **14 records** with verified emails.
- **UI Notes**: Email Status filter panel shows categories: "Safe to send" (Verified), "Send with caution" (Unverified, User managed), "Do not send" (Update required, Unavailable). Also has "Include catch-all emails" toggle (switch, checked by default). Filter applied via URL param: `contactEmailStatusV2[]=verified`. Active filter count shown as badge on "Email Status" label: `button " 1"`.

#### Step 2.2 — Select all contacts
- **Action**: Clicked header checkbox `checkbox "14 rows selected"` to select all 14 contacts. Bulk action toolbar (`dialog`) appeared at bottom of page.
- **Result**: All 14 contacts selected. Bulk toolbar shows: Clear selection, Save, Email, Sequence, Call, Add to list, Export, Enrich, Research with AI, Salesforce, Open more actions.
- **UI Notes**: Header checkbox toggles select-all. Bulk toolbar is a `dialog` element that appears when contacts are selected. It shows "Clear 14 selected" button + action buttons. The "Salesforce" button has `haspopup="menu"` — it's a dropdown with sub-actions.

#### Step 2.3 — Push to Salesforce
- **Action**: Clicked `button "Salesforce"` (expandable, haspopup="menu") in bulk toolbar. Dropdown opened with two options: `StaticText "Push to Salesforce"` and `StaticText "Add to Salesforce Campaign"`. Clicked "Push to Salesforce".
- **Result**: Toast notification appeared: "Pushing to CRM" / "We are trying to push to your CRM." Toast disappeared after ~10s indicating async completion. No explicit "success" text — completion is detected by toast disappearance. Data refreshed after push (e.g., Sarah Bierschwale's company updated from "University of Maine at Farmington" to "Kind Outside Marketing").
- **UI Notes**: Salesforce dropdown: `button "Salesforce"` → opens `menu` with `menuitem "Push to Salesforce"` and `menuitem "Add to Salesforce Campaign"`. Push is async — shows toast, then toast vanishes on completion. Selection (14 checked contacts) is preserved after push. Push also triggers data refresh in the grid.

#### Step 2.4 — Add to SF Campaign
- **Campaign**: "2025 Growth Squad - Intent Job Changers Campaign (Parent)"
- **Action**: Re-opened Salesforce dropdown. Clicked "Add to Salesforce Campaign". A bulk action modal opened (not just a dropdown) with sections: Add to Lists, Add to Sequence, Add to Salesforce Campaign, Assign Owner, Mobile Numbers, Export as CSV. Found `searchbox "Search Salesforce Campaign and press Enter"`. Typed campaign name, pressed Enter. Dropdown appeared with matching result. Clicked campaign name to select. Clicked `button "Save"`.
- **Result**: Save button changed to "Loading..." (disabled). Modal closed on completion. 14 contacts added to SF campaign.
- **UI Notes**: "Add to Salesforce Campaign" opens a **multi-section bulk action modal** (not just a dropdown). The SF campaign search uses a `searchbox` with placeholder "Search Salesforce Campaign and press Enter". Must press Enter to trigger search. Results appear in a `dialog` dropdown below the searchbox. Click the campaign `StaticText` to select. Confirmation via `button "Save"` at bottom. Save button shows "Loading..." while processing, then modal closes.

#### Step 2.5 — Cleanup (remove from list)
- **Action**: With 14 contacts still selected, clicked `button "Open more actions"` in bulk toolbar. Dropdown menu appeared with options: View Companies, Assign Owner, Assign Account, Merge duplicates, Create Task, Set stage, **Remove from List**, Set custom field, Opt out of calls, Delete. Clicked `button "Remove from List"`. Confirmation dialog appeared: "Remove from list?" / "Are you sure you want to remove these contacts from 2026-02 Job changers intent - Global (ENRICHED)?". Clicked `button "Remove from list"`.
- **Result**: All 14 contacts removed. List now shows "0 records" and "No people match your criteria" empty state.
- **UI Notes**: "Open more actions" button (uid varies) opens a `menu` with `menuitem` elements. "Remove from List" is a `menuitem` with nested `button`. Triggers a confirmation `dialog "Remove from list?"` with Cancel and "Remove from list" buttons. After removal, list refreshes to show empty state (with filter still active).

---

## Learned UI Patterns Summary

| Element | Selector / Pattern | Notes |
|---------|-------------------|-------|
| "Update available" badge | `button "Update available"` + `button "Accept update"` + `button "Dismiss update"` | 3 inline buttons per contact row. "Accept update" opens popup. |
| Update Contact pop-up | `document` inside RootWebArea with StaticText "Update Contact" | Modal dialog. Shows contact name, new company/title. |
| "Create new contact" | `radio "Create new contact"` | Default is "Update existing contact". Must switch to create new. Reveals stage dropdown + "Show More Settings". |
| Stage dropdown | `combobox` with `textbox` child | Options: New, MQL, Working, Qualified, Nurturing, Unqualified, + 3 more. Click combobox to open, click option StaticText to select. |
| "Show more settings" | `StaticText "Show More Settings"` | Toggles to "Hide More Settings" when expanded. Not a button in a11y tree — just StaticText that's clickable. |
| Add to list (in pop-up) | `combobox` after "Add to Lists:" label, `textbox` child | Type to search. Dropdown shows tabs (All/My/Team) + "Create new list" + matching lists. Click list name to select. |
| "Mark sequences finished" | `StaticText "Mark current sequences as finished"` | Underlying element is checkbox (`input[type="checkbox"]`). Not visible in a11y tree as checkbox — appears as StaticText. Verify state via `evaluate_script`. |
| "Yes, update" button | `button "Yes, Update"` | Final confirmation. Closes popup on success. |
| Email Status filter | `StaticText "Verified"` under "Email Status" in Filters region | Categories: Safe to send (Verified), Send with caution (Unverified, User managed), Do not send (Update required, Unavailable). Has "Include catch-all emails" `switch checked`. URL param: `contactEmailStatusV2[]=verified`. |
| Select-all checkbox | `checkbox "N rows selected"` in header `columnheader` | Toggles all visible rows. Shows count in label. |
| Bulk action toolbar | `dialog` at bottom of page | Appears when contacts selected. Contains: Clear selection, Save, Email, Sequence, Call, Add to list, Export, Enrich, Research with AI, Salesforce, Open more actions. |
| Salesforce dropdown | `button "Salesforce"` expandable haspopup="menu" | Opens menu with "Push to Salesforce" and "Add to Salesforce Campaign". |
| Push to Salesforce | `menuitem "Push to Salesforce"` | Async. Shows "Pushing to CRM" toast. No success message — toast disappears on completion. Triggers data refresh. Selection preserved. |
| Add to SF Campaign | `menuitem "Add to Salesforce Campaign"` → opens multi-section modal | Modal has: Add to Lists, Add to Sequence, Add to Salesforce Campaign, Assign Owner, Mobile Numbers, Export as CSV. Campaign search via `searchbox` + Enter. Select from dropdown. Confirm with `button "Save"`. |
| Remove from List | `button "Open more actions"` → `menuitem "Remove from List"` | Confirmation dialog: "Remove from list?" with Cancel / "Remove from list" buttons. |

---

## Phase 3: Clean Individual Lists

### EN List Cleanup

**URL**: https://app.apollo.io/#/lists/68a3d3b1d927eb000d5975c8
**List name**: "2025-09 Growth Squad - Job Changers - Current Users OLD Job"
**Records before cleanup**: 1 (Mel Smith)

#### Step 3.1 — Navigate to EN list
- **Action**: Navigated to EN list URL via Chrome DevTools MCP
- **Result**: Page loaded showing **1 record** — only Mel Smith remained.
- **UI Notes**: Chelsea Brooks and Sarah Bierschwale were automatically removed from the source list when "Create new contact" was selected during Phase 1 processing. Only Mel Smith's OLD record persisted.

#### Step 3.2 — Select and remove remaining contact
- **Action**: Clicked `checkbox "Select current row"` next to Mel Smith. Bulk action toolbar appeared. Clicked `button "Open more actions"` → `menuitem "Remove from List"`. Confirmation dialog: "Are you sure you want to remove this contact from 2025-09 Growth Squad - Job Changers - Current Users OLD Job?". Clicked `button "Remove from list"`.
- **Result**: Success toast: "Successfully removed 1 contact from 2025-09 Growth Squad - Job Changers - Current Users OLD Job". List now shows "0 records" and empty state.
- **UI Notes**: Same removal flow as Phase 2.5. Confirmation dialog text uses "this contact" (singular) vs "these contacts" (plural) depending on selection count. Success toast includes the list name.

**EN List Cleanup Summary**: 1/1 remaining contact removed.

---

### FR List Cleanup

**URL**: https://app.apollo.io/#/lists/68f9fd6aa4287600018c367d
**List name**: "2025-09 Growth Squad - FR Job Changers - Current Users OLD Job list."
**Records before cleanup**: 2 (Simon Raulin, François Benoiton)

#### Step 3.3 — Navigate to FR list
- **Action**: Navigated to FR list URL via Chrome DevTools MCP
- **Result**: Page loaded showing **2 records** — Simon Raulin (Chargé de Communication) and François Benoiton (Chef de Projet Affaires Institutionnelles Et Sport).

#### Step 3.4 — Select all and remove
- **Action**: Clicked `checkbox "Select all rows"` (header checkbox) to select all 2 contacts. Bulk action toolbar appeared. Clicked `button "Open more actions"` → `menuitem "Remove from List"`. Confirmation dialog: "Are you sure you want to remove these contacts from 2025-09 Growth Squad - FR Job Changers - Current Users OLD Job list.?". Clicked `button "Remove from list"`.
- **Result**: Success toast: "Successfully removed 2 contacts from 2025-09 Growth Squad - FR Job Changers - Current Users OLD Job list." List now shows "0 records" (note: header may show stale count until page refresh).
- **UI Notes**: Same removal flow as EN list and Phase 2. Even though no job changes were processed from this list, contacts should be cleaned to reset the list for the next cycle.

**FR List Cleanup Summary**: 2/2 contacts removed.

---

### DACH List Cleanup

**URL**: https://app.apollo.io/#/lists/68f80e37de28c80011bb2d51
**List name**: "2025-09 Growth Squad - DACH Job Changers - Current Users OLD Job list"
**Records**: 0

#### Step 3.5 — Navigate and verify
- **Action**: Navigated to DACH list URL via Chrome DevTools MCP
- **Result**: Page loaded showing **0 records** — empty state: "No saved people yet! Add people to this list to get started."
- **Action**: No cleanup needed — list was already empty.

**DACH List Cleanup Summary**: 0 records — nothing to clean.

---

## Issues & Observations

- "Mark current sequences as finished" checkbox is NOT exposed as a checkbox in the a11y tree — only as StaticText. Must use `evaluate_script` to verify checked state.
- "Show More Settings" is StaticText, not a button element — but clickable via Chrome DevTools MCP click.
- Badge removal after processing is async — contact may still show "Update available" immediately after popup closes, but it clears on subsequent page loads/snapshots.
- The popup header shows the NEW company name (destination), not the old one.
- "Set Owner" defaults to "Keep existing one" (radio checked) — no action needed.
- "Find data via Waterfall" switch is checked by default — enriches email via waterfall data sources. Credit usage: 1-4 per enriched record.
- Each contact popup is processed individually (no bulk processing for job changer updates).
- **Phase 2**: Push to Salesforce has no explicit success message in a11y tree — the "Pushing to CRM" toast simply disappears. Detect completion by toast absence.
- **Phase 2**: Push to Salesforce refreshes contact data in the grid (e.g., company names update).
- **Phase 2**: Contact selection (checkboxes) is preserved across Salesforce push and campaign assignment operations.
- **Phase 2**: "Add to Salesforce Campaign" opens a **multi-section modal** (not just the campaign picker). It bundles: Add to Lists, Add to Sequence, Add to SF Campaign, Assign Owner, Mobile Numbers, Export as CSV. Only the SF Campaign section needs to be filled — others can be left empty.
- **Phase 2**: SF Campaign search requires pressing Enter after typing. Results appear in a nested `dialog` dropdown.
- **Phase 2**: The "Save" button in the multi-section modal changes to "Loading..." (disabled) while processing, then the modal closes automatically.
- **Phase 2**: "Remove from List" is under "Open more actions" menu, not a top-level button. Has a confirmation dialog before removal.
- **Phase 3**: "Create new contact" in Phase 1 automatically removes the OLD contact from the source list for some contacts, but not all. Chelsea Brooks and Sarah Bierschwale were auto-removed; Mel Smith was not. This means source list cleanup is still required after Phase 1 to ensure all OLD records are removed.
- **Phase 3**: Confirmation dialog text adapts to selection count: "this contact" (singular) vs "these contacts" (plural).
- **Phase 3**: Success toast after removal includes the full list name, confirming which list the contact was removed from.
- **Phase 3**: FR list contacts were removed even though no job changes were detected — this is the correct behavior to reset lists for the next monthly cycle.
- **Phase 3**: After bulk removal, the header record count ("2 records") may show a stale value until the page is refreshed or navigated away. The success toast is the reliable confirmation.
- **Chrome DevTools MCP**: `wait_for` can time out if the expected text doesn't appear within the timeout window. Workaround: take a snapshot instead to verify the page state.
- **Chrome DevTools MCP**: If the MCP connection drops ("The browser is already running" error), fix by running `pkill -f "chrome-devtools-mcp/chrome-profile"` to kill stale Chrome processes. The MCP server will restart with a fresh browser on the next tool call.
