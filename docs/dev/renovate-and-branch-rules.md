# Dependency & Branch Protection Strategy for `Zammad-MCP`

This document describes how dependency updates, branch protection, and dependency-bot CI are configured for the [`basher83/Zammad-MCP`](https://github.com/basher83/Zammad-MCP) repository.

It covers:

- How Renovate and Dependabot responsibilities are split
- How dependency-bot PRs interact with secret-dependent integrations
- Which updates auto‑merge to `main` (“no visible PR”)
- Which updates always require human attention
- How branch protection and required checks interact with Renovate

---

## 1. Dependency Bot Ownership

Renovate owns routine version-update PRs for this repository. Dependabot remains available for GitHub's security-alert and security-update workflows, but Dependabot version updates are intentionally disabled in `.github/dependabot.yml` with `open-pull-requests-limit: 0`.

This avoids two bots opening competing `uv.lock`, GitHub Actions, or Docker update branches for the same dependency surface. In practice, normal dependency maintenance should come from Renovate, while Dependabot is treated as the security-alert backstop.

Dependency-bot PRs must still run the required validation jobs. Secret-dependent reporting and publishing integrations are optional for PR validation and must skip cleanly when secrets are unavailable.

GitHub treats Dependabot-triggered `pull_request` workflows like forked PRs: they receive a read-only token and do not receive normal Actions secrets. If the repository needs secret-backed behavior on Dependabot PRs, configure matching Dependabot secrets in GitHub and keep the workflow guarded so the absence of those secrets does not fail validation.

## 2. Renovate Overview

`Zammad-MCP` uses [Renovate](https://docs.renovatebot.com/) with a centralized configuration stored in [`basher83/renovate-config`](https://github.com/basher83/renovate-config).

### 2.1 Repo-level Renovate config

[`renovate.json`](../../renovate.json) in this repo extends the central config and three presets, and adds four package rules. Read the file for the exact JSON.

Key points:

- **Extends a central config** (`local>basher83/renovate-config`) plus three presets:
  - `python-mcp.json` (Python & MCP‑specific behavior)
  - `github-actions-security.json` (GitHub Actions)
  - `docker.json` (Docker images)
- All Renovate PRs:
  - Are labeled with `dependencies` and `renovate`.
  - Are assigned to `@basher83`.
  - Use `chore(deps):` as the commit message prefix.
- Extra repo‑specific rules:
  - Renovate does not propose Python 3.14 or later (`allowedVersions: "<3.14"`). This matches `requires-python` in `pyproject.toml`.
  - The uv pins in `mise.toml` and the `uv-pre-commit` hook update in one PR (group `uv version pins`).
  - Major updates to `zammad-py` require explicit approval in the Dependency Dashboard.
  - Major updates to `fastmcp` require explicit approval in the Dependency Dashboard. They move together with the `mcp` major (#353).
- `mise.toml` is the source of truth for the tool versions, and CI installs Python and uv from it with `jdx/mise-action`. `mise.lock` records checksums and download URLs, and CI installs with `--locked`, so a `mise.toml` change without a matching `mise.lock` change fails CI. `scripts/validate.sh` fails when the `uv-pre-commit` hook pins a different uv version, so a PR that updates only one uv pin fails CI.

---

## 3. What Auto‑Merges vs. What Requires Review

The overall philosophy:

> “No visible PR; updates land in `main` automatically for changes that don’t need manual verification.  
> Risky changes remain as PRs and require explicit attention/approval.”

Below is how this breaks down by dependency type.

Sections 3.1 to 3.3 describe the presets in [`basher83/renovate-config`](https://github.com/basher83/renovate-config). That repository is the source of truth for them, and this repository does not check them. Read the preset files before you rely on a specific rule below.

### 3.1 Python dependencies (`presets/python.json` & `python-mcp.json`)

**Auto‑merge (PR merges & disappears, once checks pass):**

- Any dependency categorized as `python` with:
  - **Patch** updates.
- Python **dev dependencies** with:
  - **Minor** updates.
- Grouped dev/test tooling:
  - `pytest*` → grouped as *“Python test dependencies”*.
  - Linters/dev tools: `black`, `ruff`, `mypy`, `flake8`, `isort`, `pylint`, `uv` → grouped as *“Python linters and dev tools”*.
  - Type stubs: `types-*` → grouped as *“Python type stubs”*.

These groups are configured with `automerge: true` (no `automergeType` override), so Renovate will:

1. Open a PR.
2. Wait for required checks to pass.
3. Merge the PR into `main`.
4. Close the PR → often barely visible unless you watch in real time.

**Require review / manual action:**

- **Major** version bumps for most Python libraries:
  - No `automerge` rule → PRs stay open until manually handled.
- MCP- and Python-version specific rules from `python-mcp.json`:
  - Python runtime (`python` Docker image / GitHub tags):  
    - `allowedVersions: "<=3.13"` (stay at or below 3.13.x for now).
  - `requires-python` in `pyproject.toml`:  
    - `allowedVersions: "<3.14"`.
  - MCP SDK (`mcp` package):
    - **Major** updates have `dependencyDashboardApproval: true` → must be explicitly approved in the Dependency Dashboard.

**Repo-specific rule:**

- `zammad-py` (Zammad API client) **major updates**:
  - `dependencyDashboardApproval: true` → PR will not auto‑merge; requires explicit approval.

### 3.2 GitHub Actions (`presets/github-actions-security.json`)

Goals:

- Pin actions to **commit SHAs** for security.
- Auto‑merge safe updates (digests + non‑sensitive version bumps).
- Require approval for sensitive action updates.

**Auto‑merge (PR merges & disappears):**

- All GitHub Actions **digest** updates:
  - e.g. `actions/checkout@<sha>` digest bumps.
  - Rule: `"matchUpdateTypes": ["digest"], "automerge": true`.

- Non‑sensitive GitHub Actions **patch/minor/major** updates:
  - Any action **not** matching the “sensitive” patterns below.
  - Rule uses `matchPackageNames` with negative regex patterns to pick out non‑sensitive actions and `automerge: true`.

**Require approval / manual review:**

- **Sensitive** GitHub Actions with `minor` or `major` bumps:
  - `actions/checkout`
  - `actions/upload-artifact`
  - `actions/download-artifact`
  - `aws-actions/*`
  - `google-github-actions/*`
  - `azure/*`
  - `docker/*`
- For these, `matchUpdateTypes: ["minor","major"]` + `dependencyDashboardApproval: true`.
- Result: PRs open and won’t auto‑merge until you explicitly approve via the Dependency Dashboard.

### 3.3 Docker (`presets/docker.json`)

Goals:

- Pin images to **digests** for reproducibility and security.
- Auto‑merge safe image bumps.
- Require manual approval for high‑impact database/network infra images.

**Auto‑merge (PR merges & disappears):**

- All Docker **digest** updates:
  - Group: *“Docker Digests”* with `automerge: true`.
- All Docker **patch** updates.
- **Minor** updates for **non‑critical** images:
  - Non‑critical = anything *not* matching critical infra patterns like:
    - `postgres`, `mysql`, `redis`, `mongo*`, `elasticsearch`, `rabbitmq`, `kafka`, `nginx`, `traefik`, `envoyproxy/*`.

**Require approval / manual review:**

- **Minor** updates for critical infra images:
  - `postgres`, `mysql`, `redis`, `mongo*`, `elasticsearch`, `rabbitmq`, `kafka`, `nginx`, `traefik`, `envoyproxy/*`.
  - Configured with `dependencyDashboardApproval: true`.
- **All major** Docker image updates:
  - Always require manual approval.

---

## 4. Branch Protection for `main`

Branch protection is configured via a ruleset named **“Protection Rules”** and applies to `~DEFAULT_BRANCH` (i.e. `main`).

### 4.1 Ruleset summary

```jsonc
{
  "name": "Protection Rules",
  "target": "branch",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"]
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "required_reviewers": [],
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "automatic_copilot_code_review_enabled": false,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          { "context": "test-and-coverage", "integration_id": 15368 },
          { "context": "security-scan",    "integration_id": 15368 }
        ]
      }
    }
  ],
  "bypass_actors": [
    {
      "actor_id": 5,
      "actor_type": "RepositoryRole",
      "bypass_mode": "always"
    }
  ]
}
```

**What this enforces:**

- `main` **cannot** be:
  - Deleted.
  - Force‑pushed (no non‑fast‑forward pushes).
- All changes to `main` must go through **pull requests**.
- **No review required**:
  - `required_approving_review_count: 0`.
  - No code owner review.
- **Required status checks** on PRs to `main`:
  - `test-and-coverage` (from `.github/workflows/tests.yml`).
  - `security-scan` (from `.github/workflows/security-scan.yml`).

> Renovate **can** automerge, but only when these required checks are passing. GitHub enforces this, not Renovate: Renovate enables GitHub auto-merge on each automerge PR, and GitHub merges as soon as the ruleset is satisfied. Other checks, such as `build-and-push`, CodeQL, and Codacy, do not hold the merge. They can still be running, or can fail, after the PR merges (observed in #392).

---

## 5. Secret-Dependent CI Policy

Required PR validation must not depend on repository, Codacy, Docker Hub, or publishing credentials. The repo follows this split:

`test-and-coverage` is required. It runs tests, enforces the coverage threshold, and uploads coverage artifacts on every PR. The Codacy coverage upload runs only when `CODACY_PROJECT_TOKEN` is available.

`security-scan` is required. It runs Bandit and dependency scanning without requiring external credentials. Uploads that rely on the built-in `GITHUB_TOKEN` remain part of the job.

`Build and Publish Docker Image` validates the Docker build on PRs but only pushes images and creates attestations on non-PR events. Transient BuildKit or registry errors should be retried; they are not normally fixed by changing dependency-update PR branches.

## 6. How Renovate and Branch Rules Work Together

Putting it all together:

1. Renovate detects an update that matches an **automerge** rule.
2. Renovate opens a PR against `main`.
3. GitHub runs the required checks: `Tests and Coverage` as `test-and-coverage`, and `Security Scan` as `security-scan`.
4. When Renovate opens the PR, it also enables GitHub auto-merge on it (Renovate's `platformAutomerge` default, with "Allow auto-merge" on in this repository). As soon as both required checks succeed, GitHub merges the PR into `main` and closes it, without waiting for non-required checks. This is the “no visible PR” experience when updates move quickly. #392 recorded a merge 11 seconds after `test-and-coverage` passed, while a non-required check was still running.
5. If a required check fails, GitHub does not merge the PR, and it stays open until a new commit passes.
   A failing non-required check does not stop the merge. Watch `build-and-push` and the CodeQL and Codacy results on merged Renovate PRs, or make a check required if it must gate merges.
6. Updates that require approval, such as a `zammad-py` major, MCP major, sensitive Actions update, or critical Docker image update, use `dependencyDashboardApproval: true`. Renovate does not create a branch or PR for them. They stay under "Pending Approval" on the Dependency Dashboard until someone approves them there. After approval, Renovate opens the PR. It automerges through steps 4 and 5 only if an automerge rule also matches, as for GitHub-hosted runner updates; otherwise it waits for a manual merge.

This gives a clear separation between:

- **Low‑risk, routine maintenance**: silently auto‑merged to `main` once the required checks are green.
- **High‑impact or risky changes**: visible PRs that require either manual review/merge or explicit dashboard approval.

---

## 7. Quick Reference

### Auto‑merged (once tests & security checks pass)

- Python:
  - All `patch` updates.
  - Dev `minor` updates.
  - Grouped pytest, linters, and type stubs.
- GitHub Actions:
  - All `digest` updates.
  - Non‑sensitive `patch` / `minor` / `major`.
- Docker:
  - All `digest` updates.
  - All `patch` updates.
  - Non‑critical `minor` updates.

### Require manual approval / attention

- `zammad-py` **major** updates.
- MCP SDK (`mcp`) **major** updates.
- Python library **majors** in general.
- GitHub Actions:
  - Sensitive `minor` / `major` updates (checkout, upload-artifact, AWS/GCP/Azure/docker actions).
- Docker:
  - `minor` updates to critical images (databases, queues, proxies, etc.).
  - All **major** image updates.

### Branch rules (for `main`)

- Protected from deletion & force‑push.
- All changes via PR.
- No required human reviews.
- Required checks:
  - `test-and-coverage`
  - `security-scan`

---

## 8. How to Adjust This in Future

- To make more things **auto‑merge**:
  - Add/adjust `packageRules` with `automerge: true` in `basher83/renovate-config`.
- To make certain areas **stricter**:
  - Add `dependencyDashboardApproval: true` or remove `automerge` for those dependencies.
- To tighten branch safety:
  - Add more required status checks if needed (e.g., Codacy), or
  - Increase `required_approving_review_count` (note: this will block Renovate unless you also adjust bypass behavior).

This document reflects the current behavior and is intended as a reference when revisiting Renovate or branch protection configuration for `Zammad-MCP`.
