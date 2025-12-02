# Dependency & Branch Protection Strategy for `Zammad-MCP`

This document describes how dependency updates and branch protection are configured for the [`basher83/Zammad-MCP`](https://github.com/basher83/Zammad-MCP) repository.

It covers:

- How Renovate is configured for this repo
- Which updates auto‑merge to `main` (“no visible PR”)
- Which updates always require human attention
- How branch protection and required checks interact with Renovate

---

## 1. Renovate Overview

`Zammad-MCP` uses [Renovate](https://docs.renovatebot.com/) with a centralized configuration stored in [`basher83/renovate-config`](https://github.com/basher83/renovate-config).

### 1.1 Repo-level Renovate config

`renovate.json` in this repo:

```jsonc
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "local>basher83/renovate-config",
    "local>basher83/renovate-config//presets/python-mcp.json",
    "local>basher83/renovate-config//presets/github-actions-security.json",
    "local>basher83/renovate-config//presets/docker.json"
  ],
  "labels": [
    "dependencies",
    "renovate"
  ],
  "assignees": [
    "basher83"
  ],
  "commitMessagePrefix": "chore(deps):",
  "packageRules": [
    {
      "description": "Require approval for major Zammad API updates",
      "matchPackageNames": [
        "zammad-py"
      ],
      "matchUpdateTypes": [
        "major"
      ],
      "dependencyDashboardApproval": true
    }
  ]
}
```

Key points:

- **Extends a central config** (`local>basher83/renovate-config`) plus three presets:
  - `python-mcp.json` (Python & MCP‑specific behavior)
  - `github-actions-security.json` (GitHub Actions)
  - `docker.json` (Docker images)
- All Renovate PRs:
  - Are labeled with `dependencies` and `renovate`.
  - Are assigned to `@basher83`.
  - Use `chore(deps):` as the commit message prefix.
- Extra repo‑specific rule:
  - **`zammad-py` major updates require explicit approval** in the Dependency Dashboard.

---

## 2. What Auto‑Merges vs. What Requires Review

The overall philosophy:

> “No visible PR; updates land in `main` automatically for changes that don’t need manual verification.  
> Risky changes remain as PRs and require explicit attention/approval.”

Below is how this breaks down by dependency type.

### 2.1 Python dependencies (`presets/python.json` & `python-mcp.json`)

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

### 2.2 GitHub Actions (`presets/github-actions-security.json`)

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

### 2.3 Docker (`presets/docker.json`)

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

## 3. Branch Protection for `main`

Branch protection is configured via a ruleset named **“Protection Rules”** and applies to `~DEFAULT_BRANCH` (i.e. `main`).

### 3.1 Ruleset summary

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

> Renovate **can** automerge, but only when these required checks are passing.

---

## 4. How Renovate and Branch Rules Work Together

Putting it all together:

1. Renovate detects an update that matches an **automerge** rule.
2. Renovate opens a PR against `main`.
3. GitHub runs the required checks:
   - `Tests and Coverage` → `test-and-coverage`
   - `Security Scan` → `security-scan`
4. If both required checks succeed:
   - Branch rules allow merging (no required approvals).
   - Renovate merges the PR into `main`.
   - PR is closed (often quickly), giving the “no visible PR” experience.
5. If checks fail **or** the update requires approval (e.g. `zammad-py` major, MCP major, sensitive Actions, critical Docker images):
   - Renovate **does not** merge.
   - PR remains open.
   - For rules using `dependencyDashboardApproval: true`, Renovate waits for explicit approval from the Dependency Dashboard.

This gives a clear separation between:

- **Low‑risk, routine maintenance**: silently auto‑merged to `main` once green.
- **High‑impact or risky changes**: visible PRs that require either manual review/merge or explicit dashboard approval.

---

## 5. Quick Reference

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

## 6. How to Adjust This in Future

- To make more things **auto‑merge**:
  - Add/adjust `packageRules` with `automerge: true` in `basher83/renovate-config`.
- To make certain areas **stricter**:
  - Add `dependencyDashboardApproval: true` or remove `automerge` for those dependencies.
- To tighten branch safety:
  - Add more required status checks if needed (e.g., Codacy), or
  - Increase `required_approving_review_count` (note: this will block Renovate unless you also adjust bypass behavior).

This document reflects the current behavior and is intended as a reference when revisiting Renovate or branch protection configuration for `Zammad-MCP`.
