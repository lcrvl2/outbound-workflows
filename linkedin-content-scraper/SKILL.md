---
name: linkedin-content-scraper
description: Scrape LinkedIn profile posts using Apify and save them as formatted .md files. Use when scraping LinkedIn posts, extracting LinkedIn content, building content libraries from LinkedIn creators, or creating custom instructions from LinkedIn profiles. Triggers on requests involving LinkedIn post scraping, content extraction, or creator content analysis.
---

# LinkedIn Content Scraper

Scrape the latest posts from any LinkedIn profile using the Apify Actor `harvestapi/linkedin-profile-posts`, then write results to a formatted `.md` file per creator.

## Workflow

### Step 1: Launch the Apify scrape

Use `call-actor` with the Actor `harvestapi/linkedin-profile-posts`.

Input format:
```json
{
  "targetUrls": ["https://www.linkedin.com/in/<profile-slug>/"],
  "maxPosts": 100,
  "includeReposts": false,
  "includeQuotePosts": true,
  "scrapeReactions": false,
  "scrapeComments": false
}
```

- Cost: ~$0.002/post ($0.20 for 100 posts)
- No LinkedIn cookies required
- For multiple profiles, launch one Actor run per profile in parallel

### Step 2: Get the dataset ID

After the Actor run completes, note the `defaultDatasetId` from the run output. This ID is needed to fetch the posts.

### Step 3: Write the .md file

Run the bundled script to fetch posts from the Apify dataset and write the `.md` file:

```bash
python3 scripts/fetch_and_write_posts.py <dataset_id> "<Profile Name>" "<linkedin_url>" <output_path> --limit 100
```

Example:
```bash
python3 scripts/fetch_and_write_posts.py UYQOuWhmyn5Kf0TYO "Pierre Herubel" \
    "https://www.linkedin.com/in/pierre-herubel-540b3949/" \
    ./pierre-herubel-content.md --limit 100
```

For multiple profiles, run scripts in parallel (e.g. two parallel Bash Task agents).

The script:
- Fetches posts from the public Apify REST API in batches of 15 (avoids truncation at 50k chars)
- Handles SSL certificate issues on macOS
- Extracts `content`, `postedAt.date`, and `linkedinUrl` fields
- Writes a formatted `.md` file with numbered posts, dates, and URLs

### Output format

```markdown
# {Name} - LinkedIn Content ({N} Posts)

Profile: {linkedin_url}

---

## Post 1

**Date:** 2026-01-29

**URL:** https://www.linkedin.com/posts/...

{post content}

---

## Post 2
...
```

## Key constraints

- **Batch size 15**: The Apify MCP tool truncates output at ~50k chars. Always use batches of 15 when fetching via `get-actor-output`. The bundled script handles this automatically.
- **Public API**: Apify datasets are accessible without a token at `https://api.apify.com/v2/datasets/{id}/items?format=json&limit=15&offset=0`
- **Fields**: Only `content`, `postedAt.date`, and `linkedinUrl` are needed for the `.md` file.
