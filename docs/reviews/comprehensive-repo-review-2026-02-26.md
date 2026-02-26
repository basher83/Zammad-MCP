# Comprehensive Repository Review: Zammad MCP Server

**Date**: 2026-02-26
**Repository**: basher83/Zammad-MCP
**Version**: 1.0.0 (pyproject.toml) / 1.1.0 (CHANGELOG.md)
**Codebase Size**: ~3,800 lines production code, ~4,200 lines tests
**Review Scope**: Security, Code Quality, Feature Gaps, Simplification, DevOps

---

## Executive Summary

The Zammad MCP Server is a well-architected Python project that demonstrates strong security awareness, thorough documentation, and a mature DevOps setup. The codebase successfully bridges the Zammad ticket system with the Model Context Protocol (MCP) ecosystem, exposing 19 tools, 4 resources, and 3 prompts.

**Overall Assessment**: The project is production-ready for its current scope but has clear areas for improvement across all review dimensions. The most impactful issues center around: (1) a data-corruption bug in input HTML escaping, (2) SSRF protection that warns but doesn't block, (3) a monolithic server.py that would benefit from decomposition, and (4) significant untapped Zammad API surface area.

### Scoring Summary

| Dimension | Score | Key Strength | Key Weakness |
|-----------|-------|--------------|--------------|
| Security | 7/10 | Multi-layered defense, Docker hardening | SSRF warning-only, inconsistent output sanitization |
| Code Quality | 7/10 | Clean architecture, strong typing | server.py monolith, HTML escaping bug |
| Feature Completeness | 5/10 | Core ticket CRUD is solid | Only 53% of zammad_py resources used |
| Code Simplification | 6/10 | Models and config are clean | ~1,000-1,400 lines of removable duplication |
| DevOps | 8/10 | Excellent CI/CD, pre-commit hooks | Python version inconsistency, no lint in CI |

---

## Table of Contents

