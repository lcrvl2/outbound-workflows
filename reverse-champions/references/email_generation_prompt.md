# Email Generation Prompt

Used by `generate_emails.py` (Claude Sonnet) to create champion-angle email sequences. Hybrid personalization: body per-company, subject + opener per-contact.

## Philosophy

**"The champion IS the signal."**

The fact that a former employee of the target company now uses Agorapulse is the strongest social proof available. But we never name the champion - the angle is "someone who's been in your shoes chose us."

## Hard Rules (Non-Negotiable)

| Constraint | Specification |
|------------|--------------|
| Email 1 length | Max 120 words |
| Email 2 length | Max 80 words |
| Email 3 length | Max 120 words |
| Paragraph structure | Max 2 lines per paragraph |
| Questions | Exactly ONE question mark per email |
| Dashes | Regular dash only (never em dash) |
| Exclamation marks | Forbidden |
| Emojis | Forbidden |
| Merge tags | `{{firstName}}`, `{{companyName}}` only |
| Champion name | NEVER mentioned |
| Champion identity | NEVER identifiable (no current role, company, or details) |

## Two-Part Generation (Hybrid)

### Part A: Company-Level (one generation per target company)

Generate the **email bodies** based on:
- Champion context (how many champions, which CW company they're at now - but never reveal this in the email)
- Target company industry/size
- Case studies matched to industry

All contacts at the same target company get the same body text.

### Part B: Contact-Level (one generation per contact)

Generate personalized **subject lines + opening sentences** based on:
- Contact's name ({{firstName}})
- Contact's title
- Contact's company ({{companyName}})

## Three-Email Structure

### Email 1: "The Insider" (New Thread)
- **Subject line**: 2-4 words, personalized to contact's role/industry
- **Opening**: Personalized sentence referencing their role/situation
- **Body**: Reference that someone who used to work at {{companyName}} now uses Agorapulse. Frame the value their team gets.
- **CTA**: Soft interest check ("Worth a quick look?")

### Email 2: "The Proof Point" (Same Thread, No Subject)
- **Body**: Short case study aligned with their industry/size. Concrete outcomes, not features.
- **CTA**: None explicit - proof speaks for itself, ends with a single question

### Email 3: "Social Proof + FOMO" (New Thread)
- **Subject line**: 2-4 words, different angle from Email 1
- **Opening**: Personalized sentence
- **Body**: "Companies like [type] are already doing X." Industry momentum framing.
- **CTA**: Easy out/easy in ("If timing's off, no worries. If not, happy to show you how...")

## Champion Privacy in Emails

### Single Champion
- "someone who used to work at {{companyName}}"
- "a former {{companyName}} team member"

### Multiple Champions
- "multiple people who've worked at {{companyName}} before"
- "several former {{companyName}} team members"

### NEVER
- Name the champion
- Mention their current company
- Mention their current title
- Offer an introduction

## Case Studies

Injected dynamically based on target company's `industry` field:

| Vertical | Case Study |
|----------|-----------|
| Agency (scaling) | **Adtrak** (UK, 51-200): switched from Hootsuite, doubled team 3->7, 100+ profiles for 400+ SME clients |
| Agency (cost) | **ClickMedia** (Australia): switched from Sprout Social, 25% cost reduction |
| Agency (migration) | **Quimby Digital** (US): migrated from Sprout Social, better cost structure |
| E-commerce | Generic: tracks social posts -> revenue in Shopify/WooCommerce, 30% savings |
| B2B SaaS | Generic: connects LinkedIn content to demo requests/pipeline in Salesforce |
| Enterprise | Generic: 20+ profiles, centralized approval workflows, dedicated support |

## JSON Output Format

```json
{
  "email_1_subject": "Subject line here",
  "email_1_opener": "Personalized opening sentence for contact.",
  "email_1_body": "Rest of email body (shared across contacts at this company).",
  "email_2_body": "Full email 2 body.",
  "email_3_subject": "Different subject line",
  "email_3_opener": "Personalized opening sentence for contact.",
  "email_3_body": "Rest of email 3 body (shared across contacts at this company)."
}
```

## What NOT to Include

- Signatures or formal sign-offs
- Generic compliments
- Filler phrases ("just checking in", "circling back")
- Unsupported ROI claims or made-up metrics
- Placeholders like [Company]
- Multiple questions per email
- Your company name in CTAs
- Subject lines in email body
- Calendar links or URLs
- Any reference to job postings or hiring
