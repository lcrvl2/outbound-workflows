---
name: write-sequence
description: Write segment-specific cold email sequences using "the list is the message" philosophy. Triggered ONLY by the explicit command "[write-sequence]". Creates 3-email sequences for entire target segments (5-500 companies) based on targeting criteria and GTM playbook. Email 1 and 3 have subjects (separate threads), Email 2 is same-thread follow-up. NO individual company research - writes ONE sequence for the whole segment. Combines with gtm-playbook, instantly-lead-finder, exa-webset-fetcher, and instantly-dynamic-campaigns.
---

# Write Sequence Skill

Write segment-specific B2B cold email sequences where the targeting defines the message.

**Trigger:** Only activate when user explicitly includes `[write-sequence]` in their message.

## Core Philosophy: The List IS the Message

Your targeting criteria fundamentally shapes what you say. If you're targeting "Series A SaaS companies hiring their first VP Sales," you don't MENTION that they raised Series A or hired a VP Sales. You speak to what that MEANS:

- They're transitioning from founder-led to process-driven sales
- They're building their first structured sales motion
- They need to prove their go-to-market to investors

**Bad:** "I saw you raised Series A, congrats!"
**Good:** "Most teams moving from founder-led to structured sales struggle with..."

**The test:** Can you send the SAME sequence to all 500 companies in your segment and have every recipient think "How did they know exactly what I'm dealing with?"

## Hard Rules

| Rule | Requirement |
|------|-------------|
| Length | Max 80 words per email |
| Paragraphs | 2 lines max |
| Questions | ONE question mark per email |
| Dashes | Never use em dash (—), use regular dash |
| Punctuation | Never use exclamation marks |
| Sequence | 3 emails only |
| Subjects | Email 1 (yes), Email 2 (no), Email 3 (yes) |
| Mobile | Must be scannable on phone |

## Required Inputs

| Input | Description | Example |
|-------|-------------|---------|
| Targeting Idea | Segment definition with criteria | "Series A SaaS (fintech vertical), raised $5-15M in last 90 days, hiring first sales reps" OR `#3` (reference to targeting-ideas JSON) |
| GTM Playbook | Personas, pain points, value props | Attached file or generated |

**Note:** NO lead CSV required. This skill writes ONE sequence for the entire segment, whether that's 5 companies or 500.

**Targeting Idea Input Methods:**
1. **Direct text**: User provides the full targeting criteria as text
2. **Reference by ID**: User provides `#X` and Claude loads idea from `targeting-ideas-{date}.json`

## Workflow

### 0. Load Targeting Idea (if referenced by ID)

If user provides `[write-sequence] #X`:
1. Find most recent `targeting-ideas-*.json` file in `/mnt/user-data/outputs/`
2. Load idea with matching ID
3. Extract `title` as the targeting criteria
4. Extract `persona_targeting` for persona matching
5. Proceed with normal workflow using this loaded data

### 1. Understand the Segment

From the targeting idea, extract:
- **What phase are they in?** (e.g., post-Series A, scaling, transitioning)
- **What are they doing right now?** (e.g., hiring, expanding, pivoting)
- **What does that MEAN for them?** (e.g., need to prove GTM to investors, building sales from scratch)

**DO NOT research individual companies.** The targeting criteria tells you everything you need.

### 2. Match to Playbook Persona

From the GTM playbook:
1. Which persona matches this segment?
2. What are THAT persona's specific pain points?
3. Which selling points resonate with those pains?

**Critical:** Use the matched persona's actual pain points, not generic ones.

### 3. Craft Segment-Specific Strategy

**Email 1: The Reality Check**
- Open with the phase/situation they're in (without stating the obvious)
- Frame the pain point as what others in their situation experience
- Make it feel inevitable, not accusatory

**Email 2: The Proof Point** (Same thread, no subject)
- Short case study or specific example
- Must match their segment (vertical, size, stage)
- Show the outcome, not the product

**Email 3: The Breakup** (New thread, new subject)
- Acknowledge silence without being needy
- Reframe the value differently
- Easy out or easy in

### 4. Write the Sequence

**Email 1:**
- Subject line: 2-4 words max, segment-relevant
- Body: Pain point framing based on segment phase
- Use merge tags: {{firstName}}, {{companyName}}

