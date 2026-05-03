#!/usr/bin/env python3
# mypy: ignore-errors
# ruff: noqa: PLR2004
"""Post the combined Zammad-MCP issue and PR digest to a tracking issue."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from triage_common import DEFAULT_REPO, TRACKING_ISSUE_TITLE, GhCommandError, ensure_labels, gh_json, run_gh


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post a combined Zammad-MCP triage digest.")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--issue-digest", required=True)
    parser.add_argument("--pr-digest", required=True)
    parser.add_argument("--title", default=TRACKING_ISSUE_TITLE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def load_json_file(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def issue_attention_rows(issue_digest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = issue_digest.get("digest_rows") or []
    return [
        row
        for row in rows
        if row.get("marker")
        or str(row.get("state") or "").casefold() == "open"
        or int(row.get("interactions") or 0) > 0
    ][:10]


def pr_attention_rows(pr_digest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = pr_digest.get("owner_attention") or []
    if rows:
        return rows[:10]
    return [row for row in pr_digest.get("digest_rows") or [] if row.get("state") == "open"][:10]


def should_post(issue_digest: dict[str, Any], pr_digest: dict[str, Any]) -> bool:
    issue_totals = issue_digest.get("totals") or {}
    pr_totals = pr_digest.get("totals") or {}
    return bool(
        issue_attention_rows(issue_digest)
        or pr_attention_rows(pr_digest)
        or int(issue_totals.get("new_issues") or 0) > 0
        or int(issue_totals.get("new_comments") or 0) > 0
        or int(pr_totals.get("owner_attention") or 0) > 0
        or int(pr_totals.get("dependency_policy_drift") or 0) > 0
        or int(pr_totals.get("dependabot_policy_drift") or 0) > 0
        or bool(pr_digest.get("dependency_policy_drift") or [])
    )


def format_issue_line(row: dict[str, Any]) -> str:
    marker = f"{row.get('marker')} " if row.get("marker") else ""
    state = str(row.get("state") or "").casefold()
    interactions = int(row.get("interactions") or 0)
    ref = row.get("ref_markdown") or f"#{row.get('number')}"
    return f"- {marker}{ref} `{state}` {row.get('description')} ({interactions} interactions)"


def format_pr_line(row: dict[str, Any]) -> str:
    state = row.get("state") or "unknown"
    labels = ", ".join(row.get("labels") or [])
    ref = row.get("ref_markdown") or f"#{row.get('number')}"
    reason = "; ".join(row.get("reasons") or []) or "PR needs maintainer review"
    return f"- {ref} `{state}` {row.get('title')} [{labels}] - {reason}"


def build_body(issue_digest: dict[str, Any], pr_digest: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    issue_totals = issue_digest.get("totals") or {}
    pr_totals = pr_digest.get("totals") or {}
    issue_rows = issue_attention_rows(issue_digest)
    pr_rows = pr_attention_rows(pr_digest)
    drift_rows = pr_digest.get("dependency_policy_drift") or []

    lines = [
        f"## Triage digest - {now}",
        "",
        "Maintainer attention summary for Zammad-MCP.",
        "",
        "### Issue activity",
        (
            f"- {issue_totals.get('included_issues', 0)} recent issues, "
            f"{issue_totals.get('new_issues', 0)} new, "
            f"{issue_totals.get('new_comments', 0)} new comments."
        ),
    ]
    if issue_rows:
        lines.append("")
        lines.extend(format_issue_line(row) for row in issue_rows)
    else:
        lines.append("- No issue-side owner attention surfaced.")

    lines.extend(
        [
            "",
            "### Pull request activity",
            (
                f"- {pr_totals.get('candidate_prs', 0)} recent PRs, "
                f"{pr_totals.get('open', 0)} open, "
                f"{pr_totals.get('merged', 0)} merged, "
                f"{pr_totals.get('closed_unmerged', 0)} closed unmerged."
            ),
        ]
    )
    if pr_rows:
        lines.append("")
        lines.extend(format_pr_line(row) for row in pr_rows)
    else:
        lines.append("- No PR-side owner attention surfaced.")

    lines.extend(["", "### Dependency automation"])
    renovate = pr_digest.get("renovate_summary") or {}
    lines.append(
        f"- Renovate: {renovate.get('count', 0)} recent PRs "
        f"({renovate.get('merged', 0)} merged, {renovate.get('open', 0)} open)."
    )
    if drift_rows:
        lines.append(f"- Dependabot policy drift: {len(drift_rows)} PRs need owner reconciliation.")
    else:
        lines.append("- No Dependabot policy drift surfaced in this window.")

    issue_source = issue_digest.get("source") or {}
    pr_source = pr_digest.get("source") or {}
    lines.extend(
        [
            "",
            "### Source",
            (
                f"- Issue collector v{issue_source.get('script_version')} "
                f"window {issue_digest.get('window', {}).get('since')} to {issue_digest.get('window', {}).get('until')}."
            ),
            (
                f"- PR collector v{pr_source.get('script_version')} "
                f"window {pr_digest.get('window', {}).get('since')} to {pr_digest.get('window', {}).get('until')}."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def find_tracking_issue(repo: str, title: str) -> int | None:
    payload = gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--search",
            f"{title} in:title",
            "--limit",
            "20",
            "--json",
            "number,title",
        ]
    )
    if not isinstance(payload, list):
        return None
    for issue in payload:
        if isinstance(issue, dict) and issue.get("title") == title:
            return int(issue.get("number") or 0)
    return None


def create_tracking_issue(repo: str, title: str) -> int:
    ensure_labels(repo, ["type:chore", "status:in-progress"])
    body = "Rolling maintainer digest for Zammad-MCP issue and pull request triage.\n"
    proc = run_gh(
        [
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--label",
            "type:chore",
            "--label",
            "status:in-progress",
            "--body-file",
            "-",
        ],
        input_text=body,
    )
    url = proc.stdout.strip().splitlines()[-1]
    match = re.search(r"/issues/(\d+)(?:\b|$)", url)
    if match is None:
        raise GhCommandError("Unable to determine created tracking issue number")
    return int(match.group(1))


def post_comment(repo: str, issue_number: int, body: str) -> None:
    run_gh(["issue", "comment", str(issue_number), "--repo", repo, "--body-file", "-"], input_text=body)


def main() -> int:
    args = parse_args()
    try:
        issue_digest = load_json_file(args.issue_digest)
        pr_digest = load_json_file(args.pr_digest)
        body = build_body(issue_digest, pr_digest)
        post = should_post(issue_digest, pr_digest)
        issue_number = None
        created = False
        if args.apply and post:
            issue_number = find_tracking_issue(args.repo, args.title)
            if issue_number is None:
                issue_number = create_tracking_issue(args.repo, args.title)
                created = True
            post_comment(args.repo, issue_number, body)
        payload = {
            "repo": args.repo,
            "title": args.title,
            "tracking_issue": issue_number,
            "created_tracking_issue": created,
            "should_post": post,
            "applied": bool(args.apply and post),
            "body": body,
        }
    except (GhCommandError, RuntimeError, TypeError, ValueError, OSError, json.JSONDecodeError) as err:
        sys.stderr.write(f"post_triage_digest.py error: {err}\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