1. [Critical Issues (Immediate Action Required)](#1-critical-issues)
2. [Security Review](#2-security-review)
3. [Code Quality Review](#3-code-quality-review)
4. [Feature Gap Analysis](#4-feature-gap-analysis)
5. [Code Simplification Opportunities](#5-code-simplification-opportunities)
6. [DevOps & Infrastructure Review](#6-devops--infrastructure-review)
7. [Prioritized Action Plan](#7-prioritized-action-plan)

---

## 1. Critical Issues

These issues should be addressed before any other work:

### 1.1 HTML Escaping Corrupts Data Sent to Zammad API

- **Severity**: Critical (Bug)
- **Location**: `mcp_zammad/models.py:268-272`

The `TicketCreate`, `ArticleCreate`, and `TicketUpdateParams` models HTML-escape user input via Pydantic field validators before sending data to the Zammad API:

```python
@field_validator("title", "article_body")
@classmethod
def sanitize_html(cls, v: str) -> str:
    return html.escape(v)
```

This means a ticket titled `"Server <script> issue"` gets stored in Zammad as `"Server &lt;script&gt; issue"`. The data is **corrupted at the storage layer** rather than escaped at the display layer. Zammad handles its own XSS prevention in rendering.

**Fix**: Remove input-side HTML escaping from all Pydantic validators. Escape only at the output/display layer (the `_escape_article_body()` function at `server.py:193-203` already does this correctly for article display).

### 1.2 SSRF Protection is Warning-Only, Not Blocking

- **Severity**: High
- **Location**: `mcp_zammad/client.py:92-100`

The URL validator checks for localhost and private network addresses but only emits `logger.warning()` instead of rejecting the request. The variable is named `blocked_hosts`, but nothing is actually blocked. Additionally:

- The `172.*` prefix check is overly broad (should check `172.16.0.0/12`)
- Missing IPv6 mapped addresses (`::ffff:127.0.0.1`)
- Missing DNS rebinding protection
- `0.0.0.0` is listed but only warned on

**Fix**: Change warnings to raise `ConfigException` for blocked hosts. Add opt-in `ZAMMAD_ALLOW_PRIVATE_NETWORK=true` for legitimate internal Zammad instances.

### 1.3 Python Version Inconsistency Across 5 Sources

- **Severity**: Critical (DevOps)
- **Locations**: `.python-version` (3.13), `mise.toml` (3.14.3), `pyproject.toml` classifiers (3.10-3.12), CI workflows (3.14), Dockerfile (3.13), `CLAUDE.md` ("pinned to 3.13")

Developers using `.python-version` get 3.13, mise installs 3.14.3, Docker runs 3.13, CI tests 3.14, and classifiers claim only 3.10-3.12.

**Fix**: Decide on one authoritative Python version and align all sources.

---

## 2. Security Review

### 2.1 Findings by Severity

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| S1 | High | SSRF protection warning-only | `client.py:92-100` |
| S2 | Medium | Credentials stored as instance attributes in plaintext | `client.py:32-42` |
| S3 | Medium | Search query injection via unsanitized Elasticsearch input | `client.py:139-156` |
| S4 | Medium | HTTP health endpoint has no authentication | `server.py:2514-2524` |
| S5 | Medium | No size limit on base64 attachment upload data | `models.py:63-86` |
| S6 | Medium | Inconsistent HTML sanitization on output path | `server.py:193-203, 593-613` |
| S7 | Low | Error messages may leak internal information | `server.py:783`, `client.py:103` |
| S8 | Low | Docker secret file reading lacks path validation | `client.py:105-123` |
| S9 | Low | `MCP_HOST` can bind to all interfaces without warning | `server.py:2505`, `config.py:84` |
| S10 | Low | Overly permissive dependency version ranges | `pyproject.toml:24-30` |
| S11 | Low | MIME type not validated on attachment upload | `models.py:68` |
| S12 | Low | Stale cache never expires | `server.py:1808-1841` |
| S13 | Low | Resource handlers accept unvalidated string IDs | `server.py:2307,2352,2376` |

### 2.2 Credential Retention (S2)

`ZammadClient.__init__` stores `self.password`, `self.http_token`, and `self.oauth2_token` as plaintext instance attributes that persist for the server's lifetime. After passing credentials to `ZammadAPI(...)`, they should be deleted from `self`.

### 2.3 Search Query Injection (S3)

The `search_tickets()` method concatenates user-provided filter values directly into Elasticsearch query strings. A `state` value like `open OR owner.login:admin` could alter filter logic.

**Fix**: Wrap structured filter values in double quotes: `f'state.name:"{state}"'`.

### 2.4 Inconsistent Output Sanitization (S6)

`_escape_article_body()` escapes HTML for resource handlers, but `_format_ticket_detail_markdown()` renders article bodies without escaping. Ticket titles, organization notes, and user notes are also rendered unescaped.

**Fix**: Apply HTML escaping consistently in all formatting functions for all Zammad-sourced content.

### 2.5 Positive Security Observations

The following deserve recognition:

- **Pydantic StrictBaseModel with `extra="forbid"`** prevents unexpected field injection
- **Filename sanitization** strips path components via `os.path.basename()` and removes null bytes
- **Base64 validation** uses `validate=True` for strict encoding checks
- **Docker security**: Multi-stage build, non-root user, pinned base image digests, Docker secrets support
- **Response truncation** prevents excessive data return with JSON-aware truncation
- **Comprehensive security tooling**: Bandit, Semgrep, pip-audit, Safety, CodeQL, Codacy in CI
- **Dependency overrides** force secure versions of `authlib>=1.6.5` and `urllib3>=2.6.0`
- **URL scheme validation** only allows `http://` and `https://`

---

## 3. Code Quality Review

### 3.1 Architecture Issues

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| Q1 | Major | God-module anti-pattern (2559 lines) | `server.py` |
| Q2 | Major | Broad `except Exception` catches | `server.py:1043,1096,1162,1377` |
| Q3 | Major | Client returns `dict[str, Any]` everywhere | `client.py` (all methods) |
| Q4 | Major | Synchronous blocking calls in async architecture | `server.py` (all tool handlers) |
| Q5 | Major | Triplicated JSON response construction | `server.py:383,437,488` |
| Q6 | Major | Tests reimplement handler logic | `test_server.py:1807-1854` |
| Q7 | Minor | Module-level side effects on import | `server.py:2503-2510` |
| Q8 | Minor | Duplicate `main()` entry points | `server.py:2556`, `__main__.py:7` |
| Q9 | Minor | `hasattr` cache pattern instead of typed attributes | `server.py:1810-1841` |
| Q10 | Minor | `async def initialize` does no async work | `server.py:825` |
| Q11 | Minor | Stale `__version__` (0.1.0 vs 1.0.0) | `__init__.py:3` |
| Q12 | Minor | Unused `_ticket_id` parameter | `client.py:398` |
| Q13 | Minor | `docstring_templates.py` is dead code | `docstring_templates.py` |
| Q14 | Minor | `CLAUDE.md` claims non-existent sentinel pattern | `CLAUDE.md` |
| Q15 | Minor | Unimplemented date params exposed to users | `models.py:448-453` |

### 3.2 Synchronous Blocking in Async Context (Q4)

All 19 tool handlers are synchronous `def` functions making blocking HTTP calls via `zammad_py` (which uses `requests`). The `CLAUDE.md` describes an "async-first architecture," but the only true async functions are the lifespan context manager and health check.

The `zammad_get_ticket_stats` tool is especially concerning -- it paginates through up to 1000 pages of synchronous HTTP calls, blocking the entire event loop.

**Fix**: Wrap blocking client calls with `asyncio.to_thread()` for HTTP transport, or document that stdio transport is the recommended mode.

### 3.3 Client Type Safety (Q3)

Every method in `ZammadClient` returns `dict[str, Any]` or `list[dict[str, Any]]`. Pydantic validation only happens in the server layer via `Ticket(**ticket_data)` patterns. This means:

- No compile-time type safety in the client layer
- Data shape mismatches caught only at runtime
- Repetitive `Model(**data)` construction scattered through server.py

**Fix**: Have the client return Pydantic models directly, or at minimum use TypedDict stubs.

### 3.4 Test Quality Concerns

**Duplicated handler logic** (Q6): `TestResourceHandlers` contains tests that reimplement resource handler logic inline rather than calling the actual handlers. If the real handler changes, these tests still pass on their local copies.

**Missing edge-case tests**: The truncation functions (`_find_max_items_for_limit`, `_truncate_json_response`) are complex algorithms without comprehensive edge-case coverage.

---

## 4. Feature Gap Analysis

### 4.1 Current Inventory

- **19 tools**: Ticket CRUD, user/org search, article management, tag operations, system info
- **4 resources**: ticket, user, organization, queue
- **3 prompts**: analyze_ticket, draft_response, escalation_summary
- **zammad_py resources used**: 9 of 17 (53%)

### 4.2 CRUD Completeness

| Entity | Create | Read | Update | Delete | Coverage |
|--------|--------|------|--------|--------|----------|
| Tickets | Yes | Yes | Yes | No | 75% |
| Users | Yes | Yes | No | No | 50% |
| Organizations | No | Yes | No | No | 25% |
| Groups | No | Yes | No | No | 25% |
| Articles | Yes | Yes | No | No | 50% |
| Tags | Yes | Yes | -- | Yes | 75% |
| Attachments | -- | Yes | -- | Yes | 67% |

### 4.3 High Priority Missing Features

| # | Feature | Category | Complexity |
|---|---------|----------|------------|
| F1 | Knowledge Base integration (search, read, create) | Missing Feature | Moderate |
| F2 | User update (`zammad_update_user`) | Missing Feature | Simple |
| F3 | Ticket custom fields support | Enhancement | Moderate |
| F4 | Ticket links (get, add, remove) | Missing Feature | Simple |

### 4.4 Medium Priority Missing Features

| # | Feature | Category | Complexity |
|---|---------|----------|------------|
| F5 | Organization create & update | Missing Feature | Simple |
| F6 | Stats date filtering (start_date/end_date) | Enhancement | Moderate |
| F7 | Average response/resolution time computation | Enhancement | Moderate |
| F8 | Ticket merge | Missing Feature | Simple |
| F9 | Mentions / subscriptions | Missing Feature | Moderate |
| F10 | Online notifications | Missing Feature | Moderate |
| F11 | Overviews integration | Missing Feature | Moderate |
| F12 | Search sort options | Enhancement | Simple |
| F13 | Search by date range | Enhancement | Simple |
| F14 | Bulk ticket update | Enhancement | Moderate |
| F15 | SLA compliance reporting | Missing Feature | Moderate |
| F16 | Customer history prompt | Enhancement | Simple |
| F17 | Ticket triage prompt | Enhancement | Simple |
| F18 | Queue summary/dashboard prompt | Enhancement | Simple |
| F19 | Queue resource pagination (capped at 50) | Enhancement | Simple |
| F20 | Unified search across entity types | Enhancement | Moderate |
| F21 | Async wrapping for blocking I/O | Enhancement | Moderate |
| F22 | Client-side rate limiting | Enhancement | Moderate |

### 4.5 Low Priority Missing Features

| # | Feature | Category | Complexity |
|---|---------|----------|------------|
| F23 | Tag list management (`zammad_list_tags`) | Missing Feature | Simple |
| F24 | Roles (list, get) | Missing Feature | Simple |
| F25 | Calendars (list, get) | Missing Feature | Moderate |
| F26 | Checklists | Missing Feature | Moderate |
| F27 | Ticket delete | Enhancement | Simple |
| F28 | User deactivate | Enhancement | Simple |
| F29 | Webhook/real-time events | Integration | Complex |
| F30 | Agent workload reporting | Enhancement | Moderate |
| F31 | Cache TTL/invalidation | Enhancement | Simple |
| F32 | Audit logging | Enhancement | Simple |

### 4.6 Declared but Unimplemented Features

- `GetTicketStatsParams.start_date` / `end_date` -- "NOT YET IMPLEMENTED" in field descriptions
- `TicketStats.avg_first_response_time` / `avg_resolution_time` -- always returns `None`

---

## 5. Code Simplification Opportunities

### 5.1 Summary

| File | Lines | Simplification Potential | Est. Lines Removable |
|------|-------|------------------------|---------------------|
| `mcp_zammad/server.py` | 2,559 | High | ~400-550 |
| `tests/test_server.py` | 2,903 | High | ~400-600 |
| `tests/test_client*.py` | 697 | Medium | ~80-100 |
| `mcp_zammad/models.py` | 642 | Low | ~30 |
| `mcp_zammad/client.py` | 403 | Medium | ~40-60 |
| `mcp_zammad/docstring_templates.py` | 64 | High (dead code) | 85 |
| **Total** | **~7,800** | | **~1,000-1,400** |

### 5.2 Highest-Value Simplifications

**1. Generic Paginated JSON Formatter** (Impact: High, Risk: Low, ~55 lines saved)

Three nearly-identical functions (`_format_tickets_json`, `_format_users_json`, `_format_organizations_json`) build the same pagination response dict. Replace with a single generic function accepting `items: list[BaseModel]`.

**2. Test Tool-Capture Fixture** (Impact: High, Risk: Low, ~70 lines saved)

17 occurrences of the same 5-line boilerplate for tool capture setup in `test_server.py`. Extract to a shared fixture.

**3. Test Mock Data Factories** (Impact: Medium, Risk: Low, ~100-150 lines saved)

`"created_at": "2024-01-01T00:00:00Z"` appears 41 times in test_server.py. Create factory fixtures for groups, states, and priorities.

**4. Remove Dead Code** (Impact: Medium, Risk: Low, ~85 lines saved)

`docstring_templates.py` and its test file are never imported. Remove entirely.

**5. Docstring Compression** (Impact: High readability, Risk: Low, ~150-250 lines saved)

The "ticket_id must be the internal database ID" note appears 9 times verbatim. The three `list_*` tool docstrings are copy-paste of each other. Extract shared notes into constants.

**6. Response Format Dispatch Helper** (Impact: Medium, Risk: Low, ~25-35 lines saved)

9 tools repeat the same `if params.response_format == ResponseFormat.JSON: ... else: ... return truncate_response(result)` pattern.

### 5.3 Structural Simplification

**Module Splitting** (Impact: High maintainability, Risk: Medium)

Split `server.py` from a 2,559-line monolith into:
- `server.py` (~500 lines) - Core MCP server class and setup
- `tools/ticket_tools.py` - Ticket-related tool handlers
- `tools/user_org_tools.py` - User/organization tool handlers
- `tools/system_tools.py` - System info tools
- `formatters.py` - All `_format_*` functions

### 5.4 Dependency Cleanup

- `httpx>=0.25.0` is listed as a dependency but never imported in source code (0 usages)
- `requests` is only used for exception types (`requests.exceptions.RequestException`)

---

## 6. DevOps & Infrastructure Review

### 6.1 Findings by Severity

| # | Severity | Category | Finding |
|---|----------|----------|---------|
| D1 | Critical | DX | Python version inconsistency across 5 sources |
| D2 | Major | CI/CD | No dedicated linting/type-checking CI workflow |
| D3 | Major | CI/CD | No Python version matrix testing (claims 3.10+, tests only 3.14) |
| D4 | Major | Docker | No HEALTHCHECK instruction in Dockerfile |
| D5 | Major | CI/CD | No automated release workflow (manual process) |
| D6 | Minor | CI/CD | Coverage threshold mismatch (65% in CI vs 86-90% elsewhere) |
| D7 | Minor | Config | Both Dependabot AND Renovate configured simultaneously |
| D8 | Minor | Docs | SECURITY.md stale (shows 0.1.x supported, project at 1.1.0) |
| D9 | Minor | Docs | ARCHITECTURE.md references "16 tools" (now 19) |
| D10 | Minor | Docs | Bug report template has irrelevant browser/smartphone fields |
| D11 | Minor | DX | Setup scripts use `uv pip install` instead of `uv sync` |
| D12 | Minor | DX | `prek` used but CONTRIBUTING.md documents `pre-commit` commands |
| D13 | Minor | CI/CD | quality-check.sh swallows semgrep/pip-audit exit codes |
| D14 | Minor | Monitoring | Plain text logging only; no structured JSON log option |
| D15 | Minor | Monitoring | Health endpoint lacks depth (doesn't verify Zammad connectivity) |

### 6.2 Positive DevOps Observations

- **Actions pinned to commit SHAs** - Prevents supply chain attacks through mutable tags
- **Fork-safe workflow design** - Guards against failures in forked repos
- **Multi-stage Docker build** - Non-root user, slim base, proper caching
- **Comprehensive pre-commit hooks** - Ruff, mypy, Bandit, Semgrep, pip-audit, markdown linting
- **Dependency override for CVEs** - Proactively forces secure versions of transitive deps
- **Excellent documentation suite** - README, CONTRIBUTING, SECURITY, ARCHITECTURE, CLAUDE.md
- **mise task ecosystem** - Well-organized for development workflows
- **PEP 723 inline metadata** - UV scripts use self-contained dependency management
- **CodeRabbit configuration** - One of the most comprehensive configurations seen (290 lines)

### 6.3 No Lint/Type-Check in CI (D2)

Linting and type-checking are only enforced via pre-commit hooks locally. If a contributor bypasses pre-commit with `--no-verify`, malformatted code can be merged.

**Fix**: Add a `lint.yml` workflow running `ruff check`, `ruff format --check`, and `mypy mcp_zammad/`.

### 6.4 Coverage Threshold Mismatch (D6)

- `tests.yml` enforces: 65%
- `scripts/quality-check.sh` enforces: 86%
- `CLAUDE.md` states: 90%+
- `CONTRIBUTING.md` states: 80%

A regression from 90% to 66% would pass CI silently.

**Fix**: Raise CI threshold to at least 85%.

---

## 7. Prioritized Action Plan

### Phase 1: Critical Fixes (Immediate)

| # | Action | Category | Effort |
|---|--------|----------|--------|
| 1 | Remove input-side HTML escaping from Pydantic validators | Bug Fix | Small |
| 2 | Convert SSRF warnings to blocking behavior | Security | Small |
| 3 | Resolve Python version inconsistency | DevOps | Small |
| 4 | Escape search query filter values for Elasticsearch | Security | Small |
| 5 | Add consistent HTML escaping to all output formatting | Security | Medium |

### Phase 2: High-Impact Improvements (Short-Term)

| # | Action | Category | Effort |
|---|--------|----------|--------|
| 6 | Add linting/type-checking to CI | DevOps | Small |
| 7 | Raise CI coverage threshold to 85% | DevOps | Small |
| 8 | Add base64 upload size limits | Security | Small |
| 9 | Delete credentials from client after initialization | Security | Small |
| 10 | Remove dead `docstring_templates.py` | Simplification | Small |
| 11 | Remove unused `httpx` dependency | Simplification | Small |
| 12 | Fix `__version__` in `__init__.py` | Quality | Small |
| 13 | Extract generic paginated JSON formatter | Simplification | Small |
| 14 | Add Docker HEALTHCHECK | DevOps | Small |

### Phase 3: Feature Development (Medium-Term)

| # | Action | Category | Effort |
|---|--------|----------|--------|
| 15 | Add `zammad_update_user` tool | Feature | Small |
| 16 | Add `zammad_create_organization` and `zammad_update_organization` | Feature | Small |
| 17 | Add ticket links (get, add, remove) | Feature | Small |
| 18 | Knowledge Base integration | Feature | Medium |
| 19 | Ticket custom fields support | Feature | Medium |
| 20 | Implement stats date filtering | Feature | Medium |
| 21 | Add search sort options and date range filtering | Feature | Small |

### Phase 4: Architecture Evolution (Long-Term)

| # | Action | Category | Effort |
|---|--------|----------|--------|
| 22 | Split server.py into tool modules | Simplification | Medium |
| 23 | Wrap blocking calls with asyncio.to_thread() | Quality | Medium |
| 24 | Return Pydantic models from client layer | Quality | Large |
| 25 | Consolidate test fixtures and remove duplicated handler tests | Quality | Medium |
| 26 | Add Python version matrix to CI | DevOps | Small |
| 27 | Add automated release workflow | DevOps | Medium |
| 28 | Add structured JSON logging option | DevOps | Small |
| 29 | Implement cache TTL/invalidation | Feature | Small |
| 30 | Add client-side rate limiting | Feature | Medium |

---

## Appendix A: Files Reviewed

### Production Code
| File | Lines | Purpose |
|------|-------|---------|
| `mcp_zammad/server.py` | 2,559 | MCP server, tools, resources, prompts, formatting |
| `mcp_zammad/models.py` | 642 | Pydantic models for validation |
| `mcp_zammad/client.py` | 403 | Zammad API wrapper |
| `mcp_zammad/config.py` | 84 | Transport configuration |
| `mcp_zammad/docstring_templates.py` | 64 | Unused docstring template system |
| `mcp_zammad/__main__.py` | 28 | Entry point |
| `mcp_zammad/__init__.py` | 3 | Package init |

### Test Code
| File | Lines | Purpose |
|------|-------|---------|
| `tests/test_server.py` | 2,903 | Server tool/resource/prompt tests |
| `tests/test_client_methods.py` | 480 | Client method tests |
| `tests/test_models.py` | 237 | Pydantic model tests |
| `tests/test_client.py` | 216 | Client configuration tests |
| `tests/test_main.py` | 88 | Entry point tests |
| `tests/test_config.py` | 77 | Config tests |
| `tests/conftest.py` | 68 | Shared fixtures |
| `tests/test_docstring_templates.py` | 20 | Dead code tests |

### Configuration & DevOps
| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, tooling |
| `Dockerfile` | Multi-stage container build |
| `.pre-commit-config.yaml` | Pre-commit hooks (prek) |
| `.github/workflows/tests.yml` | CI test workflow |
| `.github/workflows/security-scan.yml` | Security scanning |
| `.github/workflows/docker-publish.yml` | Docker image publishing |
| `mise.toml` | Development task runner |
| `.devcontainer/devcontainer.json` | Codespaces configuration |
| `.coderabbit.yaml` | CodeRabbit review configuration |
| `.codacy.yml` | Codacy analysis configuration |
| `renovate.json` | Dependency update automation |
| `cliff.toml` | Changelog generation |
| `scripts/quality-check.sh` | Local quality gate |

## Appendix B: Methodology

This review was conducted by 5 specialized analysis agents running in parallel:

1. **Security Auditor**: Focused on authentication, input validation, SSRF, XSS, file security, Docker hardening, dependency vulnerabilities, and error information leakage.

2. **Code Quality Reviewer**: Analyzed architecture, error handling patterns, type safety, async patterns, code duplication, API design, test quality, and Python best practices.

3. **Feature Gap Analyst**: Cataloged existing tools/resources/prompts, mapped against the full Zammad REST API surface and zammad_py library capabilities, identified missing CRUD operations, pagination gaps, and potential new prompts/resources.

4. **Simplification Specialist**: Measured code duplication, identified dead code, analyzed test boilerplate, reviewed dependency necessity, and estimated lines removable with specific refactoring patterns.

5. **DevOps Reviewer**: Evaluated CI/CD pipelines, Docker configuration, developer experience, pre-commit hooks, dependency management, release process, documentation quality, and monitoring/observability.

Each agent independently read all relevant source files and produced findings with severity ratings, file locations, and recommendations. This report synthesizes and deduplicates their findings into a unified action plan.
