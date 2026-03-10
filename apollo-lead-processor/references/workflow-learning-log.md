# Apollo Lead Processor - Workflow Learning Log

Detailed step-by-step instructions discovered during interactive learning runs. Use this to update the main workflow and UI patterns files.

---

## Step 1: Navigate to Source Company List

### What works
1. Navigate to `https://app.apollo.io/#/people` (or use source_list_url from config)
2. **Direct URL with `configurableViewId` does NOT reliably load filters** — the page may show 236.5M unfiltered results
3. Instead, must manually select the saved view:
   - Click the view dropdown combobox (`combobox "Select view"`) below "Find people"
   - A dialog opens with a search combobox and list of saved views
   - **Cannot use `fill` on the search combobox** — it tries to select an option instead of typing
   - **Use `evaluate_script` with React native input setter** to type into the search:
     ```javascript
     (el) => {
       const input = el.tagName === 'INPUT' ? el : el.querySelector('input');
       const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
       nativeInputValueSetter.call(input, 'SEARCH_TERM');
       input.dispatchEvent(new Event('input', { bubbles: true }));
       input.dispatchEvent(new Event('change', { bubbles: true }));
       return input.value;
     }
     ```
   - After filtering, click the matching view option
4. **Verify**: View loaded correctly when `Total` count matches expected (e.g., 30) and filters panel shows applied filters

### Key selectors
- View dropdown: `combobox "Select view"`
- Search input inside view dropdown: first `combobox` inside the opened dialog
- Filters region: `region "Filters"` with `radio "Total X"` showing contact count

---

## Step 2: Select 3 Contacts Per Company

### What works
1. Click the **"Bulk select options menu"** button (small dropdown arrow next to "Select all rows" checkbox)
   - Selector: `button "Bulk select options menu"` (marked as disabled in a11y tree but still clickable)
2. A menu opens with 3 options:
   - `menuitem "Select all"` → `button "Select all 30"`
   - `menuitem "Deselect all"` → `button "Deselect all"`
   - `menuitem "Select custom"` → has a right-arrow chevron indicating submenu
3. **Hover** on `menuitem "Select custom"` to expand submenu (not click)
4. Submenu reveals a form `"Select custom records"` with:
   - `spinbutton "Number of people"` (default: 25)
   - `spinbutton "Max no. of people per company"` (default: empty)
   - `button "Select"`
5. **Cannot click/type into spinbuttons directly** — they're marked as disabled in a11y tree
6. **Use `evaluate_script` with React native input setter** to set values:
   - Set "Max no. of people per company" to `3`
   - Set "Number of people" to `30` (or total available)
7. Click `button "Select"` to apply

### Important notes
- The spinbuttons and buttons in the submenu are all marked `disableable disabled` in the a11y tree, but values can be set via JavaScript
- The submenu UIDs change each time it's opened (e.g., `13_2` → `15_2`)
- If user accidentally hovers elsewhere, the submenu collapses — re-hover on "Select custom" to reopen
- After clicking "Select", contacts should be checked in the table with a count shown (e.g., "X rows selected")

### Verification
- Check that `checkbox "Select all rows"` shows "X rows selected" (X should be ≤ total, with max 3 per company)
- Rows in the table should have `checkbox "Select current row" checked`
- `checked="mixed"` on the select-all checkbox confirms partial selection (not all rows)

### Result from first run
- Total contacts: 30, Selected: 26 (max 3 per company applied)
- The `button "Select"` in the submenu must be clicked via `evaluate_script` since it's marked disabled:
  ```javascript
  (el) => { el.click(); return { clicked: true }; }
  ```

---

## Step 3: Add Selected Contacts to Destination People List

### What works
1. After selecting contacts, a **floating action toolbar** appears as a `dialog` element at the bottom of the a11y tree (not inline with the table)
2. Toolbar contains these buttons (left to right):
   - `button "Clear X selected"` — deselects all
   - `button "Save"` — saves contacts
   - Unlabeled buttons (email, phone, export icons)
   - **`combobox "Select lists"`** — the "Add to list" control
   - More unlabeled buttons (sequences, Salesforce, etc.)
   - `button "More Actions"`