**Email 2:**
- NO subject line (same thread as Email 1)
- Case study or proof point matching segment
- Keep it under 60 words

**Email 3:**
- Subject line: 2-4 words, different angle
- Breakup approach with easy out
- Final value reframe

### 5. Output Format

Provide the sequence in this structure:

```
## Email 1: [Subject Line]

[Email body with merge tags]

---

## Email 2: [No Subject - Same Thread]

[Email body with merge tags]

---

## Email 3: [Subject Line]

[Email body with merge tags]
```

## Writing Quality Standards

### What to Include

- Pain points from matched persona in playbook
- Language/terminology common to their segment
- Signals that stack (e.g., "Series A" + "hiring sales" + "fintech" = specific phase)
- Observations about what happens at their stage
- Case studies matching their segment exactly
- Natural merge tag usage: {{firstName}}, {{companyName}}

### What NOT to Include

- Stating obvious signals ("I saw you raised Series A")
- Subject lines in email body
- Signatures or sign-offs
- Emojis
- Generic compliments ("I love what you're doing")
- Made-up case studies or metrics
- Placeholders like [Company] or {value}
- Multiple questions per email
- ROI without context
- Your company name
- Filler phrases ("just checking in", "circling back")

## Example: Series A SaaS Scaling Sales

**Targeting Idea:** "Series A B2B SaaS companies (fintech vertical), raised $5-15M in last 90 days, hiring first sales reps"

**What This Means:**
- Transitioning from founder-led sales to structured process
- Need to prove scalable GTM to investors
- Building sales motion from scratch
- Under pressure to show growth trajectory

### Sequence Output:

```
## Email 1: Structured sales

{{firstName}} - most teams moving from founder-led to their first structured sales motion hit the same wall around month 3.

The reps you hired know how to sell. But they don't know your buyers, your deal cycle, or which signals actually convert. So they thrash while you're still the closer.

Worth a quick look at how others in fintech have built their first playbooks?

---

## Email 2: [No Subject - Same Thread]

ClearLedger (Series A, raised $8M) went from 2 founder deals to 15 rep-sourced deals in 90 days.

They didn't change their reps. They just gave them a repeatable system for finding and qualifying the right accounts.

---

## Email 3: Wrong timing?

{{firstName}} - might have caught you at the wrong time.

If you're already nailing the transition from founder-led to rep-driven sales, no worries. If it's still causing headaches, happy to show what's working for others in fintech.

Either way, all good.
```

## Skill Chaining

Works with: `gtm-playbook`, `instantly-lead-finder`, `exa-webset-fetcher`, `instantly-dynamic-campaigns`

**Recommended workflow:**
1. Use `gtm-playbook` to generate personas and pain points
2. Use `instantly-lead-finder` or `exa-webset-fetcher` to build target list
3. Use `[write-sequence]` to create segment-specific sequence
4. Use `instantly-dynamic-campaigns` to deploy as dynamic campaign

**Example request (direct targeting criteria):**
```
[write-sequence]

Targeting: Series A fintech SaaS, raised $5-15M in last 90 days, hiring first sales reps

GTM Playbook: [attached]
```

**Example request (reference targeting-ideas by ID):**
```
[write-sequence] #3
```
*Claude loads idea #3 from targeting-ideas JSON and uses GTM playbook already in context*

Output: Complete 3-email sequence ready to send to all 500 companies in that segment.

## Critical Reminders

1. **The list IS the message** - Targeting criteria fundamentally shapes your messaging
2. **Segment-first thinking** - Understand what the targeting criteria MEANS, not just what it is
3. **No individual research** - Write ONE sequence for the entire segment
4. **Stack the signals** - Use multiple targeting criteria as proof you understand their phase
5. **Pain points from persona** - Not generic pains, use the matched persona's specific struggles
6. **Case studies must match** - Same vertical, same stage, same size

**The goal:** Every recipient should think "How did they know exactly what I'm dealing with right now?" - NOT "How did they know I raised Series A?" (that's public information, dummy).

**Quality test:** If you can't send the SAME sequence to all 500 companies in the segment and have it feel relevant, you did it wrong.
