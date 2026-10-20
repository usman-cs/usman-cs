#!/usr/bin/env python3
"""Generate a public SVG with aggregate GitHub profile stats, including private repos.

Requires GH_STATS_TOKEN, a GitHub token with permission to read the user's
private repositories and profile contributions. Never outputs repository names.
"""

import html
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

GRAPHQL_URL = "https://api.github.com/graphql"
QUERY = """
query ProfileStats {
  viewer {
    login
    private: repositories(first: 1, privacy: PRIVATE, ownerAffiliations: OWNER) {
      totalCount
    }
    public: repositories(first: 1, privacy: PUBLIC, ownerAffiliations: OWNER) {
      totalCount
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
      }
    }
  }
}
"""
OUTPUT = Path(__file__).resolve().parents[1] / "profile" / "github-activity.svg"


def fetch_stats(token: str, expected_login: str) -> dict[str, int]:
    payload = json.dumps({"query": QUERY}).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Profile-Activity-Card",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}; check the token and scopes") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not connect to the GitHub API") from exc

    if data.get("errors"):
        messages = "; ".join(error.get("message", "GraphQL error") for error in data["errors"])
        raise RuntimeError(f"GitHub GraphQL query failed: {messages}")

    viewer = data.get("data", {}).get("viewer")
    if not viewer or viewer["login"].lower() != expected_login.lower():
        raise RuntimeError("The token's GitHub account does not match the expected profile owner")

    contributions = viewer["contributionsCollection"]
    return {
        "private": viewer["private"]["totalCount"],
        "public": viewer["public"]["totalCount"],
        "commits": contributions["totalCommitContributions"],
        "contributions": contributions["contributionCalendar"]["totalContributions"],
    }


def render_svg(stats: dict[str, int]) -> str:
    items = [
        ("Private repositories", stats["private"]),
        ("Public repositories", stats["public"]),
        ("Commit contributions", stats["commits"]),
        ("All contributions", stats["contributions"]),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="780" height="185" viewBox="0 0 780 185" role="img" aria-label="GitHub profile repository and contribution counts">',
        '<rect x="1" y="1" width="778" height="183" rx="12" fill="#0d1117" stroke="#30363d"/>',
        '<text x="28" y="35" font-family="Arial, Helvetica, sans-serif" font-size="19" font-weight="600" fill="#f0f6fc">GitHub overview</text>',
        '<text x="752" y="35" text-anchor="end" font-family="Arial, Helvetica, sans-serif" font-size="12" fill="#8b949e">Rolling 12 months for contributions</text>',
        '<line x1="28" y1="51" x2="752" y2="51" stroke="#30363d"/>',
    ]
    for index, (label, value) in enumerate(items):
        x = 28 + index * 186
        if index:
            parts.append(f'<line x1="{x - 15}" y1="70" x2="{x - 15}" y2="145" stroke="#30363d"/>')
        parts.extend(
            [
                f'<text x="{x}" y="103" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="600" fill="#f0f6fc">{value:,}</text>',
                f'<text x="{x}" y="130" font-family="Arial, Helvetica, sans-serif" font-size="13" fill="#a5adb8">{html.escape(label)}</text>',
            ]
        )
    parts.append('<text x="28" y="163" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#8b949e">Private repositories are counted, not identified. Commits are GitHub contribution-counted commits.</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main() -> None:
    token = os.environ.get("GH_STATS_TOKEN", "").strip()
    login = os.environ.get("GH_LOGIN", "usman-cs").strip()
    if not token:
        raise SystemExit("Missing GH_STATS_TOKEN. Add the PROFILE_STATS_TOKEN Actions secret.")
    stats = fetch_stats(token, login)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_svg(stats), encoding="utf-8")
    print("Updated aggregate GitHub statistics SVG (no private repository details printed).")


if __name__ == "__main__":
    main()
