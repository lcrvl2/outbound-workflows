---
name: targeting-ideas
description: Generate B2B campaign targeting ideas from a GTM playbook. Triggered ONLY by the explicit command "[targeting-ideas]". Outputs a numbered table of 20 targeting ideas with company criteria, personas, and signal tags. User must provide a playbook in the conversation before or with the command.
---

# Targeting Ideas Generator

Generate 20 B2B campaign targeting ideas from a GTM playbook and display as a numbered table.

## Workflow

### 1. Parse the Playbook

Extract from the provided playbook:
- **Product**: What it does, value prop, differentiators
- **Verticals**: Industries, company sizes, geographies
- **Personas**: Job titles, pain points, goals
- **Proof**: Case studies, customer examples

**Geography**: Find geographic mentions. Default to "United States" if not found.

### 2. Generate 20 Ideas

Each idea needs:
- **Title**: `{geo}-based {company description} ({headcount}) {signal}, targeting: {titles}`
- **Company Targeting**: Geo + industry + size + signal (no trailing punctuation)
- **Persona Targeting**: Job titles, comma-separated
- **Tags**: Applicable signals from list below

**Mandatory types** (include at least one of each):

| Type | Description |
|------|-------------|
| New hires | People in role <8 months |
| Lack of department | Companies missing relevant teams |
| Funding | Raised in past 12 months |
| Hiring | Currently hiring relevant roles |
| Technologies | Using or not using relevant tech |
| Growth | Growing or shrinking headcount/revenue |

**Rules**:
- Max 2 signals per idea
- Only use info from the playbook
- Always start with geographic region
- Focus on observable "outside-in" signals

### 3. Create Interactive HTML Artifact

Create an HTML artifact with:
- Clickable row numbers that trigger `[write-sequence]` for that idea
- Clean table styling
- All 20 targeting ideas displayed
- Data stored in JavaScript for easy access

**HTML Structure:**
```html
<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: system-ui; padding: 20px; max-width: 1400px; margin: 0 auto; }
  h1 { margin-bottom: 8px; }
  .instructions { color: #6b7280; margin-bottom: 24px; font-size: 14px; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #f3f4f6; padding: 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e5e7eb; }
  td { padding: 12px; border-bottom: 1px solid #e5e7eb; }
  .id-cell { text-align: center; font-weight: 600; width: 60px; }
  .id-button { 
    background: #3b82f6; 
    color: white; 
    border: none; 
    padding: 6px 12px; 
    border-radius: 6px; 
    cursor: pointer; 
    font-weight: 600;
    transition: background 0.2s;
  }
  .id-button:hover { background: #2563eb; }
  .id-button:active { background: #1d4ed8; }
  .tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag { background: #dbeafe; color: #1e40af; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
  .toast { 
    position: fixed; 
    bottom: 20px; 
    right: 20px; 
    background: #10b981; 
    color: white; 
    padding: 12px 20px; 
    border-radius: 8px; 
    font-weight: 600;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
  }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
<h1>Targeting Ideas - Click to Copy Command</h1>
<p class="instructions">Click any row number to copy the write-sequence command for that idea</p>
<table>
<thead>
  <tr>
    <th class="id-cell">#</th>
    <th>Campaign</th>
    <th>Company Targeting</th>
    <th>Personas</th>
    <th>Tags</th>
  </tr>
</thead>
<tbody id="ideas-table"></tbody>
</table>
<div id="toast" class="toast">Copied to clipboard!</div>
<script>
const ideas = /* JSON DATA HERE */;

async function copyCommand(id) {
  const command = `[write-sequence] #${id}`;
  try {
    await navigator.clipboard.writeText(command);
    showToast();
  } catch (err) {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = command;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    showToast();
  }
}

function showToast() {
  const toast = document.getElementById('toast');
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2000);
}

// Render table
ideas.forEach(idea => {
  const row = document.createElement('tr');
  row.innerHTML = `
    <td class="id-cell"><button class="id-button" onclick="copyCommand(${idea.id})">${idea.id}</button></td>
    <td>${idea.title}</td>
    <td>${idea.company_targeting}</td>
    <td>${idea.persona_targeting}</td>
    <td class="tags">${idea.tags.map(t => `<span class="tag">${t}</span>`).join('')}</td>
  `;
  document.getElementById('ideas-table').appendChild(row);
});
</script>
</body>
</html>
```

### 4. Save JSON File

Save data to `/mnt/user-data/outputs/targeting-ideas-{YYYY-MM-DD}.json`:

```json
{
  "generated_at": "ISO timestamp",
  "ideas": [
    {
      "id": 1,
      "title": "...",
      "company_targeting": "...",
      "persona_targeting": "...",
      "tags": []
    }
  ]
}
```

**Integration with write-sequence:**
When user clicks a row number and responds with `[write-sequence] #X`, Claude:
1. Loads the targeting idea from the JSON file
2. Uses the GTM playbook already in context
3. Generates the 3-email sequence for that specific targeting segment

## Example

**User**: Here's my playbook. [targeting-ideas]

**Claude**: 
*Creates interactive HTML artifact with clickable table*

Saved to `targeting-ideas-2025-01-15.json`

Click any row number to copy `[write-sequence] #X` to your clipboard, then paste to generate the sequence.

---

**User**: *Clicks #3, pastes `[write-sequence] #3`*

**Claude**: 
*Loads targeting idea #3 from JSON*
*Generates 3-email sequence using that targeting criteria + GTM playbook*
