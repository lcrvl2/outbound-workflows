#!/usr/bin/env python3
"""
Fetch LinkedIn posts from an Apify dataset and write them to a .md file.

Usage:
    python3 fetch_and_write_posts.py <dataset_id> <profile_name> <profile_url> <output_path> [--limit N]

Example:
    python3 fetch_and_write_posts.py UYQOuWhmyn5Kf0TYO "Pierre Herubel" \
        "https://www.linkedin.com/in/pierre-herubel-540b3949/" \
        ./pierre-herubel-content.md --limit 100
"""

import argparse
import json
import ssl
import sys
import urllib.request
import urllib.error


def fetch_posts(dataset_id: str, limit: int = 100) -> list:
    """Fetch posts from Apify public dataset API in batches of 15 to avoid truncation."""
    all_posts = []
    batch_size = 15
    offset = 0

    # Handle macOS SSL certificate issues
    ctx = ssl.create_default_context()
    try:
        urllib.request.urlopen("https://api.apify.com", timeout=5, context=ctx)
    except Exception:
        ctx = ssl._create_unverified_context()

    while offset < limit:
        current_batch = min(batch_size, limit - offset)
        url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?format=json&limit={current_batch}&offset={offset}"
        )
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                all_posts.extend(data)
        except urllib.error.URLError as e:
            print(f"Error fetching offset {offset}: {e}", file=sys.stderr)
            break
        offset += current_batch

    return all_posts


def extract_date(post: dict) -> str:
    """Extract date from post, handling nested and flat formats."""
    # Try flat key first (Apify flattens nested keys with dots)
    date = post.get("postedAt.date")
    if not date:
        posted_at = post.get("postedAt", {})
        if isinstance(posted_at, dict):
            date = posted_at.get("date")
        elif isinstance(posted_at, str):
            date = posted_at
    if date and "T" in str(date):
        date = str(date).split("T")[0]
    return str(date) if date else "Unknown"


def write_md(posts: list, profile_name: str, profile_url: str, output_path: str):
    """Write posts to a formatted .md file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {profile_name} - LinkedIn Content ({len(posts)} Posts)\n\n")
        f.write(f"Profile: {profile_url}\n\n")

        for i, post in enumerate(posts, 1):
            date = extract_date(post)
            url = post.get("linkedinUrl", "N/A")
            content = post.get("content", "")

            f.write(f"---\n\n## Post {i}\n\n")
            f.write(f"**Date:** {date}\n\n")
            f.write(f"**URL:** {url}\n\n")
            f.write(f"{content}\n\n")

    print(f"Written {len(posts)} posts to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Fetch LinkedIn posts from Apify dataset and write to .md")
    parser.add_argument("dataset_id", help="Apify dataset ID")
    parser.add_argument("profile_name", help="Display name for the profile")
    parser.add_argument("profile_url", help="LinkedIn profile URL")
    parser.add_argument("output_path", help="Output .md file path")
    parser.add_argument("--limit", type=int, default=100, help="Max posts to fetch (default: 100)")

    args = parser.parse_args()

    print(f"Fetching up to {args.limit} posts from dataset {args.dataset_id}...")
    posts = fetch_posts(args.dataset_id, args.limit)

    if not posts:
        print("No posts fetched. Check the dataset ID.", file=sys.stderr)
        sys.exit(1)

    write_md(posts, args.profile_name, args.profile_url, args.output_path)


if __name__ == "__main__":
    main()