3. Click `combobox "Select lists"` to open the list picker dialog
4. A dialog opens with:
   - `combobox "Search..."` — search field (autocomplete, focused by default)
   - Tabs: "All lists", "My lists", "Team lists"
   - `listbox` with `option` elements for each list
   - `button "Create new list"`
   - `button "Add to list"` (disabled until a list is selected)
5. **Use `evaluate_script` with React native input setter** to type search term in the search combobox
6. Click the matching `option` to select it (it becomes `selected`)
7. Click `button "Add to list"` to confirm

### Key selectors
- Floating toolbar: `dialog` at bottom of a11y tree (not near the table headers)
- Lists combobox: `combobox "Select lists"` inside the toolbar dialog
- Search field: `combobox "Search..."` inside the nested dialog
- Add button: `button "Add to list"` inside the nested dialog

### Important notes
- The floating toolbar buttons are mostly **unlabeled** in a11y — identify them by position or use screenshot
- The search combobox supports React native input setter pattern
- After selecting a list, a tooltip appears showing the full list name (useful for verification)
- Success notification appears top-right: "Completed — Finished adding X out of X prospects"

### Result from first run
- Successfully added 26 out of 26 prospects to "NEW 2025-09 Growth Squad: Final People List Companies Hiring Social Media Roles"
- Search term used: "Final People List" (filtered to exactly 1 result)

---

## Step 4a: Select All on People List

### What works
1. Navigate to destination people list URL: `https://app.apollo.io/#/lists/68e53b46980f6b00110bf2d2`
2. **Important**: The page may load with a saved view's filters applied (e.g., "NEW 2025-09 Growth Squad: Comp..."), showing **0 records** even though contacts were just added
3. **Fix**: Click `combobox "Select view"` → select `option "Default view"` to clear all filters
4. After switching to Default view, the page shows the correct record count (e.g., "26 records")
5. Click `checkbox "Select all rows"` — this selects only the visible page (25 rows max per page)
6. If total > 25, click `button "Bulk select options menu"` (marked disabled but clickable) to open the bulk menu
7. Click `button "Select all X"` (e.g., "Select all 26") to select across all pages
8. **Verify**: `button "Clear X selected"` in the floating toolbar shows the correct total count

### Key selectors
- View dropdown: `combobox "Select view"`
- Default view option: `option "Default view"` (first item in the listbox)
- Select all checkbox: `checkbox "Select all rows"`
- Bulk select dropdown: `button "Bulk select options menu"` (marked disabled, still clickable)
- Select all button: `button "Select all X"` inside the opened menu

### Important notes
- **Saved views persist across navigation** — when navigating to a list page, the previously selected saved view and its filters carry over, potentially hiding all contacts
- The page shows 25 rows per page — "Select all rows" checkbox only selects visible rows
- Use "Select all X" from bulk menu to select across pages
- The bulk select menu items are all marked `disableable disabled` but remain interactive

### Result from first run
- 26 records on the list, all 26 selected via "Select all 26" button
- Had to switch from saved view to "Default view" first to see the contacts

---

## Step 4b: Change Ownership to Sales Rep

### What works (partially confirmed)
1. With all contacts selected, click `button "Open more actions"` (three dots `...` at end of floating toolbar, marked disabled but clickable)
2. Menu opens with items: View Companies, **Assign Owner**, Assign Account, Merge duplicates, Create Task, Set stage, Remove from List, Set custom field, Opt out of calls, Delete
3. Click `button "Assign Owner"` → opens "Set owner" dialog
4. Dialog has: `combobox` "New owner:" with searchable textbox, checkbox "Update account owners for those contacts as well.", `button "Set owner"`
5. Click the combobox to open the dropdown → shows full list of reps with a search textbox (uid of textbox inside combobox)
6. `fill` tool works on this textbox (unlike most Apollo inputs) — type rep name to filter
7. Select the matching rep name from the filtered list
8. (Optional) Check "Update account owners for those contacts as well." if needed
9. Click `button "Set owner"` to confirm

