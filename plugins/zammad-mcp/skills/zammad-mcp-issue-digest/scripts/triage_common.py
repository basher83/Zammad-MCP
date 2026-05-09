#!/usr/bin/env python3
# mypy: ignore-errors
"""Shared deterministic triage helpers for Zammad-MCP issues and pull requests."""

from __future__ import annotations

import json
import math
import re
import subprocess  # nosec B404
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPO = "basher83/Zammad-MCP"
TRACKING_ISSUE_TITLE = "[triage] Zammad-MCP maintainer digest"

TYPE_LABELS = {
    "type:bug",
    "type:feature",
    "type:docs",
    "type:security",
    "type:performance",
    "type:chore",
    "dependencies",
}
AREA_LABELS = {
    "area:python",
    "area:web",
    "area:docs",
    "area:ci-cd",
    "area:security",
    "area:infra",
    "area:mcp-tools",
    "area:zammad-api",
    "area:transport",
}
WORKFLOW_LABELS = {
    "needs:owner-review",
    "needs:repro",
    "needs:info",
    "needs:duplicate-review",
    "status:backlog",
    "status:blocked",
    "status:done",
    "status:in-progress",
    "status:in-review",
    "status:ready-to-merge",
}
BOT_LABELS = {
    "bot:renovate",
    "bot:dependabot",
    "renovate",
    "docker",
    "github-actions",
    "python:uv",
    "security",
}
ALLOWED_LABELS = TYPE_LABELS | AREA_LABELS | WORKFLOW_LABELS | BOT_LABELS

LABEL_DEFINITIONS = {
    "area:mcp-tools": ("MCP tool schemas, prompts, resources, and agent-facing tool ergonomics", "3776ab"),
    "area:zammad-api": ("Zammad API coverage, ticket/article/user/knowledgebase behavior", "0e8a16"),
    "area:transport": ("MCP stdio, HTTP transport, sessions, and client initialization", "0052cc"),
    "needs:owner-review": ("Requires maintainer review or product decision", "fbca04"),
    "needs:repro": ("Needs reproduction details before implementation", "fef2c0"),
    "needs:info": ("Needs more information from the reporter", "fef2c0"),
    "needs:duplicate-review": ("Potential duplicate; maintainer should review before closing", "cfd3d7"),
    "bot:renovate": ("Automated dependency updates by Renovate", "0366d6"),
    "bot:dependabot": ("Automated dependency updates by Dependabot", "0366d6"),
    "renovate": ("Renovate dependency automation", "ededed"),
    "docker": ("Docker image, Dockerfile, or container dependency updates", "ededed"),
    "github-actions": ("GitHub Actions workflow or action dependency updates", "ededed"),
    "python:uv": ("Python uv, uv.lock, or Python package dependency updates", "2b67c6"),
    "security": ("Security advisory, vulnerability, or security-sensitive dependency update", "b60205"),
    "type:bug": ("Something is not working correctly", "d73a4a"),
    "type:feature": ("New feature or enhancement", "a2eeef"),
    "type:docs": ("Documentation or content", "0075ca"),
    "type:security": ("Security-related work", "d73a4a"),
    "type:performance": ("Performance improvements or optimizations", "fbca04"),
    "type:chore": ("Maintenance, refactor, or tooling", "5319e7"),
    "dependencies": ("Dependency updates or dependency issues", "0366d6"),
}


class GhCommandError(RuntimeError):
    pass


@dataclass
class TriageDecision:
    number: int
    kind: str
    labels: list[str]
    confidence: str
    attention: str
    reasons: list[str] = field(default_factory=list)
    duplicate_candidates: list[dict[str, Any]] = field(default_factory=list)
    state_summary: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "number": self.number,
            "kind": self.kind,
            "labels": self.labels,
            "confidence": self.confidence,
            "attention": self.attention,
            "reasons": self.reasons,
        }
        if self.duplicate_candidates:
            out["duplicate_candidates"] = self.duplicate_candidates
        else:
            out["duplicate_candidates"] = []
        if self.state_summary is not None:
            out["state_summary"] = self.state_summary
        return out


