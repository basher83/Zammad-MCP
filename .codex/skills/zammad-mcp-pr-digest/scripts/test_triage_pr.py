# mypy: ignore-errors
"""Tests for Zammad-MCP PR triage automation."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPT_DIR.parents[1]
COMMON_DIR = SKILLS_DIR / "zammad-mcp-issue-digest" / "scripts"
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(COMMON_DIR))
sys.path.insert(0, str(SCRIPT_DIR))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


triage_common = load_module("triage_common", COMMON_DIR / "triage_common.py")
triage_pr = load_module("triage_pr", SCRIPT_DIR / "triage_pr.py")
collect_pr_digest = load_module("collect_pr_digest", SCRIPT_DIR / "collect_pr_digest.py")


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def check_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def pr(number: int, title: str, author: str, body: str = "", state: str = "OPEN", labels=None, files=None):
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "author": {"login": author, "is_bot": author.startswith("app/")},
        "labels": [{"name": label} for label in (labels or [])],
        "files": [{"path": path} for path in (files or [])],
        "reviewDecision": "",
        "mergeable": "UNKNOWN",
        "url": f"https://github.com/basher83/Zammad-MCP/pull/{number}",
    }


def test_pr_200_open_human_knowledgebase_gets_owner_review() -> None:
    current = pr(
        200,
        "Feature/knowledge base crud",
        "snizzleorg",
        "Add knowledge base CRUD support.",
        files=["mcp_zammad/server.py", "tests/test_server.py"],
    )

    decision = triage_common.classify_pr_payload(current).to_json()

    check("type:feature" in decision["labels"], "knowledgebase PR should be a feature")
    check("area:zammad-api" in decision["labels"], "knowledgebase PR should be zammad API")
    check("needs:owner-review" in decision["labels"], "open human PR should need owner review")
    check_equal(decision["state_summary"]["author_type"], "human")


def test_renovate_docker_pr_gets_dependency_bot_and_docker_labels() -> None:
    current = pr(
        249,
        "chore(deps): Update ghcr.io/astral-sh/uv:latest Docker digest to 3b7b60a",
        "app/renovate",
        files=["Dockerfile"],
    )

    decision = triage_common.classify_pr_payload(current).to_json()

    check("dependencies" in decision["labels"], "Renovate PR should be dependency-labeled")
    check("bot:renovate" in decision["labels"], "Renovate PR should be bot-labeled")
    check("docker" in decision["labels"], "Docker digest PR should get docker label")


def test_renovate_github_actions_pr_gets_github_actions_label() -> None:
    current = pr(
        254,
        "chore(deps): Update GitHub Actions",
        "app/renovate",
        files=[".github/workflows/tests.yml"],
    )

    decision = triage_common.classify_pr_payload(current).to_json()

    check("dependencies" in decision["labels"], "Renovate Actions PR should be dependency-labeled")
    check("bot:renovate" in decision["labels"], "Renovate Actions PR should be bot-labeled")
    check("github-actions" in decision["labels"], "Actions PR should get github-actions label")


def test_dependabot_pr_gets_policy_drift_signal() -> None:
    current = pr(
        252,
        "chore(deps): bump protobuf from 4.25.9 to 5.29.6 in the uv group across 1 directory",
        "app/dependabot",
        files=["uv.lock"],
    )

    decision = triage_common.classify_pr_payload(current).to_json()

    check("dependencies" in decision["labels"], "Dependabot PR should be dependency-labeled")
    check("bot:dependabot" in decision["labels"], "Dependabot PR should be bot-labeled")
    check("needs:owner-review" in decision["labels"], "Dependabot routine PR should flag policy drift")
    check_equal(decision["attention"], "owner")


def test_review_required_pr_state_maps_to_needed_attention() -> None:
    current = pr(300, "Improve ticket search", "snizzleorg", "Add better ticket search.")
    current["reviewDecision"] = "REVIEW_REQUIRED"

    decision = triage_common.classify_pr_payload(current).to_json()

    check_equal(decision["state_summary"]["review"], "needed")
    check_equal(decision["attention"], "owner")


def test_pr_single_dry_run_uses_mocked_gh_payload(monkeypatch, capsys, tmp_path: Path) -> None:
    changed_files = tmp_path / "changed-files.txt"
    changed_files.write_text("mcp_zammad/server.py\n")

    def fake_gh_json(args):
        if args[0:2] == ["pr", "view"]:
            return pr(200, "Feature/knowledge base crud", "snizzleorg", "Add knowledgebase CRUD.")
        raise AssertionError(f"Unexpected gh args: {args}")

    monkeypatch.setattr(triage_pr, "gh_json", fake_gh_json)
    monkeypatch.setattr(
        sys,
        "argv",
        ["triage_pr.py", "--pr", "200", "--changed-files", str(changed_files), "--dry-run", "--json"],
    )

    code = triage_pr.main()
    captured = json.loads(capsys.readouterr().out)

    check_equal(code, 0)
    check_equal(captured["number"], 200)
    check(captured["applied"] is False, "dry-run should not apply")
    check("area:zammad-api" in captured["labels"], "mocked PR should classify")


def test_pr_backfill_uses_mocked_open_pr_payloads(monkeypatch, capsys) -> None:
    payloads = [
        pr(200, "Feature/knowledge base crud", "snizzleorg", "Add knowledgebase CRUD."),
        pr(249, "chore(deps): Update ghcr.io/astral-sh/uv Docker digest", "app/renovate", files=["Dockerfile"]),
    ]

    def fake_gh_json(args):
        if args[0:2] == ["pr", "list"]:
            return payloads
        raise AssertionError(f"Unexpected gh args: {args}")

    monkeypatch.setattr(triage_pr, "gh_json", fake_gh_json)
    monkeypatch.setattr(sys, "argv", ["triage_pr.py", "--backfill", "--state", "open", "--dry-run", "--json"])

    code = triage_pr.main()
    captured = json.loads(capsys.readouterr().out)

    check_equal(code, 0)
    check_equal(captured["kind"], "pull_request_backfill")
    check_equal(len(captured["results"]), 2)
    check(captured["applied"] is False, "backfill dry-run should not apply")


def test_pr_backfill_rejects_single_pr_context_inputs(monkeypatch, capsys, tmp_path: Path) -> None:
    changed_files = tmp_path / "changed-files.txt"
    changed_files.write_text("mcp_zammad/server.py\n")

    monkeypatch.setattr(
        sys,
        "argv",
        ["triage_pr.py", "--backfill", "--changed-files", str(changed_files), "--dry-run", "--json"],
    )

    code = triage_pr.main()
    captured = capsys.readouterr()

    check_equal(code, 1)
    check("--backfill does not support --llm-output or --changed-files" in captured.err, "should fail clearly")


def test_collect_pr_digest_filters_exact_updated_window(monkeypatch) -> None:
    payloads = [
        {"number": 1, "updatedAt": "2026-05-01T11:59:59Z"},
        {"number": 2, "updatedAt": "2026-05-01T12:00:00Z"},
        {"number": 3, "updatedAt": "2026-05-02T12:00:00Z"},
        {"number": 4, "updatedAt": "2026-05-02T12:00:01Z"},
        "not-a-dict",
    ]

    def fake_gh_json(args):
        check(
            "updated:2026-05-01T12:00:00Z..2026-05-02T12:00:00Z" in args,
            "search should bound the broad query by exact timestamps",
        )
        return payloads

    monkeypatch.setattr(collect_pr_digest, "gh_json", fake_gh_json)

    rows = collect_pr_digest.fetch_prs(
        "basher83/Zammad-MCP",
        datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
        datetime(2026, 5, 2, 12, tzinfo=timezone.utc),
        50,
    )

    check_equal([row["number"] for row in rows], [2, 3])


def test_collect_pr_digest_fails_when_limit_may_truncate_window(monkeypatch) -> None:
    payloads = [{"number": 1, "updatedAt": "2026-05-01T12:00:00Z"}]

    monkeypatch.setattr(collect_pr_digest, "gh_json", lambda _args: payloads)

    try:
        collect_pr_digest.fetch_prs(
            "basher83/Zammad-MCP",
            datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
            datetime(2026, 5, 2, 12, tzinfo=timezone.utc),
            1,
        )
    except collect_pr_digest.GhCommandError as err:
        check("reached --limit 1" in str(err), "limit truncation should fail clearly")
    else:
        raise AssertionError("fetch_prs should fail when gh results reach the requested limit")


def test_pr_triage_workflow_collects_fork_diff_without_running_pr_code() -> None:
    workflow = (REPO_ROOT / ".github/workflows/pr-triage.yml").read_text()

    check((REPO_ROOT / ".github/workflows/pr-triage.yml").exists(), "workflow path should resolve from repo root")
    check("pull_request_target:" in workflow, "PR workflow should use pull_request_target for label permissions")
    check("git fetch --no-tags" in workflow, "PR workflow should fetch fork heads for diff metadata")
    check("git diff --name-only" in workflow, "PR workflow should collect changed paths without running PR code")
    check('git diff "$diff_base" "$head_sha"' not in workflow, "PR workflow should not export full patches")
    check("changes.diff" not in workflow, "PR workflow should not pass full diffs to triage")
    check("CODEX_OPENAI_API_KEY" not in workflow, "PR workflow should not expose LLM secrets in label job")
    check("openai/codex-action" not in workflow, "PR workflow should be deterministic-only in v1")
    check("--llm-output" not in workflow, "PR workflow should not depend on LLM output artifacts")
    check("default: false" in workflow, "manual PR triage should default to dry-run")
    check("inputs.apply || true" not in workflow, "explicit manual dry-run should not be coerced to apply")
    check('INPUT_APPLY="${INPUT_APPLY:-true}"' in workflow, "PR workflow should default missing apply input in shell")
    check("pr-context.json" not in workflow, "PR workflow should not fetch unused context artifacts")
    check("gh pr comment" not in workflow, "PR workflow should not comment on source PRs")
