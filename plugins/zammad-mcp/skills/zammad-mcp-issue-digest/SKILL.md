---
name: zammad-mcp-issue-digest
description: Run issue digest and issue triage workflows for basher83/Zammad-MCP, including small-repo owner attention, deterministic labels, optional LLM label suggestions, duplicate candidates, Renovate/Dependabot policy drift, and the scheduled maintainer tracking digest.
---

# Zammad-MCP Issue Digest

## Objective

Produce a headline-first, repo-owner digest of `basher83/Zammad-MCP` issues for requested labels over the previous 24 hours by default. Honor a different duration when the user asks for one, for example `past week`, `48 hours`, or `30d`.

For triage automation, classify issues with deterministic rules first. The CLI accepts optional LLM JSON as an additive signal for local or future isolated generator runs, but the repository Actions run deterministic-only in v1. Apply labels only. Do not comment on source issues, close issues, or close duplicates in v1. Duplicate candidates belong in JSON output and the maintainer tracking digest.

Default to a summary-only response. Include a details table only when the user asks for details, a full digest, a table, or similar.

This skill mirrors the upstream `codex-issue-digest` pattern but is scoped to this repository's labels and operating model. It is meant for triage and owner attention, not broad GitHub reporting.

## Inputs

Accept any of these:

- Area labels such as `area:python`, `area:ci-cd`, `area:security`, `area:docs`, `area:web`, `area:infra`, `area:mcp-tools`, `area:zammad-api`, or `area:transport`.
- Bot/dependency labels such as `bot:renovate`, `bot:dependabot`, `dependencies`, `renovate`, `github-actions`, `docker`, or `python:uv`.
- `all areas` / `all labels` to scan across current Zammad-MCP area and bot labels.
- Optional repo override, default `basher83/Zammad-MCP`.
- Optional time window, default previous 24 hours.

When the user says "dependency digest" or asks about Renovate/Dependabot without naming labels, use `--labels dependencies bot:renovate bot:dependabot renovate github-actions docker python:uv`.

When the user asks generally for repo issue status without labels, use `--all-labels`. This repository has a small issue set and sparse labeling, so all-label mode intentionally scans all recently updated issues and treats missing type labels as `unclassified`.

## Workflow

Run targeted issue triage when a new or reopened issue needs labels:

```bash
python3 plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/triage_issue.py --issue 212 --dry-run --json
```

Backfill open issues before enabling or after changing label rules:

```bash
python3 plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/triage_issue.py --backfill --state open --dry-run --json
```

Use `--apply` only when the maintainer has asked to mutate labels. The script will create missing controlled labels as needed and then add labels to the issue.

For the scheduled maintainer tracking issue, collect the issue digest and combine it with the PR digest through `post_triage_digest.py`. The tracking issue title is `[triage] Zammad-MCP maintainer digest`.

1. Run the collector from a current `Zammad-MCP` repo checkout:

```bash
python3 plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/collect_issue_digest.py --all-labels --window-hours 24
```

Use `--window "past week"` or `--window-hours 168` when the user asks for a non-default duration.

Use label-specific runs when requested:

```bash
python3 plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/collect_issue_digest.py --labels area:python area:ci-cd --window "past week"
```

Use the dependency-maintenance run for Renovate/Dependabot triage:

```bash
python3 plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/collect_issue_digest.py --labels dependencies bot:renovate bot:dependabot renovate github-actions docker python:uv --window "past week"
```

1. Treat the collector JSON as source of truth. It includes new issues, new comments, reactions, current labels, `summary_inputs`, `digest_rows`, source metadata, and the time window.

1. Choose output mode from the user's request. Default mode starts with `## Summary` and does not include `## Details`. Details mode starts with `## Summary`, then includes `## Details`.

1. In `## Summary`, write a single headline or judgment as the first nonblank line. On quiet runs, prefer exactly:

```markdown
No major issues reported by users.
```

Use that when there are no elevated rows, no repeated theme, and nothing needing owner action.

1. For active runs, lead with the count or theme, then list only the issues or clusters that need attention. Use inline numbered references from `ref_markdown`, for example `[1](https://github.com/basher83/Zammad-MCP/issues/123)`. Do not add a separate footnotes section.

1. Cluster only when issues share the same repo problem. Good Zammad-MCP clusters include FastMCP migration/runtime behavior, Zammad API coverage, auth/security hardening, CI and release workflow, docs drift, and dependency-bot governance. Do not cluster merely because several issues share a broad `area:*` label.

1. Treat dependency bot items specially. Surface Dependabot version-update PRs as policy drift if routine Dependabot PRs appear after the repo disabled them. Surface Renovate blocked/approval-needed items when they affect required checks, Python/MCP pins, Docker image pins, or GitHub Actions security updates.

1. In `## Details`, include a compact table only when useful. Prefer columns for marker, area, type, description, interactions, and refs. Keep it short and omit low-signal rows when the summary already covers them.

1. Mention the collector `script_version`, repo checkout `git_head`, and time window in one compact source line. In default mode, put this before the final details prompt.

1. In default mode, end with a short prompt such as:

```markdown
Want details? I can expand this into the issue table.
```

## Attention Rules

The collector uses small-repo attention markers. The baseline is 2 human interactions for elevated attention and 4 for very high attention over 24 hours. Longer windows scale those cutoffs by the square root of the window length, not linearly, and cap at 4 and 8 interactions because this repository has fewer than 50 total issues and very low comment volume.

Human interactions are human-authored new issue posts, human-authored new comments, and human reactions created during the window. Bot posts and bot reactions are excluded.

Use the JSON `attention_marker` exactly. Do not invent new marker symbols. Explain it as high user interaction when needed.

## Validation

Validate the triage classifier:

```bash
uv run pytest plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/test_triage_issue.py
```

Dry run recent repo issue activity:

```bash
python3 plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/collect_issue_digest.py --all-labels --window "past week" --limit-issues 20
```

Dry run dependency bot activity:

```bash
python3 plugins/zammad-mcp/skills/zammad-mcp-issue-digest/scripts/collect_issue_digest.py --labels dependencies bot:renovate bot:dependabot renovate github-actions docker python:uv --window "past week" --limit-issues 20
```