### Key selectors
- More actions button: `button "Open more actions"` (last button in floating toolbar, `...` icon)
- Assign Owner menuitem: `menuitem "Assign Owner"` / `button "Assign Owner"` in the menu
- Owner combobox: `combobox` with `haspopup="listbox"` inside the dialog
- Search textbox: `textbox` inside the combobox (focusable, `fill` works here)
- Set owner confirm: `button " Set owner"` (has icon prefix space)

### Important notes
- The `fill` tool works on the owner search textbox (unlike most Apollo React inputs that need the native input setter pattern)
- All "More actions" menu items are marked `disableable disabled` but remain interactive
- The menu also contains **"Remove from List"** (useful for Step 6 cleanup) and **"View Companies"** (useful for Step 5 suppression)
- "Update account owners for those contacts as well." checkbox left unchecked (per user instruction)

### Result from first run
- Owner set to **Lauren Martin** for all 26 contacts
- Notification: "Finished re-assigning owners for 26 contacts"
- After confirmation, the action toolbar remains visible with all 26 still selected — ready for next action

---

## Step 4c: Add to Email Sequence

### What works
1. With all contacts selected, click `button "Sequence"` in the floating action toolbar (paper plane icon)
2. Dropdown opens with: "Add to new Sequence", "Add to existing Sequence", "Mark as Finished in Sequence", "Remove from Sequence"
3. Click `"Add to existing Sequence"` → opens "Add to Sequence" dialog
4. Dialog has:
   - `combobox` for sequence search (with textbox)
   - **Tabs: "My" and "Team"** — default is "My" (only shows your sequences)
   - `switch` "Rotate mailboxes"
   - `combobox` "Send Emails From:" (with textbox for email search)
   - `checkbox` "Skip Contacts Validation"
   - `button "Add X contacts"` (disabled until email selected)
   - `button "Cancel"`, `button "Schedule"`
5. **Click "Team" tab** to see all team sequences (not just your own)
6. Type sequence name in the search textbox using `fill` — `fill` works here
7. Click the matching sequence option to select it
8. Click the "Send Emails From:" combobox to open email dropdown
9. Type rep name (e.g., "lauren") in the email textbox using `fill` — `fill` works here
10. Select the `@meetagorapulse.com` email variant (always use meetagorapulse domain)
11. Leave "Skip Contacts Validation" unchecked (contacts will be verified before adding)
12. Click `button "Add X contacts"` to confirm

### Key selectors
- Sequence button: `button "Sequence"` in floating toolbar (paper plane icon)
- Add to existing: `"Add to existing Sequence"` in the dropdown menu
- Sequence search: `combobox` with `textbox` inside the dialog
- Team tab: click "Team" text/tab (switches from "My" to show all team sequences)
- Email combobox: second `combobox` in dialog (labeled "Send Emails From:")
- Email search textbox: `textbox` inside the email combobox
- Add button: `button "Add X contacts"` (disabled until email selected)

### Important notes
- **"My" vs "Team" tabs**: Default is "My" — sequences owned by other team members won't appear. Must click "Team" to find them
- **`fill` works on both search fields** (sequence search and email search) — no need for React native input setter
- **Always select `@meetagorapulse.com` email domain** for the sending email
- "Add X contacts" button stays disabled until a sending email is selected
- Button shows "Loading..." while processing, then dialog closes automatically
- Success notification: "Finished adding X out of X contacts to sequence"

### Result from first run
- Sequence: "2025-09 Growth Squad: EN Companies Hiring Social Media Roles Email Sequence" (found under Team tab)
- Email: lauren.martin@meetagorapulse.com
- Result: "Finished adding 26 out of 26 contacts to sequence"

---

## Step 4d: Push to Salesforce

