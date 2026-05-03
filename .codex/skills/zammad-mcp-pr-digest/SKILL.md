---
name: zammad-mcp-pr-digest
description: Run pull request triage and digest workflows for basher83/Zammad-MCP, including human PR review attention, Renovate/Dependabot dependency noise, CI state, mergeability, and configurable time windows.
---

# Zammad-MCP PR Digest

## Objective

Produce a maintainer-focused pull request digest for `basher83/Zammad-MCP`. This repository has high PR volume from dependency bots and low but important human contributor volume, so the digest should separate routine Renovate updates from PRs that need owner review.

Default to summary-only output. Include compact details when the user asks for a table, full digest, or specific PR status.

For triage automation, classify PRs from metadata plus changed files. The CLI accepts optional LLM JSON as an additive signal for local or future isolated generator runs, but the repository Actions run deterministic-only in v1. Apply labels only. Do not run PR code, merge PRs, close PRs, or comment on source PRs in v1. `pull_request_target` workflows must fetch file names safely from the fork or branch and pass only file names and metadata into the classifier.

## Inputs

- Optional PR number for targeted triage.
- Optional time window, default previous 30 days.
- Optional repo override, default `basher83/Zammad-MCP`.
- Optional backfill mode for open or recent PRs.

## Workflow

Run the PR collector for a recent digest:

```bash
python3 .codex/skills/zammad-mcp-pr-digest/scripts/collect_pr_digest.py --window 30d
```

Run targeted PR triage:

```bash
python3 .codex/skills/zammad-mcp-pr-digest/scripts/triage_pr.py --pr 200 --dry-run --json
```

Run open PR backfill:

```bash
python3 .codex/skills/zammad-mcp-pr-digest/scripts/triage_pr.py --backfill --state open --dry-run --json
```

## Interpretation

Treat Renovate as the routine dependency update owner. Renovate PRs should usually be summarized by ecosystem and failure state, not individually unless checks fail, security labels appear, or the PR remains open.

Treat Dependabot routine version PRs as policy drift because this repository keeps Dependabot configured for security posture while Renovate owns routine version updates.

Treat open human-authored PRs as owner-attention items unless they are already merged, closed, or explicitly marked ready-to-merge.

Use the paired issue skill's `post_triage_digest.py` to publish combined issue and PR summaries into the tracking issue titled `[triage] Zammad-MCP maintainer digest`.

## Validation

```bash
uv run pytest .codex/skills/zammad-mcp-pr-digest/scripts/test_triage_pr.py
```

```bash
python3 .codex/skills/zammad-mcp-pr-digest/scripts/collect_pr_digest.py --window 30d --limit-prs 50
```