def run_gh(
    args: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
    timeout: float | None = 30.0,
) -> subprocess.CompletedProcess:
    cmd = ["gh", *args]
    try:
        proc = subprocess.run(  # nosec B603 B607
            cmd,
            input=input_text,
            check=check,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as err:
        raise GhCommandError("`gh` command not found") from err
    except subprocess.TimeoutExpired as err:
        raise GhCommandError(f"GitHub CLI command timed out after {timeout}s: {' '.join(cmd)}") from err
    except subprocess.CalledProcessError as err:
        raise GhCommandError(format_gh_error(cmd, err)) from err
    return proc


def gh_json(args: list[str]) -> Any:
    proc = run_gh(args)
    raw = proc.stdout.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise GhCommandError(f"Failed to parse JSON from gh output for {' '.join(args)}") from err


def format_gh_error(cmd: list[str], err: subprocess.CalledProcessError) -> str:
    stdout = (err.stdout or "").strip()
    stderr = (err.stderr or "").strip()
    parts = [f"GitHub CLI command failed: {' '.join(cmd)}"]
    if stdout:
        parts.append(f"stdout: {stdout}")
    if stderr:
        parts.append(f"stderr: {stderr}")
    return "\n".join(parts)


def parse_duration_hours(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().casefold().replace("_", " ")
    if not text:
        return None
    text = re.sub(r"^(past|last)\s+", "", text)
    aliases = {"day": 24.0, "24h": 24.0, "week": 168.0, "7d": 168.0, "30d": 720.0, "year": 8760.0}
    if text in aliases:
        return aliases[text]
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)", text)
    if match:
        return float(match.group(1))
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(d|day|days)", text)
    if match:
        return float(match.group(1)) * 24.0
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(w|week|weeks)", text)
    if match:
        return float(match.group(1)) * 168.0
    raise ValueError(f"Unsupported duration: {value}")


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_window(
    window: str | None, window_hours: float | None, since: str | None, until: str | None
) -> tuple[datetime, datetime]:
    end = parse_timestamp(until) or datetime.now(timezone.utc)
    start = parse_timestamp(since)
    if start is None:
        hours = parse_duration_hours(window)
        if hours is None:
            hours = window_hours or 24.0
        if hours <= 0:
            raise ValueError("window duration must be > 0")
        start = end - timedelta(hours=hours)
    if start >= end:
        raise ValueError("--since must be before --until")
    return start, end


def compact_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(limit - 3, 0)].rstrip()}..."


def extract_login(author: Any) -> str:
    if isinstance(author, dict):
        return str(author.get("login") or "")
    return str(author or "")


def author_is_bot(author: Any) -> bool:
    if isinstance(author, dict) and author.get("is_bot") is True:
        return True
    login = extract_login(author).casefold()
    return login.startswith("app/") or login.endswith("[bot]") or login in {"renovate", "dependabot"}


def label_names(item: dict[str, Any]) -> list[str]:
    names = [label.get("name") if isinstance(label, dict) else label for label in item.get("labels") or []]
    return sorted({str(name) for name in names if name}, key=str.casefold)


def comments_text(item: dict[str, Any]) -> str:
    chunks = []
    for comment in item.get("comments") or []:
        if isinstance(comment, dict):
            chunks.append(str(comment.get("body") or ""))
    return "\n".join(chunks)


def text_blob(*values: Any) -> str:
    return "\n".join(str(value or "") for value in values).casefold()


def path_blob(paths: list[str] | None) -> str:
    return "\n".join(paths or []).casefold()


def ordered_labels(labels: set[str]) -> list[str]:
    type_order = [
        "type:bug",
        "type:feature",
        "type:docs",
        "type:security",
        "type:performance",
        "type:chore",
        "dependencies",
    ]
    area_order = [
        "area:mcp-tools",
        "area:zammad-api",
        "area:transport",
        "area:security",
        "area:ci-cd",
        "area:docs",
        "area:python",
        "area:infra",
        "area:web",
    ]
    rest_order = [
        "bot:renovate",
        "bot:dependabot",
        "renovate",
        "docker",
        "github-actions",
        "python:uv",
        "security",
        "needs:owner-review",
        "needs:repro",
        "needs:info",
        "needs:duplicate-review",
    ]
    order = {label: index for index, label in enumerate([*type_order, *area_order, *rest_order])}
    return sorted(labels & ALLOWED_LABELS, key=lambda label: (order.get(label, 999), label.casefold()))


