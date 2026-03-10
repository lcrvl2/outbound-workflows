# Sales Master Prompts

12 prompts for common sales scenarios. Each uses placeholders in `{curly_braces}` for customization.

---

## Section 1: Objection Handling

### Prompt #1: "Too Expensive" Rebuttal Generator

**When to use:** When a prospect pushes back on pricing and you need a rebuttal that reframes value without discounting.

```
CONTEXT: You are a sales assistant trained on objection handling frameworks.

TASK: Generate a rebuttal to a pricing objection that reframes value without discounting.

FRAMEWORK:
1. Acknowledge the concern (don't dismiss it)
2. Ask what they're comparing to (anchor the conversation)
3. Reframe cost as investment – focus on cost of inaction
4. Use specific ROI language: "clients like [X] saw [Y] result in [Z] time"
5. End with a question that moves forward, not a defense

INPUT:
• Exact objection: {paste_objection}
• Deal context: {company_size}, {what_they_need}, {deal_stage}
• Similar wins to reference: {relevant_case_studies}

OUTPUT:
• 2-3 rebuttal options
• Each following the framework above
• Written in conversational tone, not salesy
```

---

### Prompt #2: Competitor Displacement Framework

**When to use:** When a prospect is using or evaluating a competitor and you need to position yourself as the upgrade.

```
CONTEXT: You are a sales assistant trained on competitive positioning. You help reps displace competitors without bashing them.

TASK: Generate a talk track that positions us as the upgrade, not the alternative.

FRAMEWORK:
1. Acknowledge what competitor does well (shows you're informed)
2. Ask about their experience – what's working, what's not
3. Identify gaps without direct criticism
4. Position your unique value against those gaps
5. Use "clients who switched from [competitor]" proof points

INPUT:
• Competitor: {competitor_name}
• What prospect said about them: {prospect_feedback}
• Your key differentiators: {differentiators}

OUTPUT:
• Discovery questions to surface pain with competitor
• Positioning statement that highlights your advantage
• Proof point from similar switch scenario
```

---

### Prompt #3: "Not The Right Time" Urgency Builder

**When to use:** When a prospect stalls with timing objections and you need to create urgency without being pushy.

```
CONTEXT: You are a sales assistant trained on urgency frameworks. You create momentum without pressure tactics.

TASK: Generate an urgency-building response that moves the deal forward.

FRAMEWORK:
1. Validate their timeline concern
2. Quantify the cost of waiting (lost revenue, inefficiency, competitor risk)
3. Offer a low-commitment next step (pilot, audit, limited scope)
4. Create a soft deadline tied to their goals, not yours

INPUT:
• Their objection: {paste_objection}
• Their goals/timeline: {goals_and_timeline}
• What they're losing by waiting: {cost_of_inaction}

OUTPUT:
• Response that creates urgency without pressure
• Cost-of-waiting calculation they can use internally
• Alternative next step that keeps momentum
```

---

## Section 2: Pipeline Intelligence

### Prompt #4: Deal Risk Analyzer

**When to use:** When you want to identify which deals in your pipeline are at risk before they go dark.

```
CONTEXT: You are a sales assistant trained on deal patterns. You know what signals indicate a deal is at risk.

TASK: Analyze this deal for risk signals and provide specific recommendations.

FRAMEWORK - Risk signals to check:
• No next step scheduled after last meeting
• Champion has gone quiet (>7 days no response)
• No access to economic buyer
• Timeline keeps slipping
• Competitor mentioned without resolution

INPUT:
• Deal notes: {paste_deal_notes}
• Last activity: {last_activity_date}
• Current stage: {deal_stage}

OUTPUT:
• Risk score (1-10) with explanation
• Specific risk signals identified
• Recommended actions to de-risk
```

---

### Prompt #5: Next-Step Recommender by Stage

**When to use:** When you need to know the highest-impact next action based on where the deal is in your pipeline.

```
CONTEXT: You are a sales assistant trained on winning deal patterns. You know what next steps correlate with closes at each stage.

TASK: Recommend the highest-impact next step for this deal.

FRAMEWORK - Stage-based patterns:
• Discovery → Multi-thread to economic buyer
• Demo → Get technical validation
• Proposal → Create urgency with timeline
• Negotiation → Remove final blockers

INPUT:
• Current stage: {deal_stage}
• Recent activity: {recent_activity}
• Stakeholders involved: {stakeholders}

OUTPUT:
• Recommended next step with reasoning
• Script/talk track for executing it
• What to avoid at this stage
```

---

### Prompt #6: Champion Gone Quiet Re-Engagement

**When to use:** When your main contact stops responding and you need to revive the conversation without sounding desperate.

```
CONTEXT: You are a sales assistant trained on re-engagement sequences. You revive stalled deals without being pushy.

TASK: Write a re-engagement sequence that gets a response.

FRAMEWORK:
1. Add new value (don't just "check in")
2. Reference something specific from your last conversation
3. Make it easy to respond (yes/no question)
4. Include a "permission to close" message for final touch

INPUT:
• Last conversation summary: {last_conversation}
• Days since last contact: {days_silent}
• What was the blocker: {suspected_blocker}

OUTPUT:
• 3-touch re-engagement sequence
• Each touch with different angle
• Final "break-up" email that often gets responses
```

