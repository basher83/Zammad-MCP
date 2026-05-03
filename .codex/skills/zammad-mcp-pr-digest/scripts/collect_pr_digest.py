#!/usr/bin/env python3
# mypy: ignore-errors
# ruff: noqa: PLR2004
"""Collect recent Zammad-MCP pull request activity for maintainer digests."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILLS_DIR = Path(__file__).resolve().parents[2]
COMMON_DIR = SKILLS_DIR / "zammad-mcp-issue-digest" / "scripts"
sys.path.insert(0, str(COMMON_DIR))

from triage_common import (  # noqa: E402
    DEFAULT_REPO,
    GhCommandError,
    classify_pr_payload,
    days_since,
    format_timestamp,
    gh_json,
    resolve_window,
)

PR_LIST_FIELDS = (
    "number,title,body,state,author,labels,comments,createdAt,updatedAt,closedAt,mergedAt,"
    "isDraft,reviewDecision,headRefName,baseRefName,url,mergeable,statusCheckRollup,files"
)
SCRIPT_VERSION = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect recent Zammad-MCP PR activity.")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--window", default="30d", help='Lookback duration such as "30d" or "365d"')
    parser.add_argument("--window-hours", type=float, help="Lookback window in hours")
    parser.add_argument("--since", help="UTC ISO timestamp override for window start")
    parser.add_argument("--until", help="UTC ISO timestamp override for window end")
    parser.add_argument("--limit-prs", type=int, default=250)
    return parser.parse_args()


def git_head() -> str | None:
    try:
        git_proc = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return git_proc.stdout.strip() or None


def fetch_prs(repo: str, since: datetime, limit: int) -> list[dict[str, Any]]:
    since_date = since.date().isoformat()
    payload = gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            str(limit),
            "--search",
            f"updated:>={since_date}",
            "--json",
            PR_LIST_FIELDS,
        ]
    )
    if not isinstance(payload, list):
        raise GhCommandError("Unexpected PR list payload")
    return [item for item in payload if isinstance(item, dict)]


def pr_state(pr: dict[str, Any]) -> str:
    if pr.get("mergedAt"):
        return "merged"
    return str(pr.get("state") or "").casefold()


def digest_row(pr: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    state = pr_state(pr)
    updated_days = days_since(str(pr.get("updatedAt") or ""))
    attention = decision.get("attention") == "owner"
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "ref_markdown": f"[#{pr.get('number')}]({pr.get('url')})",
        "state": state,
        "author": (pr.get("author") or {}).get("login"),
        "labels": decision.get("labels", []),
        "attention": attention,
        "attention_marker": "owner" if attention else "",
        "updated_days_ago": updated_days,
        "state_summary": decision.get("state_summary", {}),
        "reasons": decision.get("reasons", []),
    }


def collect_digest(args: argparse.Namespace) -> dict[str, Any]:
    since, until = resolve_window(args.window, args.window_hours, args.since, args.until)
    prs = fetch_prs(args.repo, since, args.limit_prs)
    decisions = []
    rows = []
    for pr in prs:
        decision = classify_pr_payload(pr).to_json()
        decisions.append(decision)
        rows.append(digest_row(pr, decision))

    rows.sort(
        key=lambda row: (
            row["attention"],
            row["state"] == "open",
            row["updated_days_ago"] is not None and -row["updated_days_ago"],
            int(row["number"] or 0),
        ),
        reverse=True,
    )
    bot_rows = [row for row in rows if row["state_summary"].get("author_type") == "bot"]
    human_rows = [row for row in rows if row["state_summary"].get("author_type") == "human"]
    dependabot_policy_drift = [
        row for row in rows if "bot:dependabot" in row["labels"] and row["state"] in {"open", "closed"}
    ]
    renovate_rows = [row for row in rows if "bot:renovate" in row["labels"]]

    return {
        "generated_at": format_timestamp(datetime.now(timezone.utc)),
        "source": {
            "repo": args.repo,
            "skill": "zammad-mcp-pr-digest",
            "script_version": SCRIPT_VERSION,
            "git_head": git_head(),
        },
        "window": {
            "since": format_timestamp(since),
            "until": format_timestamp(until),
            "hours": round((until - since).total_seconds() / 3600, 3),
        },
        "totals": {
            "candidate_prs": len(prs),
            "open": sum(1 for pr in prs if pr_state(pr) == "open"),
            "merged": sum(1 for pr in prs if pr_state(pr) == "merged"),
            "closed_unmerged": sum(1 for pr in prs if pr_state(pr) == "closed"),
            "human_authored": len(human_rows),
            "bot_authored": len(bot_rows),
            "renovate_prs": len(renovate_rows),
            "dependabot_policy_drift": len(dependabot_policy_drift),
            "owner_attention": sum(1 for row in rows if row["attention"]),
        },
        "owner_attention": [row for row in rows if row["attention"]],
        "dependency_policy_drift": dependabot_policy_drift,
        "renovate_summary": {
            "count": len(renovate_rows),
            "open": sum(1 for row in renovate_rows if row["state"] == "open"),
            "merged": sum(1 for row in renovate_rows if row["state"] == "merged"),
            "closed_unmerged": sum(1 for row in renovate_rows if row["state"] == "closed"),
        },
        "digest_rows": rows[:20],
        "pull_requests": rows,
        "decisions": decisions,
    }


def main() -> int:
    args = parse_args()
    try:
        digest = collect_digest(args)
    except (GhCommandError, RuntimeError, ValueError) as err:
        sys.stderr.write(f"collect_pr_digest.py error: {err}\n")
        return 1
    sys.stdout.write(json.dumps(digest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
