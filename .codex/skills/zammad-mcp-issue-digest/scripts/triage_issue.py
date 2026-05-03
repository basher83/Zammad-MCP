#!/usr/bin/env python3
# mypy: ignore-errors
# ruff: noqa: PLR2004
"""Triage Zammad-MCP GitHub issues and apply controlled labels."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from triage_common import (
    DEFAULT_REPO,
    GhCommandError,
    apply_labels,
    classify_issue_payload,
    gh_json,
    load_optional_json,
)

ISSUE_FIELDS = "number,title,body,state,author,labels,comments,createdAt,updatedAt,closedAt,url"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Zammad-MCP issue triage labels.")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--issue", type=int, help="Issue number to triage")
    target.add_argument("--backfill", action="store_true", help="Triage multiple issues")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Do not apply labels")
    mode.add_argument("--apply", action="store_true", help="Apply labels through gh")
    parser.add_argument("--state", choices=["open", "closed", "all"], default="open", help="Backfill issue state")
    parser.add_argument("--limit", type=int, default=100, help="Maximum issues to inspect in backfill/pool")
    parser.add_argument("--llm-output", help="Optional Codex/LLM JSON output with a labels array")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    return parser.parse_args()


def fetch_issue(repo: str, number: int) -> dict[str, Any]:
    payload = gh_json(["issue", "view", str(number), "--repo", repo, "--json", ISSUE_FIELDS])
    if not isinstance(payload, dict):
        raise GhCommandError(f"Unexpected issue payload for #{number}")
    return payload


def fetch_issue_pool(repo: str, state: str, limit: int) -> list[dict[str, Any]]:
    payload = gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            ISSUE_FIELDS,
        ]
    )
    if not isinstance(payload, list):
        raise GhCommandError("Unexpected issue list payload")
    return [item for item in payload if isinstance(item, dict)]


def process_issue(
    issue: dict[str, Any],
    *,
    repo: str,
    apply: bool,
    llm_payload: dict[str, Any] | None = None,
    duplicate_pool: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    decision = classify_issue_payload(issue, llm_payload=llm_payload, duplicate_pool=duplicate_pool)
    if apply:
        apply_labels(repo, decision.number, decision.labels, kind="issue")
    out = decision.to_json()
    out["applied"] = bool(apply)
    out["url"] = issue.get("url")
    return out


def output_payload(payload: dict[str, Any], *, json_only: bool) -> None:
    if json_only:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return
    if payload.get("mode") == "backfill":
        count = len(payload.get("results") or [])
        sys.stdout.write(f"Triage decisions for {count} issues:\n")
        for item in payload.get("results") or []:
            sys.stdout.write(f"- #{item['number']}: {', '.join(item['labels'])}\n")
        return
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    apply = bool(args.apply)
    llm_payload = load_optional_json(args.llm_output)
    try:
        if args.issue:
            issue = fetch_issue(args.repo, args.issue)
            duplicate_pool = fetch_issue_pool(args.repo, "all", args.limit)
            payload = process_issue(
                issue,
                repo=args.repo,
                apply=apply,
                llm_payload=llm_payload,
                duplicate_pool=duplicate_pool,
            )
        else:
            issues = fetch_issue_pool(args.repo, args.state, args.limit)
            duplicate_pool = fetch_issue_pool(args.repo, "all", args.limit)
            payload = {
                "repo": args.repo,
                "kind": "issue_backfill",
                "mode": "backfill",
                "state": args.state,
                "applied": apply,
                "results": [
                    process_issue(issue, repo=args.repo, apply=apply, duplicate_pool=duplicate_pool) for issue in issues
                ],
            }
    except (GhCommandError, RuntimeError, ValueError) as err:
        sys.stderr.write(f"triage_issue.py error: {err}\n")
        return 1

    output_payload(payload, json_only=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