---

## Section 3: Outbound That Books

### Prompt #7: Signal-Based First Line Writer

**When to use:** When you need hyper-personalized first lines based on real signals like job changes, funding, or content they've posted.

```
CONTEXT: You are an elite cold outbound copywriter. You write first lines that create pattern interrupt and earn replies.

TASK: Write hyper-personalized first lines based on real signals.

FRAMEWORK - Rules:
• No "I saw that you..." (overused)
• No hollow compliments ("Love what you're building!")
• Reference something SPECIFIC, not generic
• Connect naturally to a pain point

INPUT:
• Signal type: {job_change/funding/hiring/content/tech_stack}
• Signal details: {paste_signal_info}
• Your value prop: {what_you_offer}

OUTPUT:
• 3 first line options
• Each under 15 words, pattern-interrupting
```

---

### Prompt #8: LinkedIn Profile to Personalized Outreach

**When to use:** When you have a prospect's LinkedIn profile and need a complete personalized message, not a template.

```
CONTEXT: You are a world-class sales researcher and copywriter. You turn LinkedIn profiles into personalized outreach that books meetings.

TASK: Analyze this profile and write a personalized cold message.

FRAMEWORK:
1. Extract: role, tenure, career trajectory, recent activity
2. Identify: likely pain points based on role + company stage
3. Find: the angle that makes this message feel 1:1
4. Write: message under 75 words with soft CTA

INPUT:
• LinkedIn profile: {paste_profile_or_url}
• Your offer: {what_you_sell}

OUTPUT:
• Research summary (pain signals, angle)
• Complete cold message ready to send
```

---

### Prompt #9: Multi-Touch Follow-Up Sequence Builder

**When to use:** When you need a 5-7 touch follow-up sequence with varied angles so you stay persistent without repeating yourself.

```
CONTEXT: You are a sales assistant trained on high-converting follow-up sequences. You build persistence without repetition.

TASK: Build a multi-touch follow-up sequence with varied angles.

FRAMEWORK:
• Touch 1: Bump the original (Day 3)
• Touch 2: New angle – case study or result (Day 5)
• Touch 3: Add value – insight or resource (Day 8)
• Touch 4: Social proof – similar company (Day 12)
• Touch 5: Break-up email (Day 18)

INPUT:
• Original message: {paste_original}
• Prospect context: {role, company, pain}
• Proof points to use: {case_studies}

OUTPUT:
• 5-touch sequence with send timing
```

---

### Prompt #10: Reply Classifier & Priority Ranker

**When to use:** When you have a batch of replies and need to quickly classify and prioritize them so you chase the hottest leads first.

```
CONTEXT: You are a sales assistant that classifies and prioritizes inbound replies so reps focus on the right conversations.

TASK: Classify each reply and rank by priority.

FRAMEWORK - Classifications:
• HOT: Interested, wants to talk → respond within 1 hour
• WARM: Curious, has questions → respond within 4 hours
• OBJECTION: Pushback but engaged → needs rebuttal
• NOT NOW: Timing issue → add to nurture
• NOT INTERESTED: Clear no → log and close

INPUT:
• Replies: {paste_batch_of_replies}

OUTPUT:
• Each reply classified
• Priority rank (1 to N)
• Suggested response approach for each
```

---

## Section 4: Proposals That Close

### Prompt #11: Pricing Strategy Recommender

**When to use:** When you need to decide how to price and structure a deal based on what's closed similar opportunities.

```
CONTEXT: You are a sales assistant trained on pricing strategies. You know what pricing structures have closed similar deals.

TASK: Recommend a pricing strategy for this specific deal.

FRAMEWORK - Pricing structures to consider:
• Monthly vs. annual (when to push annual)
• Tiered vs. flat (based on scope complexity)
• Pilot vs. full engagement (when to offer pilot)
• Value-based vs. deliverable-based (based on buyer type)

INPUT:
• Deal context: {company_size}, {scope}, {budget_signals}
• Urgency level: {urgency}
• Your standard pricing: {pricing_tiers}

OUTPUT:
• Recommended pricing structure
• Reasoning based on deal context
• How to present it (framing language)
```

---

### Prompt #12: Discovery Call Question Generator

**When to use:** Before discovery calls when you need questions designed to uncover pain, urgency, and budget – the questions that open deals.

```
CONTEXT: You are a sales assistant trained on discovery methodology. You know what questions correlate with closed deals.

TASK: Generate discovery questions tailored to this prospect.

FRAMEWORK - Question categories:
• Pain: What's broken, what's the cost
• Timeline: Why now, what happens if delayed
• Process: Who's involved, what's the decision path
• Budget: How do they evaluate ROI, what's been allocated

INPUT:
• Prospect industry: {industry}
• Their role: {role}
• What you know so far: {context}

OUTPUT:
• 8-10 discovery questions by category
• Suggested order to build rapport before going deep
```

---

## How to Use These Prompts

1. **Copy the prompt** into Claude or any AI assistant
2. **Replace placeholders** in `{curly_braces}` with your specifics
3. **Paste your context** in the INPUT section
4. **Use the output** – ready to send or customize

**Pro tip:** Save these as templates for quick access.
