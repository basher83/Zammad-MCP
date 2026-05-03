# mypy: ignore-errors
# ruff: noqa: PLR2004
"""Tests for Zammad-MCP issue triage automation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(SCRIPT_DIR))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


triage_common = load_module("triage_common", SCRIPT_DIR / "triage_common.py")
triage_issue = load_module("triage_issue", SCRIPT_DIR / "triage_issue.py")
post_triage_digest = load_module("post_triage_digest", SCRIPT_DIR / "post_triage_digest.py")


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def check_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def issue(number: int, title: str, body: str = "", state: str = "OPEN", author: str = "Erudition", labels=None):
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "author": {"login": author, "is_bot": author.startswith("app/")},
        "labels": [{"name": label} for label in (labels or [])],
        "comments": [],
        "url": f"https://github.com/basher83/Zammad-MCP/issues/{number}",
    }


def test_issue_212_schema_bug_gets_owner_review_and_duplicate_candidate() -> None:
    current = issue(
        212,
        "Flatten tool `params` into `arguments` to fix arg/param validation failures",
        "Pydantic params nesting blocks normal agent tool calls.",
        labels=["type:bug"],
    )
    pool = [
        issue(201, "Make all constants case-insensitive if they can be", "Enum validation makes agents fail."),
        issue(198, "zammad knowledgebase", "Create and parse knowledgebase articles."),
    ]

    decision = triage_common.classify_issue_payload(current, duplicate_pool=pool).to_json()

    check("type:bug" in decision["labels"], "schema issue should be a bug")
    check("area:mcp-tools" in decision["labels"], "schema issue should be mcp-tools")
    check("needs:owner-review" in decision["labels"], "schema issue needs owner review")
    check("needs:duplicate-review" in decision["labels"], "schema issue should surface duplicate review")
    check_equal(decision["duplicate_candidates"][0]["number"], 201)


def test_issue_201_case_normalization_gets_tool_bug_labels() -> None:
    current = issue(
        201,
        "Make all constants case-insensitive if they can be",
        "Enum validation rejects MARKDOWN when agents pass the obvious constant name.",
    )

    decision = triage_common.classify_issue_payload(current).to_json()

    check("type:bug" in decision["labels"], "case normalization should be a bug")
    check("area:mcp-tools" in decision["labels"], "case normalization should be mcp-tools")


def test_issue_198_knowledgebase_gets_feature_and_zammad_api_labels() -> None:
    current = issue(
        198,
        "zammad knowledgebase",
        "It would be great to retrieve, search, and create knowledgebase articles via MCP.",
        author="snizzleorg",
    )

    decision = triage_common.classify_issue_payload(current).to_json()

    check("type:feature" in decision["labels"], "knowledgebase issue should be a feature")
    check("area:zammad-api" in decision["labels"], "knowledgebase issue should be zammad API coverage")


def test_issue_3_dependency_dashboard_gets_renovate_labels() -> None:
    current = issue(
        3,
        "Dependency Dashboard",
        "This issue lists Renovate updates and detected dependencies.",
        author="app/renovate",
    )

    decision = triage_common.classify_issue_payload(current).to_json()

    check("dependencies" in decision["labels"], "dashboard should be dependency-labeled")
    check("bot:renovate" in decision["labels"], "dashboard should be Renovate-labeled")


def test_invalid_llm_json_falls_back_to_deterministic_labels(tmp_path: Path) -> None:
    bad_output = tmp_path / "bad.json"
    bad_output.write_text("{not json")

    payload = triage_common.load_optional_json(str(bad_output))
    decision = triage_common.classify_issue_payload(
        issue(201, "Make all constants case-insensitive if they can be", "Enum validation rejects MARKDOWN."),
        llm_payload=payload,
    ).to_json()

    check_equal(payload, None)
    check("type:bug" in decision["labels"], "deterministic fallback should still label")


def test_run_gh_timeout_raises_clear_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise triage_common.subprocess.TimeoutExpired(cmd=kwargs.get("args") or args[0], timeout=kwargs.get("timeout"))

    monkeypatch.setattr(triage_common.subprocess, "run", fake_run)

    try:
        triage_common.run_gh(["issue", "list"], timeout=0.01)
    except triage_common.GhCommandError as err:
        check("timed out" in str(err), "timeout should be surfaced as GhCommandError")
    else:
        raise AssertionError("run_gh should raise GhCommandError on timeout")


def test_digest_posts_when_dependency_policy_drift_rows_exist() -> None:
    issue_digest = {"totals": {}, "digest_rows": []}
    pr_digest = {
        "totals": {},
        "owner_attention": [],
        "digest_rows": [],
        "dependency_policy_drift": [{"number": 252}],
    }

    check(post_triage_digest.should_post(issue_digest, pr_digest), "dependency drift rows should trigger digest post")


def test_issue_single_dry_run_uses_mocked_gh_payload(monkeypatch, capsys) -> None:
    payloads = {
        "view": issue(212, "Flatten tool `params` into `arguments`", "Pydantic validation fails.", labels=["type:bug"]),
        "list": [issue(201, "Make all constants case-insensitive", "Enum validation fails.")],
    }

    def fake_gh_json(args):
        if args[0:2] == ["issue", "view"]:
            return payloads["view"]
        if args[0:2] == ["issue", "list"]:
            return payloads["list"]
        raise AssertionError(f"Unexpected gh args: {args}")

    monkeypatch.setattr(triage_issue, "gh_json", fake_gh_json)
    monkeypatch.setattr(sys, "argv", ["triage_issue.py", "--issue", "212", "--dry-run", "--json"])

    code = triage_issue.main()
    captured = json.loads(capsys.readouterr().out)

    check_equal(code, 0)
    check_equal(captured["number"], 212)
    check(captured["applied"] is False, "dry-run should not apply")
    check("area:mcp-tools" in captured["labels"], "mocked dry-run should classify")


def test_issue_backfill_uses_mocked_open_issue_payloads(monkeypatch, capsys) -> None:
    payloads = [
        issue(212, "Flatten tool `params` into `arguments`", "Pydantic validation fails.", labels=["type:bug"]),
        issue(198, "zammad knowledgebase", "Add knowledgebase support."),
    ]

    def fake_gh_json(args):
        if args[0:2] == ["issue", "list"]:
            return payloads
        raise AssertionError(f"Unexpected gh args: {args}")

    monkeypatch.setattr(triage_issue, "gh_json", fake_gh_json)
    monkeypatch.setattr(sys, "argv", ["triage_issue.py", "--backfill", "--state", "open", "--dry-run", "--json"])

    code = triage_issue.main()
    captured = json.loads(capsys.readouterr().out)

    check_equal(code, 0)
    check_equal(captured["kind"], "issue_backfill")
    check_equal(len(captured["results"]), 2)
    check(captured["applied"] is False, "backfill dry-run should not apply")


def test_issue_triage_workflow_uses_labels_only_automation() -> None:
    workflow = (REPO_ROOT / ".github/workflows/issue-triage.yml").read_text()

    check("issues:" in workflow, "issue workflow should be issue-event driven")
    check("workflow_dispatch:" in workflow, "issue workflow should support manual dry-run dispatch")
    check("default: false" in workflow, "manual issue triage should default to dry-run")
    check("inputs.apply || true" not in workflow, "explicit manual dry-run should not be coerced to apply")
    check("issue-context.json" not in workflow, "issue workflow should not fetch unused context artifacts")
    check("CODEX_OPENAI_API_KEY" not in workflow, "issue workflow should not expose LLM secrets in label job")
    check("openai/codex-action" not in workflow, "issue workflow should be deterministic-only in v1")
    check("triage_issue.py" in workflow, "issue workflow should call the issue triage CLI")
    check("--llm-output" not in workflow, "issue workflow should not depend on LLM output artifacts")
    check("gh issue comment" not in workflow, "issue workflow should not comment on source issues")
