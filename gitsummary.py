#!/usr/bin/env python3
"""
gitsummary.py - Summarize git commits from the last N days using OpenRouter API.

Usage:
    python gitsummary.py [--days N]

Options:
    --days N   Number of days to look back (default: 7)
"""

import argparse
import subprocess
import os
import sys
import requests
from datetime import datetime, timedelta


def get_git_log(days):
    """Fetch git commits from the last N days."""
    since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    cmd = [
        'git', 'log',
        f'--since={since_date}',
        '--pretty=format:%an%x09%s%x09%H%x09%ad',
        '--date=short'
    ]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return output.strip().split('\n') if output.strip() else []
    except subprocess.CalledProcessError as e:
        print(f"Error running git log: {e.output}", file=sys.stderr)
        sys.exit(1)


def group_commits_by_author(commit_lines):
    """Group commits by author."""
    grouped = {}
    for line in commit_lines:
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 4:
            continue
        author, subject, hash_, date = parts[0], parts[1], parts[2], parts[3]
        grouped.setdefault(author, []).append({
            'subject': subject,
            'hash': hash_,
            'date': date
        })
    return grouped


def format_commits_for_prompt(grouped):
    """Format grouped commits into a prompt for the API."""
    lines = []
    for author, commits in grouped.items():
        lines.append(f"Author: {author}")
        for commit in commits:
            lines.append(f"  - [{commit['date']}] {commit['subject']} ({commit['hash'][:7]})")
        lines.append("")  # blank line between authors
    return "\n".join(lines)


def call_openrouter_api(prompt, api_key):
    """Call OpenRouter API to get a summary."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openrouter/free",  # using a common model; can be made configurable
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that summarizes git commit logs into a concise paragraph."},
            {"role": "user", "content": f"Based on the following git commit log from the last few days, write a one-paragraph summary of what the team worked on:\n\n{prompt}"}
        ],
        "max_tokens": 1000,
        "temperature": 0.5
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouter API: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError) as e:
        print(f"Error parsing API response: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Summarize git commits from the last N days.")
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    args = parser.parse_args()

    # Check for API key
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Get git log
    commit_lines = get_git_log(args.days)
    if not commit_lines:
        print("No commits found in the last {args.days} days.")
        return

    # Group by author
    grouped = group_commits_by_author(commit_lines)

    # Format for prompt
    prompt_text = format_commits_for_prompt(grouped)

    # Call API
    summary = call_openrouter_api(prompt_text, api_key)

    # Print summary
    print("\nSummary of the last {args.days} days:")
    print(summary)


if __name__ == '__main__':
    main()