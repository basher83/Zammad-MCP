# mypy: ignore-errors
# ruff: noqa: PLR2004
"""Regression tests for the Zammad-MCP issue digest collector."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("collect_issue_digest.py")
SPEC = importlib.util.spec_from_file_location("collect_issue_digest", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load collector from {SCRIPT_PATH}")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def utc(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def check_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def check_is(actual, expected) -> None:
    if actual is not expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def test_parse_duration_aliases_and_units() -> None:
    check_equal(collector.parse_duration_hours("past week"), 168.0)
    check_equal(collector.parse_duration_hours("48h"), 48.0)
    check_equal(collector.parse_duration_hours("2d"), 48.0)
    check_equal(collector.parse_duration_hours("1w"), 168.0)


def test_normalize_requested_labels_deduplicates_and_supports_all_labels() -> None:
    labels, all_labels = collector.normalize_requested_labels(["area:python,area:ci-cd", "AREA:PYTHON"])

    check_equal(labels, ["area:python", "area:ci-cd"])
    check_is(all_labels, False)

    labels, all_labels = collector.normalize_requested_labels(["all", "labels"])

    check_equal(labels, [])
    check_is(all_labels, True)


def test_build_search_queries_pairs_owner_labels_with_kind_labels() -> None:
    queries = collector.build_search_queries(
        "basher83/Zammad-MCP",
        ["area:python"],
        utc(2026, 5, 1),
    )

    check_equal(len(queries), len(collector.QUALIFYING_KIND_LABELS))
    check_equal(queries[0], "repo:basher83/Zammad-MCP is:issue updated:>=2026-05-01 label:area:python label:type:bug")
    check_equal(
        queries[-1],
        "repo:basher83/Zammad-MCP is:issue updated:>=2026-05-01 label:area:python label:dependencies",
    )


def test_build_search_queries_all_labels_uses_kind_labels_only() -> None:
    queries = collector.build_search_queries(
        "basher83/Zammad-MCP",
        ["area:python"],
        utc(2026, 5, 1),
        all_labels=True,
    )

    check_equal(len(queries), 1)
    check_equal(queries[0], "repo:basher83/Zammad-MCP is:issue updated:>=2026-05-01")
    check(all("area:python" not in query for query in queries), "all-labels mode should not add owner labels")


def test_area_labels_keeps_repo_owner_labels_and_excludes_kind_or_legacy_labels() -> None:
    labels = [
        "type:bug",
        "area:python",
        "bot:renovate",
        "dependencies",
        "renovate",
        "python:uv",
        "🏷️ auto-labeled",
    ]

    check_equal(collector.area_labels(labels), ["area:python", "bot:renovate"])


def test_title_cleaning_matches_repo_dependency_and_prefix_conventions() -> None:
    check_equal(
        collector.clean_title_for_description("chore(deps): bump protobuf from 4.25.9 to 5.29.6"),
        "Dependency update: protobuf from 4.25.9 to 5.29.6",
    )
    check_equal(collector.clean_title_for_description("Zammad-MCP: Add webhook support"), "Add webhook support")


def test_attention_thresholds_scale_with_digest_window() -> None:
    thresholds = collector.attention_thresholds_for_window(168)

    check_equal(thresholds["elevated"], 4)
    check_equal(thresholds["very_high"], 8)
    check_equal(collector.attention_marker_for(3, thresholds), "")
    check_equal(collector.attention_marker_for(4, thresholds), "🔥")
    check_equal(collector.attention_marker_for(8, thresholds), "🔥🔥")


def test_all_labels_mode_keeps_unclassified_issues() -> None:
    issue = {
        "number": 43,
        "title": "Zammad-MCP: HTTP transport failure",
        "state": "open",
        "html_url": "https://github.com/basher83/Zammad-MCP/issues/43",
        "created_at": "2026-05-02T10:00:00Z",
        "updated_at": "2026-05-02T12:00:00Z",
        "body": "Transport fails in some clients.",
        "comments": 0,
        "user": {"login": "zammad-user"},
        "labels": [],
        "reactions": {"total_count": 0},
    }

    summary = collector.summarize_issue(
        issue,
        comments=[],
        requested_labels=[],
        since=utc(2026, 5, 2),
        until=utc(2026, 5, 3),
        body_chars=200,
        comment_chars=200,
        all_labels=True,
    )

    check(summary is not None, "all-labels mode should keep unlabeled repo issues")
    check_equal(summary["kind_labels"], ["unclassified"])
    check_equal(summary["owner_labels"], ["unlabeled"])


def test_summarize_issue_filters_to_requested_repo_labels() -> None:
    issue = {
        "number": 42,
        "title": "Zammad-MCP: Login failure",
        "state": "open",
        "html_url": "https://github.com/basher83/Zammad-MCP/issues/42",
        "created_at": "2026-05-02T10:00:00Z",
        "updated_at": "2026-05-02T12:00:00Z",
        "body": "Users cannot authenticate with token auth.",
        "comments": 0,
        "user": {"login": "zammad-user"},
        "labels": [{"name": "type:bug"}, {"name": "area:python"}],
        "reactions": {"total_count": 0},
    }

    summary = collector.summarize_issue(
        issue,
        comments=[],
        requested_labels=["area:python"],
        since=utc(2026, 5, 2),
        until=utc(2026, 5, 3),
        body_chars=200,
        comment_chars=200,
        comments_hydration={
            "fetched": 0,
            "total": 0,
            "since": "2026-05-02T00:00:00Z",
            "truncated": False,
            "max_pages": 3,
            "fetch_all_comments": False,
        },
    )

    check(summary is not None, "issue should be summarized")
    check_equal(summary["number"], 42)
    check_equal(summary["description"], "Login failure")
    check_equal(summary["owner_labels"], ["area:python"])
    check_equal(summary["kind_labels"], ["type:bug"])
    check_equal(summary["user_interactions"], 1)
