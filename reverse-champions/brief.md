# Reverse Champions Play — Brief

## Context

We want a repeatable way to generate high-trust outbound lists from our closed-won customers. When we win a customer, we look at the people involved (CW users) and identify the companies they previously worked at, then reach out to those companies. This is warmer than cold outreach because there's a real connection point: someone in their network has already adopted Agorapulse.

The credibility signal is strong — a former employee of the target company independently chose Agorapulse at their next role, which implies the product solves problems relevant to teams like theirs.

Initial batch: all CW deals from 2025.

## Objective

For each CW user, identify the last 2 companies they worked at previously, find the right contacts, and run a champion-angle sequence that references the former employee's switch — without ever naming them. Convert that warm signal into meetings and SQLs.

## Tools Required

- Salesforce (CW deals/users source + tracking + attribution)
- Apollo (list building + enrichment + sequencing)
- Apify (LinkedIn profile scraping for work history)
- Claude Haiku (ambiguous job title classification)

## Campaign Flow

1. Source CW users from Salesforce (start with 2025 CW deals)
2. For each user, scrape LinkedIn work history via Apify (last 2 previous employers)
3. Role filtering: keep only marketing/social/content/comms positions (regex + Haiku fallback for ambiguous titles). Exclude interns, finance, unrelated functions, advisory/investor roles
4. For each previous employer, validate the target company fits criteria (ICP, employee threshold, not current client, exclude competitor list)
5. Enrich + dedupe against existing CRM records
6. Find 1-3 contacts per target company via Apollo People Search:
   - 1 marketing/comms leader
   - 1-2 social media managers or content leads
7. Enqueue contacts into Apollo sequence with champion-angle copy
8. Replies go to BDR for discovery/demo. Track outcomes by source CW user / CW deal

## Messaging

**Core angle:** "Someone who used to work at {{companyName}} now uses Agorapulse. I can share why they switched and what changed for their team."

**Guidelines:**
- NEVER name the champion, their current role, or their current company
- Only allowed reference: "someone who used to work at {{companyName}}" or "a former {{companyName}} team member"
- The BDR checks CRM notes / asks CSM before the discovery call to know WHY the champion switched — so the offer to share is genuine
- Lead with the reason to care ("why they chose us") rather than the tool list
- Position it as relevant insider context, not a referral or introduction
- Don't claim things about the champion that can't be verified
- Low-friction CTAs: "worth a quick chat?" / "happy to share what we know"

### Email 1 — New Thread

**Subject:** Former colleague, new stack

> {{firstName}},
>
> Someone who used to work at {{companyName}} now uses Agorapulse.
>
> I can share why they switched to a new SMM tool and what changed for their team after.
>
> If that's relevant to what you're dealing with today, worth a quick chat?

### Email 2 — Reply to Email 1 (No Subject)

> {{firstName}},
>
> Separate data point: Adtrak, a UK agency, replaced their previous tool with Agorapulse and scaled from 3 to 7 social managers running 100+ profiles - without adding complexity.
>
> Here's the full story: [link to Adtrak case study]

### Email 3 — New Thread

**Subject:** Social media ROI

> {{firstName}},
>
> Most marketing teams I talk to have the same blind spot - they know social is working but can't put a number on it when leadership asks.
>
> Agorapulse has a built-in ROI report that ties social posts directly to revenue. No spreadsheets, no guessing.
>
> No worries if {{companyName}} already has this sorted. If not, thought it was worth flagging.

### Email 4 — Reply to Email 3 (No Subject)

> {{firstName}},
>
> Last note from me. A former {{companyName}} team member has been using Agorapulse regularly, so I thought it was worth reaching out.
>
> If you're ever curious why they made the switch, happy to share what we know.
>
> Either way, I'll stop reaching out. Hope {{companyName}} is crushing it on social!

### Sequence Timing

| Step | Day | Thread | Subject |
|------|-----|--------|---------|
| Email 1 | Day 0 | New | Former colleague, new stack |
| Email 2 | Day 3 | Reply to 1 | — |
| Email 3 | Day 7 | New | Social media ROI |
| Email 4 | Day 10 | Reply to 3 | — |

## Next Steps

- [x] Confirm CW user export fields from Salesforce
- [x] Lock initial ICP/company filters and suppression lists
- [x] Get a real closed-won export CSV with LinkedIn URLs
- [x] Create the 4-step sequence in Apollo (`698f40f00ef2f30021af248d`) with the copy above
- [x] Custom field `[Org] Became Paid Date` created in Apollo for ongoing Salesforce tracking
- [ ] Define BDR reply routing: who handles responses, how fast
- [ ] Brief BDRs on the play: check CRM notes before discovery calls to know champion's switch reasons
- [ ] Pilot with 2025 CW cohort and validate reply/meeting/SQL rate before scaling