### What works
1. With all contacts selected, click `button "Salesforce"` in the floating action toolbar (cloud icon)
   - **Regular `click` tool may not work** — use `evaluate_script` with `el.click()` to reliably open the dropdown
2. Dropdown opens with: "Push to Salesforce", "Add to Salesforce Campaign"
3. Menu items are `<a>` tags (links), not buttons — use `evaluate_script` to click them
4. Click "Push to Salesforce" → **executes immediately with NO confirmation dialog**
5. Success notification: "Synced to Salesforce" or similar CRM sync notification

### Key selectors
- Salesforce button: `button "Salesforce"` in floating toolbar (cloud icon, `expandable haspopup="menu"`)
- Push to SF: `menuitem "Push to Salesforce"` containing an `<a>` tag
- Add to Campaign: `menuitem "Add to Salesforce Campaign"` containing an `<a>` tag

### Important notes
- **NO confirmation dialog** — Push to Salesforce executes immediately upon click
- **ALWAYS pause for user confirmation** before clicking Push to Salesforce (critical/irreversible action)
- Regular `click` tool sometimes doesn't open the Salesforce dropdown — use `evaluate_script` with `el.click()`
- Menu items contain `<a>` tags, not buttons — need `evaluate_script` to click reliably
- UIDs change each time the dropdown is reopened — always take fresh snapshot

### Result from first run
- 26 contacts pushed to Salesforce
- Notification confirmed sync

---

## Step 4e: Add to SF Campaign

### What works
1. With all contacts selected, click `button "Salesforce"` → use `evaluate_script` with `el.click()`
2. Click `"Add to Salesforce Campaign"` from the dropdown (also an `<a>` tag)
3. Dialog opens with:
   - `searchbox "Search Salesforce Campaign and press Enter"` — search field
   - `button "Cancel"`, `button "Save"`
4. **Must search using exact full campaign name** — partial terms like "Growth Squad", "Intent", "Job Hire" return "No Salesforce Campaign found"
5. Type the full campaign name and press **Enter** to search
6. Campaign result appears as `StaticText` — click it to select
7. Selected campaign name fills the searchbox
8. Click `button "Save"` to confirm

### Key selectors
- Salesforce button: same as Step 4d
- Add to Campaign menuitem: `menuitem "Add to Salesforce Campaign"` with `<a>` tag
- Search field: `searchbox "Search Salesforce Campaign and press Enter"`
- Save button: `button "Save"`
- Cancel button: `button "Cancel"`

### Important notes
- **Search requires exact full campaign name** — partial matches don't work (unlike other Apollo search fields)
- Must press **Enter** after typing to trigger the search
- `fill` works on the searchbox (no need for React native input setter)
- Campaign appears as `StaticText` in results — click it to select, then it fills the searchbox
- Success notification: "Finished adding X out of X prospects"

### Result from first run
- Campaign: "2025 Growth Squad - Intent Job Hire Campaign (Parent)"
- Result: "Finished adding 26 out of 26 prospects"

---

## Step 5: Company Suppression

### What works
1. From the destination people list (Step 4a), with all contacts selected, click `button "Open more actions"` (three dots `...`) via `evaluate_script`
2. Click `button "View Companies"` via `evaluate_script` (it's an `<a>` tag — regular `click` doesn't work)
3. Page navigates to **"Find companies"** filtered view with `qSearchListId` parameter — shows only companies associated with selected contacts
4. Click `checkbox "Select all rows"` to select all companies (if all fit on one page, no bulk select needed)
5. Click `combobox "Select lists"` in the floating toolbar to open the list picker
6. Use **React native input setter** to type search term in `combobox "Search..."` (e.g., "Companies Hiring Social Media")
7. Click the matching `option` to select it (tooltip confirms full name)
8. Click `button "Add to list"` via `evaluate_script` (marked disabled but clickable)
9. Page re-renders with selections cleared — confirms success