def merge_llm_labels(labels: set[str], llm_payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(llm_payload, dict):
        return []
    added = []
    raw_labels = llm_payload.get("labels")
    if not isinstance(raw_labels, list):
        return added
    for raw in raw_labels:
        label = str(raw)
        if label in ALLOWED_LABELS and label not in labels:
            labels.add(label)
            added.append(label)
    return added


def load_optional_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    raw = candidate.read_text().strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def issue_theme_keys(item: dict[str, Any]) -> set[str]:
    text = text_blob(item.get("title"), item.get("body"), comments_text(item))
    keys = set()
    if re.search(
        r"params?|arguments?|pydantic|schema|validation|enum|case[- ]?insensitive|tool[- ]?call|tool signatures?",
        text,
    ):
        keys.add("tool-call schema ergonomics")
    if re.search(r"stdio|http transport|transport corruption|session|initialized|/mcp\b|mcp endpoint", text):
        keys.add("MCP transport/runtime")
    if re.search(r"knowledge ?base|webhook|bulk|attachment|customer|tag|time_unit|zammad api|article email", text):
        keys.add("Zammad API coverage")
    if re.search(r"renovate|dependabot|dependency|python 3\.14|mcp package|codacy|github actions", text):
        keys.add("dependency governance")
    if re.search(r"security|cve|tls|certificate|token|ssrf|xss|audit|rate limiting|vulnerab", text):
        keys.add("security hardening")
    return keys


def find_duplicate_candidates(
    item: dict[str, Any],
    pool: list[dict[str, Any]] | None,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not pool:
        return []
    current_number = int(item.get("number") or 0)
    current_keys = issue_theme_keys(item)
    if not current_keys:
        return []
    candidates = []
    for other in pool:
        number = int(other.get("number") or 0)
        if not number or number == current_number:
            continue
        other_text = text_blob(other.get("title"), other.get("body"), comments_text(other))
        if author_is_bot(other.get("author") or other.get("user")) or dependency_labels(
            other_text,
            extract_login(other.get("author") or other.get("user")),
        ):
            continue
        overlap = current_keys & issue_theme_keys(other)
        if not overlap:
            continue
        state = str(other.get("state") or "").upper()
        score = len(overlap) + (2 if state == "OPEN" else 0)
        reason = f"same {sorted(overlap)[0]} theme"
        candidates.append({"number": number, "reason": reason, "_score": score})
    candidates.sort(key=lambda row: (row["_score"], row["number"]), reverse=True)
    return [{key: value for key, value in row.items() if key != "_score"} for row in candidates[:limit]]


def classify_type(text: str, existing_labels: set[str]) -> str:  # noqa: PLR0911
    if "dependencies" in existing_labels:
        return "dependencies"
    if re.search(r"security|cve|vulnerab|ssrf|xss|audit logging|rate limiting", text):
        return "type:security"
    if re.search(r"performance|optimi[sz]e|memory|slow|timeout", text):
        return "type:performance"
    if re.search(
        r"\b(fails?|failure|error|bug|crash|breaks?|broken|blocks?|cannot|incorrect|rejects?|regression|not initialized)\b",
        text,
    ):
        return "type:bug"
    if re.search(r"\b(feature|implement|add|support|knowledge ?base|webhook|bulk|enhancement)\b", text):
        return "type:feature"
    if re.search(r"docs?|readme|documentation|docstring", text):
        return "type:docs"
    if re.search(r"\b(chore|refactor|cleanup|test|workflow|renovate config|dependency dashboard)\b", text):
        return "type:chore"
    return "type:chore"


def classify_areas(text: str, changed_files: list[str] | None = None) -> set[str]:
    paths = path_blob(changed_files)
    labels = set()
    if re.search(
        r"params?|arguments?|pydantic|schema|validation|enum|case[- ]?insensitive|tool[- ]?call|tool signatures?",
        text,
    ):
        labels.add("area:mcp-tools")
    if re.search(r"knowledge ?base|webhook|bulk|attachment|customer|tag|time_unit|zammad api|article email", text):
        labels.add("area:zammad-api")
    if re.search(r"stdio|http transport|transport corruption|session|initialized|/mcp\b|mcp endpoint", text):
        labels.add("area:transport")
    if re.search(r"security|cve|tls|certificate|token|auth|ssrf|xss|audit|rate limiting|vulnerab", text):
        labels.add("area:security")
    if re.search(r"workflow|github actions|codacy|renovate|dependabot|ci|coverage|code scanning", text):
        labels.add("area:ci-cd")
    if re.search(r"\b(docs?|readme|documentation|docstring)\b", text) or re.search(r"(^|\n)docs/|readme|\.md$", paths):
        labels.add("area:docs")
    if re.search(r"python\s*(?:3|\d|version|runtime)|pyproject|uv|pip|pytest|ruff|mypy|bandit", text) or re.search(
        r"pyproject\.toml|uv\.lock", paths
    ):
        labels.add("area:python")
    if re.search(r"docker|ghcr|image|container|registry", text) or re.search(r"dockerfile|compose", paths):
        labels.add("area:infra")
    if re.search(r"web ui|http endpoint|webhook|browser|cors", text):
        labels.add("area:web")
    return labels


def dependency_labels(text: str, author_login: str) -> set[str]:
    labels = set()
    normalized_author = author_login.casefold()
    dependency_context = bool(
        re.search(r"dependency dashboard|chore\(deps\)|\bdeps?\b|bump|update dependency|renovate|dependabot", text)
        or "renovate" in normalized_author
        or "dependabot" in normalized_author
    )
    if "renovate" in normalized_author or "dependency dashboard" in text:
        labels.update({"dependencies", "bot:renovate", "renovate"})
    elif dependency_context and "renovate" in text:
        labels.update({"dependencies", "renovate"})
    if "dependabot" in normalized_author:
        labels.update({"dependencies", "bot:dependabot"})
    if dependency_context and re.search(r"docker|ghcr|container|image|dockerfile", text):
        labels.add("docker")
    if dependency_context and re.search(r"github actions|actions/|codeql|checkout|setup-|upload-artifact", text):
        labels.add("github-actions")
    if dependency_context and re.search(r"uv|pip|pyproject|python|pytest|ruff|mypy|bandit|pip-audit", text):
        labels.add("python:uv")
    if dependency_context and re.search(r"security|vulnerab|cve|\[security\]", text):
        labels.add("security")
    return labels


def classify_issue_payload(
    issue: dict[str, Any],
    *,
    llm_payload: dict[str, Any] | None = None,
    duplicate_pool: list[dict[str, Any]] | None = None,
) -> TriageDecision:
    number = int(issue.get("number") or 0)
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    state = str(issue.get("state") or "").upper()
    author_login = extract_login(issue.get("author") or issue.get("user"))
    existing = set(label_names(issue))
    text = text_blob(title, body, comments_text(issue), " ".join(existing), author_login)
    labels = set()
    reasons = []

    labels.update(dependency_labels(text, author_login))
    if labels & {"bot:renovate", "bot:dependabot"}:
        reasons.append("dependency automation item")
    if "bot:dependabot" in labels:
        labels.add("needs:owner-review")
        reasons.append("Dependabot routine PRs are policy-drift signals because Renovate owns updates")

    if "dependencies" not in labels:
        label_type = classify_type(text, existing)
        labels.add(label_type)
    labels.update(classify_areas(text))

    if "area:mcp-tools" in labels:
        reasons.append("agent-facing MCP tool schema or validation behavior")
    if "area:zammad-api" in labels:
        reasons.append("Zammad API coverage or ticket/article behavior")
    if "area:transport" in labels:
        reasons.append("MCP transport/runtime behavior")

    if (
        state == "OPEN"
        and not author_is_bot(issue.get("author") or issue.get("user"))
        and ("type:bug" in labels or "area:mcp-tools" in labels or "area:zammad-api" in labels)
    ):
        labels.add("needs:owner-review")

    if "type:bug" in labels and not re.search(r"repro|steps|traceback|error|```", text):
        labels.add("needs:repro")

    llm_added = merge_llm_labels(labels, llm_payload)
    if llm_added:
        reasons.append(f"LLM suggested labels: {', '.join(llm_added)}")

    duplicate_candidates = find_duplicate_candidates(issue, duplicate_pool)
    if duplicate_candidates:
        labels.add("needs:duplicate-review")
        reasons.append("potential duplicate or repeated theme found")

    type_count = len(labels & TYPE_LABELS)
    area_count = len(labels & AREA_LABELS)
    confidence = "high" if type_count and area_count else "medium"
    if llm_payload and not llm_added:
        confidence = "medium"
    attention = "owner" if "needs:owner-review" in labels or "needs:duplicate-review" in labels else "none"

    return TriageDecision(
        number=number,
        kind="issue",
        labels=ordered_labels(labels),
        confidence=confidence,
        attention=attention,
        reasons=reasons or ["deterministic label classification"],
        duplicate_candidates=duplicate_candidates,
    )


def classify_pr_payload(
    pr: dict[str, Any],
    *,
    changed_files: list[str] | None = None,
    llm_payload: dict[str, Any] | None = None,
) -> TriageDecision:
    number = int(pr.get("number") or 0)
    title = str(pr.get("title") or "")
    body = str(pr.get("body") or "")
    state = str(pr.get("state") or "").upper()
    author_login = extract_login(pr.get("author") or pr.get("user"))
    existing = set(label_names(pr))
    files = changed_files or [str(item.get("path") or item.get("filename") or "") for item in pr.get("files") or []]
    text = text_blob(title, body, " ".join(existing), author_login, " ".join(files), pr.get("headRefName"))
    labels = set()
    reasons = []

    labels.update(dependency_labels(text, author_login))
    if labels & {"bot:renovate", "bot:dependabot"}:
        labels.add("type:chore")
        reasons.append("dependency automation pull request")
    if "bot:dependabot" in labels:
        labels.add("needs:owner-review")
        reasons.append("Dependabot routine PR should be closed or reconciled against Renovate ownership")

    if "dependencies" not in labels:
        labels.add(classify_type(text, existing))
    labels.update(classify_areas(text, files))

    if not labels & AREA_LABELS and any(path.endswith(".md") for path in files):
        labels.add("area:docs")
    if not labels & AREA_LABELS and any(path.startswith(".github/") for path in files):
        labels.add("area:ci-cd")
    if not labels & AREA_LABELS and any(path.startswith("mcp_zammad/") for path in files):
        labels.add("area:python")
    if (
        "area:docs" in labels
        and "type:docs" not in labels
        and any(path.startswith(("mcp_zammad/", "tests/")) for path in files)
    ):
        labels.discard("area:docs")

    if state == "OPEN" and not author_is_bot(pr.get("author") or pr.get("user")):
        labels.add("needs:owner-review")
        reasons.append("open human-authored PR needs maintainer review")

    llm_added = merge_llm_labels(labels, llm_payload)
    if llm_added:
        reasons.append(f"LLM suggested labels: {', '.join(llm_added)}")

    state_summary = pr_state_summary(pr)
    confidence = "high" if labels & AREA_LABELS else "medium"
    attention = "owner" if "needs:owner-review" in labels or state_summary.get("review") == "needed" else "none"

    return TriageDecision(
        number=number,
        kind="pull_request",
        labels=ordered_labels(labels),
        confidence=confidence,
        attention=attention,
        reasons=reasons or ["deterministic PR classification"],
        state_summary=state_summary,
    )


def pr_state_summary(pr: dict[str, Any]) -> dict[str, Any]:
    author = pr.get("author") or pr.get("user")
    status_rollup = pr.get("statusCheckRollup")
    ci = "unknown"
    if isinstance(status_rollup, list) and status_rollup:
        conclusions = [str(item.get("conclusion") or item.get("state") or "").upper() for item in status_rollup]
        if any(value in {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT"} for value in conclusions):
            ci = "failing"
        elif all(value in {"SUCCESS", "NEUTRAL", "SKIPPED"} for value in conclusions):
            ci = "passing"
        else:
            ci = "pending"
    review_decision = str(pr.get("reviewDecision") or "").upper()
    review = "needed"
    if review_decision == "APPROVED":
        review = "approved"
    elif review_decision == "CHANGES_REQUESTED":
        review = "blocked"
    elif str(pr.get("state") or "").upper() != "OPEN":
        review = "closed"
    return {
        "author_type": "bot" if author_is_bot(author) else "human",
        "ci": ci,
        "review": review,
        "mergeability": str(pr.get("mergeable") or "unknown").casefold(),
    }


def ensure_labels(repo: str, labels: list[str]) -> None:
    for label in labels:
        description, color = LABEL_DEFINITIONS.get(label, ("", "ededed"))
        create = run_gh(
            [
                "label",
                "create",
                label,
                "--repo",
                repo,
                "--description",
                description,
                "--color",
                color,
            ],
            check=False,
        )
        if create.returncode == 0:
            continue
        run_gh(
            [
                "label",
                "edit",
                label,
                "--repo",
                repo,
                "--description",
                description,
                "--color",
                color,
            ],
            check=False,
        )


def apply_labels(repo: str, number: int, labels: list[str], *, kind: str) -> None:
    if not labels:
        return
    ensure_labels(repo, labels)
    target = "pr" if kind == "pull_request" else "issue"
    cmd = [target, "edit", str(number), "--repo", repo]
    for label in labels:
        cmd.extend(["--add-label", label])
    run_gh(cmd)


def days_since(value: str | None, *, now: datetime | None = None) -> int | None:
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, math.floor((current - parsed).total_seconds() / 86400))
