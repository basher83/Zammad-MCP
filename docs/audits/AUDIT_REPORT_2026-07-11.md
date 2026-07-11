# Repository Audit Report — 2026-07-11

## Scope and method

This audit compared the repository to `AGENTS.md`, treating that file as the source of truth. Independent passes covered
automation and CI, runtime and security, packaging and structure, and current user-facing documentation. Documentation
claims were extracted first, verified against code and configuration, then expanded by searching for repeated drift
patterns. Historical plans and generated/reference material were excluded from documentation accuracy metrics.

## Documentation accuracy

| Audited scope | True | False | Needs review | Total |
| --- | ---: | ---: | ---: | ---: |
| `README.md` and `SECURITY.md` | 31 | 18 | 9 | 58 |
| `CONTRIBUTING.md` and `ARCHITECTURE.md` | 73 | 57 | 11 | 141 |
| HTTP and deployment documentation | 21 | 13 | 11 | 45 |

The table records the pre-fix audit state. This change corrects the highest-confidence and highest-risk claims, including
HTTP authentication, canonical endpoint paths, setup-script locations, tool names and counts, coverage policy, Python
support, obsolete global-client descriptions, and security-tool status. Lower-risk drift remains in the large contributor
and architecture guides and should be resolved as those documents are simplified.

## Critical and high findings requiring a decision

### Inbound HTTP authentication

The built-in HTTP transport has no inbound MCP client authentication, while it exposes credential-backed read, write,
and destructive Zammad operations. The checked-in Compose file binds to `0.0.0.0` and publishes port 9146. Documentation
now states this boundary accurately, but choosing and implementing a supported control requires a maintainer decision:
FastMCP authentication, an authenticated reverse proxy, mTLS/service mesh, or a private-network-only contract.

### Canonical automation and release gates

The repository has useful checks but no single canonical development suite, release suite, affected-target detector, or
agentic workflow matching the structure required by `AGENTS.md`. The test workflow does not run every local lint, format,
type, Markdown, build, and release gate. Designing those orchestration boundaries is broader than a small audit fix.

Docker publishing is independent of a release gate, and the `latest` tag follows default-branch builds rather than stable
releases. The package metadata reports version 1.0.0 while the newest release tag and changelog report 1.1.0. The
maintainer must choose the authoritative version source and promotion policy before release automation is rewritten.

### Structural limits

Several core files exceed the `AGENTS.md` 200-line file limit by a wide margin: `mcp_zammad/server.py` is roughly 2,700
lines, `mcp_zammad/models.py` roughly 670, and `mcp_zammad/client.py` roughly 480. Multiple setup methods and test files
also exceed construct and file limits. Correcting this safely requires a planned, behavior-preserving refactor with tests;
it is not a documentation-only or mechanical change.

## Medium findings requiring behavioral design

The runtime audit also found missing upstream HTTP timeouts; attachment limits applied after full materialization; an HTML
sanitizer that can alter plaintext and may not cover all HTML forms; secret-file failures that can fall back to stale
environment credentials; response models that discard some promised fields; response-size limits not uniformly enforced;
statistics date filters that can be ignored; and attachment metadata lookup that does not use `ticket_id`. These findings
need explicit API, compatibility, and failure-mode decisions before code changes.

## Small fixes applied

Automation now uses Python 3.13.14 consistently while CI tests the declared 3.10–3.13 range. Coverage has one 86% policy,
security scans fail loudly for Bandit, Semgrep, and pip-audit, workflow Python commands use the uv boundary, action/tool
versions are pinned, and Markdown linting uses Rumdl consistently. Stale suppression comments were removed by the updated
Ruff hook. Documentation corrections are limited to claims directly verified during the audit.

## Residual documentation work

`CONTRIBUTING.md` still overstates portions of workflow behavior and contains old extension examples. `ARCHITECTURE.md`
still has stale model diagrams, extension recipes, and test-tree descriptions. `SECURITY.md` contains operational promises
and external GitHub-setting claims that require maintainer confirmation. These should be rewritten after the automation,
authentication, and release-policy decisions above so the documents describe a stable target rather than another
transitional snapshot.