### Key selectors
- More actions button: `button "Open more actions"` in floating toolbar
- View Companies: `button "View Companies"` / `menuitem "View Companies"` (contains `<a>` tag)
- Select all: `checkbox "Select all rows"` on the company page
- Lists combobox: `combobox "Select lists"` in floating toolbar
- Search: `combobox "Search..."` in the list picker dialog
- Add button: `button "Add to list"` in the list picker dialog

### Important notes
- **"View Companies" is an `<a>` tag** — must use `evaluate_script` with `el.click()`, regular `click` tool doesn't navigate
- **Selection is lost on navigation** — if you navigate away from the people list and come back, you must re-select all contacts before using View Companies
- After clicking "Add to list", the page re-renders (UIDs change, selections cleared) — this confirms the action succeeded
- The notification may appear briefly and disappear before it can be caught with `wait_for`
- Search in the list picker works with **React native input setter** pattern (partial match works here, unlike SF Campaign search)

### Result from first run
- 21 companies shown on filtered "Find companies" page (from 26 contacts across 21 companies)
- All 21 selected and added to "2025-09 Growth Squad - Companies Hiring Social Media Roles List" (457 → 478 companies)
- Page re-rendered with selections cleared, confirming success

---

## Step 6: Cleanup — Remove Contacts from People List

### What works
1. Navigate to destination people list URL: `https://app.apollo.io/#/lists/68e53b46980f6b00110bf2d2`
2. **Saved view may be applied** — if it shows the correct contact count, proceed; otherwise switch to "Default view"
3. Click `checkbox "Select all rows"` — selects only visible page (25 max)
4. Open `button "Bulk select options menu"` via `evaluate_script` → click `button "Select all X"` via `evaluate_script`
5. Open `button "Open more actions"` (three dots `...`) via `evaluate_script`
6. Click `button "Remove from List"` via `evaluate_script`
7. **Confirmation dialog appears**: "Are you sure you want to remove these contacts from [list name]?"
8. Click `button "Remove from list"` to confirm (regular `click` works here)
9. Success notification: "Completed — Successfully removed contacts from list. It may take 1-2 minutes for the list to get fully updated."

### Key selectors
- Select all: `checkbox "Select all rows"`
- Bulk select: `button "Bulk select options menu"` (marked disabled, clickable via evaluate_script)
- Select all X: `button "Select all X"` inside the bulk menu
- More actions: `button "Open more actions"` in floating toolbar
- Remove from List: `button "Remove from List"` / `menuitem "Remove from List"` in more actions menu
- Confirm dialog: `dialog "Remove from list?"` with `button "Remove from list"` and `button "Cancel"`

### Important notes
- **Has a confirmation dialog** — unlike Push to Salesforce, this action asks "Are you sure?"
- Regular `click` works on the confirmation dialog buttons
- After removal, page refreshes and shows remaining contacts (from other batches or not matching saved view filters)
- Notification confirms: "Successfully removed contacts from list. It may take 1-2 minutes for the list to get fully updated."

### Result from first run
- 26 contacts removed from "NEW 2025-09 Growth Squad: Final People List Companies Hiring Social Media Roles"
- Notification: "Completed — Successfully removed contacts from list."
- List shows 10 remaining records (from previous batches, not matching current saved view filters)

---

## General Patterns Learned

### React Input Setter Pattern
Apollo uses React, so standard `fill` and direct value assignment don't trigger React's state updates. Use:
```javascript
const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
nativeInputValueSetter.call(inputElement, 'value');
inputElement.dispatchEvent(new Event('input', { bubbles: true }));
inputElement.dispatchEvent(new Event('change', { bubbles: true }));
```

### Disabled Elements
Many Apollo UI elements are marked `disableable disabled` in the a11y tree but are still interactive. Try clicking/hovering them before assuming they're truly disabled.

### Snapshot Size
Apollo page snapshots can be 1500+ lines. Save to file and parse with grep/sed instead of reading inline.

### UID Instability
UIDs change when menus are reopened or page re-renders. Always take a fresh snapshot before interacting.

---

## Last Updated
- **Date**: 2026-02-10
- **Steps Completed**: All steps (1-6) — Full workflow confirmed working
