#!/usr/bin/env python3
# mypy: ignore-errors
"""Triage Zammad-MCP GitHub pull requests and apply controlled labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SKILLS_DIR = Path(__file__).resolve().parents[2]
COMMON_DIR = SKILLS_DIR / "zammad-mcp-issue-digest" / "scripts"
sys.path.insert(0, str(COMMON_DIR))

from triage_common import (  # noqa: E402
    DEFAULT_REPO,
    GhCommandError,
    apply_labels,
    classify_pr_payload,
    gh_json,
    load_optional_json,
)

PR_FIELDS = (
    "number,title,body,state,author,labels,comments,createdAt,updatedAt,closedAt,mergedAt,"
    "isDraft,reviewDecision,headRefName,baseRefName,url,mergeable,statusCheckRollup,files"
)
PR_LIST_FIELDS = (
    "number,title,body,state,author,labels,comments,createdAt,updatedAt,closedAt,mergedAt,"
    "isDraft,reviewDecision,headRefName,baseRefName,url,mergeable,statusCheckRollup,files"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Zammad-MCP PR triage labels.")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--pr", type=int, help="Pull request number to triage")
    target.add_argument("--backfill", action="store_true", help="Triage multiple PRs")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Do not apply labels")
    mode.add_argument("--apply", action="store_true", help="Apply labels through gh")
    parser.add_argument("--state", choices=["open", "closed", "merged", "all"], default="open")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--changed-files", help="Optional newline-delimited changed-files path")
    parser.add_argument("--llm-output", help="Optional Codex/LLM JSON output with a labels array")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    return parser.parse_args()


def read_changed_files(path: str | None) -> list[str] | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    return [line.strip() for line in candidate.read_text().splitlines() if line.strip()]


def fetch_pr(repo: str, number: int) -> dict[str, Any]:
    payload = gh_json(["pr", "view", str(number), "--repo", repo, "--json", PR_FIELDS])
    if not isinstance(payload, dict):
        raise GhCommandError(f"Unexpected PR payload for #{number}")
    return payload


def fetch_pr_list(repo: str, state: str, limit: int) -> list[dict[str, Any]]:
    payload = gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            PR_LIST_FIELDS,
        ]
    )
    if not isinstance(payload, list):
        raise GhCommandError("Unexpected PR list payload")
    return [item for item in payload if isinstance(item, dict)]


def process_pr(
    pr: dict[str, Any],
    *,
    repo: str,
    apply: bool,
    changed_files: list[str] | None = None,
    llm_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = classify_pr_payload(pr, changed_files=changed_files, llm_payload=llm_payload)
    if apply:
        apply_labels(repo, decision.number, decision.labels, kind="pull_request")
    out = decision.to_json()
    out["applied"] = bool(apply)
    out["url"] = pr.get("url")
    return out


def output_payload(payload: dict[str, Any], *, json_only: bool) -> None:
    if json_only:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return
    if payload.get("mode") == "backfill":
        count = len(payload.get("results") or [])
        sys.stdout.write(f"Triage decisions for {count} PRs:\n")
        for item in payload.get("results") or []:
            sys.stdout.write(f"- #{item['number']}: {', '.join(item['labels'])}\n")
        return
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    apply = bool(args.apply)
    if args.backfill and (args.llm_output or args.changed_files):
        sys.stderr.write("triage_pr.py error: --backfill does not support --llm-output or --changed-files\n")
        return 1
    llm_payload = load_optional_json(args.llm_output)
    changed_files = read_changed_files(args.changed_files)
    try:
        if args.pr:
            pr = fetch_pr(args.repo, args.pr)
            payload = process_pr(
                pr,
                repo=args.repo,
                apply=apply,
                changed_files=changed_files,
                llm_payload=llm_payload,
            )
        else:
            prs = fetch_pr_list(args.repo, args.state, args.limit)
            payload = {
                "repo": args.repo,
                "kind": "pull_request_backfill",
                "mode": "backfill",
                "state": args.state,
                "applied": apply,
                "results": [process_pr(pr, repo=args.repo, apply=apply) for pr in prs],
            }
    except (GhCommandError, RuntimeError, ValueError) as err:
        sys.stderr.write(f"triage_pr.py error: {err}\n")
        return 1

    output_payload(payload, json_only=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
