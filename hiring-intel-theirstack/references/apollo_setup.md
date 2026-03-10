# Apollo Setup Guide

One-time setup for the hiring-intel pipeline. Creates custom contact fields and a sequence template.

## Step 1: Create Custom Contact Fields

In Apollo, go to **Settings > Custom Fields > Contact Fields** and create 3 body fields:

| Field Name | API Key | Type | Field ID |
|-----------|---------|------|----------|
| Outbound Email 1 Body | `outbound_email_1_body` | Multi-line text | `698da90737e1ef000d656492` |
| Outbound Email 2 Body | `outbound_email_2_body` | Multi-line text | `698da91367e36600151d3167` |
| Outbound Email 3 Body | `outbound_email_3_body` | Multi-line text | `698da91df035d70015a9a380` |

Subject lines are written manually in the sequence template (not stored as custom fields).

**Important**: Use "Multi-line text" (not "Single-line text") for body fields to support multi-paragraph content.

## Step 2: Create Sequence Template

Create a new sequence in Apollo (e.g., "Outbound Sequence - [Your Campaign]"):

### Step 1 (Day 0): Auto Email
- **Subject**: Write manually per sequence
- **Body**: `{{custom.outbound_email_1_body}}`
- **Type**: New thread

### Step 2 (Day 3): Auto Email
- **Subject**: Write manually per sequence
- **Body**: `{{custom.outbound_email_2_body}}`
- **Type**: New thread

### Step 3 (Day 7): Auto Email
- **Subject**: Write manually per sequence
- **Body**: `{{custom.outbound_email_3_body}}`
- **Type**: New thread

### Timing Recommendations

| Step | Day | Type |
|------|-----|------|
| Email 1 | Day 0 | New thread |
| Email 2 | Day 3 | New thread |
| Email 3 | Day 7 | New thread |

Adjust timing based on your typical response patterns.

## Step 3: Sequence ID

Current sequence: `69946a6089cfe2000dff7edb`

Use with `--sequence-id 69946a6089cfe2000dff7edb` when running the pipeline.

## Step 4: Configure .env

Ensure your `.env` file has the required API keys:

```
APOLLO_API_KEY=your_apollo_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Optional (for scraping):
```
APIFY_TOKEN=your_apify_token_here
CRAWL4AI_BASE_URL=http://localhost:11235
```

## How It Works

The pipeline generates complete, unique emails for each company and stores the bodies in Apollo custom fields. The sequence steps render the custom field values — subject lines are set once in the sequence template.

This means:
- Each contact gets fully personalized email bodies (not template variables)
- You can preview exact email text in Apollo before the sequence sends
- You can manually edit any email in the custom field before sending
- The sequence is reusable — just update custom fields for new contacts

## Apollo API Details

The pipeline uses `PATCH /api/v1/contacts/{contact_id}` to write custom fields.

**Critical requirements** (discovered through testing):
- **Auth**: Must use `x-api-key` header (NOT `api_key` in JSON body — body auth silently no-ops on custom field writes)
- **Payload**: `{"typed_custom_fields": {"<field_id>": "<value>"}}` — dict with field IDs as keys
- Field **names** as keys silently no-op; only field **IDs** work
- Array format for `typed_custom_fields` returns 422
- `custom_fields` key (without `typed_`) silently no-ops

## Verification Checklist

After setup, verify:

- [ ] 3 body custom fields created (IDs match `push_to_apollo.py`)
- [ ] Sequence has 3 steps with `{{custom.outbound_email_X_body}}` in body
- [ ] Subject lines set manually in each sequence step
- [ ] All 3 steps are configured as "new thread"
- [ ] API keys are set in `.env`
- [ ] Run a test with 1 company to verify fields populate correctly
