---
name: gtm-playbook
description: Generate comprehensive Go-To-Market (GTM) playbooks from any website URL. Use when the user asks to create a GTM playbook, sales playbook, outbound playbook, ICP analysis, or market research document for a company/product based on their website. Triggers on phrases like "create a GTM playbook for [website]", "analyze [company] for outbound", "build a sales playbook", "identify ICPs for [product]", or "generate target personas from [URL]".
---

# GTM Playbook Generator

Generate sales-ready Go-To-Market playbooks by analyzing company websites. Output includes product positioning, target verticals, buyer personas, and case studies—everything a GTM team needs to execute outbound campaigns.

## Workflow

### Step 1: Gather Website Intelligence

Use Exa web search to deeply analyze the target website:

```
Exa:web_search_exa with query: "site:[domain] product features pricing customers"
```

Then fetch key pages directly:
- Homepage
- About/Company page
- Pricing page
- Solutions/Products pages
- Case studies/Customers page
- Blog (for positioning insights)

Use `web_fetch` for any URLs discovered. Aim for 5-10 pages of content.

### Step 2: Analyze & Generate Playbook Sections

Generate each section sequentially, using the gathered content:

#### 2.1 Product Description
Analyze: What exactly does this product/service do? What's the value prop? What makes it unique?

Requirements:
- Be PRECISE—this trains new sales hires
- Plain English, no marketing fluff
- Include: core functionality, key differentiators, pricing model (if found), tech stack/integrations

#### 2.2 Target Verticals (2-5 verticals)
For each vertical include:
- **Industry name**
- **Company size** (headcount range)
- **Geographic focus** (derive from website; default to "United States" if unclear)
- **Why it's a fit** (specific alignment with product capabilities)
- **Example companies** (3-5 real examples)
- **Key challenges** the product solves for this vertical

#### 2.3 Target Personas (1-5 per vertical)
Focus on DECISION MAKERS only. For each persona:
- **Job title**
- **Role description**
- **Pain points** (specific, not generic)
- **Professional goals**
- **Selling points** that resonate with this persona
- **Objections** they might raise

#### 2.4 Case Studies & Social Proof
Extract from website:
- Customer success stories (company name, challenge, solution, results)
- Testimonials (with company/person attribution)
- Logos/notable customers
- Metrics and proof points

If none found, note "No case studies found on website" and suggest the user add them manually.

### Step 3: Generate Output

Create the playbook as:
1. **Artifact** (React/HTML) - Interactive, styled playbook
2. **Markdown file** - Downloadable `.md` in `/mnt/user-data/outputs/`

## Output Template

See `references/playbook-template.md` for the exact output structure.

## Special Instructions Handling

If user provides additional requirements:
- Company context they want emphasized
- Specific verticals to focus on
- Personas to prioritize
- Tone/style preferences
- Competitor positioning

Incorporate these throughout the analysis.

## Quality Standards

- **Specificity over generality**: "CFOs at Series B+ SaaS companies" not "Finance leaders"
- **Actionable insights**: Every section should help a sales rep write better emails
- **Real examples**: Use actual company names, real job titles, specific metrics
- **No fluff**: If you can't find solid info, say so rather than making it generic
