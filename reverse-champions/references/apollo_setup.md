# Apollo Setup Guide

One-time setup for the reverse-champions pipeline. Creates custom contact fields and a sequence template.

## Step 1: Create Custom Contact Fields

In Apollo, go to **Settings > Custom Fields > Contact Fields** and create the following:

| Field Name | API Key | Type | Description |
|-----------|---------|------|-------------|
| Champion Email 1 Subject | `champion_email_1_subject` | Text | Subject line for email 1 |
| Champion Email 1 Body | `champion_email_1_body` | Text Area | Full body of email 1 |
| Champion Email 2 Body | `champion_email_2_body` | Text Area | Full body of email 2 (same thread, no subject) |
| Champion Email 3 Subject | `champion_email_3_subject` | Text | Subject line for email 3 |
| Champion Email 3 Body | `champion_email_3_body` | Text Area | Full body of email 3 |

**Important**: Use "Text Area" (not "Text") for body fields to support multi-line content.

## Step 2: Create Sequence Template

Create a new sequence in Apollo called "Reverse Champions - [Your Product]":

### Step 1 (Day 0): Auto Email
- **Subject**: `{{custom.champion_email_1_subject}}`
- **Body**: `{{custom.champion_email_1_body}}`
- **Type**: New thread

### Step 2 (Day 3): Auto Email
- **Subject**: (leave blank - same thread as Step 1)
- **Body**: `{{custom.champion_email_2_body}}`
- **Type**: Reply to previous

### Step 3 (Day 7): Auto Email
- **Subject**: `{{custom.champion_email_3_subject}}`
- **Body**: `{{custom.champion_email_3_body}}`
- **Type**: New thread

### Timing Recommendations

| Step | Day | Type |
|------|-----|------|
| Email 1 | Day 0 | New thread |
| Email 2 | Day 3 | Same thread (reply) |
| Email 3 | Day 7 | New thread |

## Step 3: Get Sequence ID

After creating the sequence, get its ID for the pipeline:

1. Open the sequence in Apollo
2. The URL will be: `https://app.apollo.io/#/sequences/SEQ_ID`
3. Copy the `SEQ_ID` value
4. Use it with `--sequence-id SEQ_ID` when running the pipeline

## Step 4: Configure .env

Ensure your `.env` file has the required API keys:

```
APOLLO_API_KEY=your_apollo_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
APIFY_TOKEN=your_apify_token_here
```

## How It Works

The pipeline generates complete, unique emails for each contact and stores them in Apollo custom fields. The sequence steps render the custom field values - no template logic needed.

This means:
- Each contact gets fully personalized emails (not template variables)
- You can preview exact email text in Apollo before the sequence sends
- You can manually edit any email in the custom field before sending
- The sequence is reusable - just update custom fields for new contacts

## Verification Checklist

After setup, verify:

- [ ] All 5 custom fields created
- [ ] Sequence has 3 steps with correct custom field references
- [ ] Step 2 is configured as "reply to previous" (not new thread)
- [ ] Step 3 is configured as "new thread"
- [ ] API keys are set in `.env`
- [ ] Run a test with 1 contact to verify fields populate correctly
