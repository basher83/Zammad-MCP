# Phase 3: Complete Legacy Wrapper Removal - Execution Plan

**Status**: 📋 Ready for execution
**Target Release**: v1.0.0 (Breaking change)
**Estimated Time**: ~5 hours
**Created**: 2025-10-17

---

## Overview

Migrate all tests from legacy wrapper functions to `ZammadMCPServer` class pattern, then remove ~320 lines of duplicate legacy code from server.py.

## Scope

### Code to Remove

- **Lines 780-1098** in `mcp_zammad/server.py`:
  - 19 legacy wrapper functions
  - Module-level globals (`zammad_client`, `_UNINITIALIZED`)
  - `async def initialize()` function
  - Total: ~320 lines of duplicate code

### Tests to Migrate

- **25 tests** using legacy wrappers (convert from async to sync where appropriate)
- **18 tests** to remove (legacy error tests no longer relevant)

### Documentation

- Remove completed migration guides
- Update ARCHITECTURE.md
- Add breaking change notice to CHANGELOG.md

---

## Detailed Changes

### 1. Test File Migration: `tests/test_server.py`

#### A. Update Imports (Lines 14-38)

**Current imports to remove:**

```python
from mcp_zammad.server import (
    _UNINITIALIZED,
    ZammadMCPServer,
    add_article,
    add_ticket_tag,
    create_ticket,
    download_attachment,
    get_article_attachments,
    get_current_user,
    get_organization,
    get_ticket,
    get_ticket_stats,
    get_user,
    initialize,
    list_groups,
    list_ticket_priorities,
    list_ticket_states,
    main,
    mcp,
    remove_ticket_tag,
    search_organizations,
    search_tickets,
    search_users,
    update_ticket,
)
```

**New imports (keep only):**

```python
from mcp_zammad.server import ZammadMCPServer, main, mcp
```

#### B. Migration Patterns

**Old Pattern (Legacy - to remove):**

```python
@pytest.mark.asyncio
async def test_search_tickets_tool(mock_zammad_client, sample_ticket_data):
    mock_instance, _ = mock_zammad_client
    mock_instance.search_tickets.return_value = [sample_ticket_data]

    await initialize()
    server.zammad_client = mock_instance

    result = search_tickets(state="open")
    assert len(result) == 1
```

**New Pattern (Option A - Direct client testing):**

```python
def test_search_tickets_tool(mock_zammad_client, sample_ticket_data):
    mock_instance, _ = mock_zammad_client
    mock_instance.search_tickets.return_value = [sample_ticket_data]

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    tickets_data = client.search_tickets(state="open")
    result = [Ticket(**t) for t in tickets_data]

    assert len(result) == 1
    mock_instance.search_tickets.assert_called_once_with(
        query=None, state="open", priority=None, group=None,
        owner=None, customer=None, page=1, per_page=25
    )
```

**New Pattern (Option B - Tool function testing):**

```python
def test_search_tickets_tool(mock_zammad_client, sample_ticket_data):
    mock_instance, _ = mock_zammad_client
    mock_instance.search_tickets.return_value = [sample_ticket_data]

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance

    # Capture tools as they're registered
    test_tools = {}
    original_tool = server_inst.mcp.tool
    def capture_tool(name=None):
        def decorator(func):
            test_tools[func.__name__ if name is None else name] = func
            return original_tool(name)(func)
        return decorator

    server_inst.mcp.tool = capture_tool
    server_inst._setup_ticket_tools()

    result = test_tools['search_tickets'](state="open")
    assert len(result) == 1
```

**Decision**: Use **Option A** for most tests (simpler, cleaner), **Option B** only where tool-specific behavior needs testing.

#### C. Tests to Migrate (25 tests)

| # | Test Name | Current Lines | Action | Notes |
|---|-----------|---------------|--------|-------|
| 1 | `test_server_initialization` | 171-206 | Keep async, update pattern | Remove `await initialize()` calls |
| 2 | `test_initialization_failure` | 221-229 | Keep async | Update to test `ZammadMCPServer.initialize()` |
| 3 | `test_tool_without_client` | 232-246 | Convert to sync | Test `server.get_client()` raises RuntimeError |
| 4 | `test_search_tickets_with_filters` | 263-296 | Convert to sync | Use Option A pattern |
| 5 | `test_search_tickets_pagination` | 309-325 | Convert to sync | Use Option A pattern |
| 6 | `test_get_ticket_with_invalid_id` | 332-344 | Convert to sync | Use Option A pattern |
| 7 | `test_create_ticket_with_invalid_data` | 348-360 | Convert to sync | Use Option A pattern |
| 8 | `test_search_with_malformed_response` | 364-385 | Convert to sync | Use Option A pattern |
| 9 | `test_search_tickets_tool` | 392-415 | Convert to sync | Use Option A pattern |
| 10 | `test_get_ticket_tool` | 419-441 | Convert to sync | Use Option A pattern |
| 11 | `test_create_ticket_tool` | 445-482 | Convert to sync | Use Option A pattern |
| 12 | `test_add_article_tool` | 486-503 | Convert to sync | Use Option A pattern |
| 13 | `test_get_user_tool` | 507-522 | Convert to sync | Use Option A pattern |
| 14 | `test_tag_operations` | 526-545 | Convert to sync | Use Option A pattern |
| 15 | `test_update_ticket_tool` | 549-575 | Convert to sync | Use Option A pattern |
| 16 | `test_get_organization_tool` | 579-594 | Convert to sync | Use Option A pattern |
| 17 | `test_search_organizations_tool` | 598-619 | Convert to sync | Use Option A pattern |
| 18 | `test_list_groups_tool` | 623-663 | Convert to sync | Use Option A pattern |
| 19 | `test_list_ticket_states_tool` | 667-707 | Convert to sync | Use Option A pattern |
| 20 | `test_list_ticket_priorities_tool` | 711-750 | Convert to sync | Use Option A pattern |
| 21 | `test_get_current_user_tool` | 755-773 | Convert to sync | Use Option A pattern, adjust call count |
| 22 | `test_search_users_tool` | 777-799 | Convert to sync | Use Option A pattern |
| 23 | `test_get_ticket_stats_tool` | 803-861 | Convert to sync | Use Option A pattern |
| 24 | `test_get_article_attachments_legacy_function` | 1901-1916 | Convert to sync | Rename to remove "legacy" |
| 25 | `test_download_attachment_legacy_function` | 1919-1932 | Convert to sync | Rename to remove "legacy" |

#### D. Tests to Remove (18 tests)

**Lines 1358-1487** - All legacy error tests:

- `test_legacy_search_tickets_without_client`
- `test_legacy_get_ticket_without_client`
- `test_legacy_create_ticket_without_client`
- `test_legacy_add_article_without_client`
- `test_legacy_get_user_without_client`
- `test_legacy_add_ticket_tag_without_client`
- `test_legacy_remove_ticket_tag_without_client`
- `test_legacy_update_ticket_without_client`
- `test_legacy_get_organization_without_client`
- `test_legacy_search_organizations_without_client`
- `test_legacy_list_groups_without_client`
- `test_legacy_list_ticket_states_without_client`
- `test_legacy_list_ticket_priorities_without_client`
- `test_legacy_get_current_user_without_client`
- `test_legacy_search_users_without_client`
- `test_legacy_get_ticket_stats_without_client`
- Plus 2 more attachment-related legacy tests

**Rationale**: These tests verified error handling for uninitialized module-level client. With class-based approach, this is covered by `test_get_client_error` (line 1075).

#### E. Fixture Updates

**Update `reset_client` fixture (lines 44-48):**

```python
# OLD - Remove this fixture entirely
@pytest.fixture
def reset_client():
    """Fixture to reset and restore the global client."""
    original_client = server.zammad_client
    yield
    server.zammad_client = original_client
```

**Reason**: No longer needed without module-level global.

---

### 2. Server File: `mcp_zammad/server.py`

#### Lines to Remove: 780-1098

**Section 1: Module-level globals (lines 780-782)**

```python
# Legacy constants and functions for backward compatibility with tests
_UNINITIALIZED = None
zammad_client = None
```

**Section 2: Initialize function (lines 785-790)**

```python
async def initialize() -> None:
    """Initialize the Zammad client (legacy wrapper for test compatibility)."""
    await server.initialize()
    # Update the module-level client reference
    globals()["zammad_client"] = server.client
```

**Section 3: All 19 legacy wrapper functions (lines 792-1098)**

- `search_tickets()`
- `get_ticket()`
- `create_ticket()`
- `add_article()`
- `get_article_attachments()`
- `download_attachment()`
- `get_user()`
- `add_ticket_tag()`
- `remove_ticket_tag()`
- `update_ticket()`
- `get_organization()`
- `search_organizations()`
- `list_groups()`
- `list_ticket_states()`
- `list_ticket_priorities()`
- `get_current_user()`
- `search_users()`
- `get_ticket_stats()`

**Keep:**

- Lines 1-779: All `ZammadMCPServer` class implementation
- Lines 1101-1103: `def main()` function

---

### 3. Documentation: `ARCHITECTURE.md`

#### Remove Section (Lines 377-416)

**Section to delete:**

```markdown
## Legacy Code Deprecation

### Current State
...
### Deprecation Strategy
...
### Benefits of Removal
...
### Detailed Plan
...
```

**Rationale**: Deprecation is complete, no longer relevant.

---

### 4. Documentation: Delete Files

#### A. Delete `docs/MIGRATION_GUIDE.md`

- Migration is complete
- Keep in git history for reference
- No longer needed in codebase

#### B. Delete `docs/LEGACY_WRAPPER_DEPRECATION.md`

- Deprecation is complete
- Keep in git history for reference
- No longer needed in codebase

---

### 5. Changelog: `CHANGELOG.md`

#### Add to Unreleased Section

```markdown
### Changed

- **BREAKING**: Removed legacy wrapper functions from `mcp_zammad.server` module (v1.0.0)
  - All 19 legacy wrapper functions have been removed
  - Tests migrated to use `ZammadMCPServer` class directly
  - Removed ~320 lines of duplicated code
  - If you were importing functions like `initialize()`, `search_tickets()`, etc. from `mcp_zammad.server`, you must now use the `ZammadMCPServer` class
  - See migration examples in git history at docs/MIGRATION_GUIDE.md (removed in v1.0.0)
```

---

## Execution Checklist

### Pre-Migration

- [ ] Review this plan with stakeholders
- [ ] Create feature branch: `git checkout -b phase3-remove-legacy-wrappers`
- [ ] Ensure clean working directory: `git status`
- [ ] Run baseline tests: `uv run pytest tests/` (72 tests should pass)
- [ ] Check baseline coverage: `uv run pytest --cov=mcp_zammad` (should be 90%+)

### Migration Steps

#### Step 1: Update Test Imports

- [ ] Edit `tests/test_server.py` lines 14-38
- [ ] Remove all legacy function imports
- [ ] Keep only: `ZammadMCPServer`, `main`, `mcp`
- [ ] Run: `uv run pytest tests/test_server.py::test_server_initialization -v` to verify imports

#### Step 2: Remove Legacy Error Tests

- [ ] Delete lines 1358-1487 in `tests/test_server.py`
- [ ] Verify deletion: `rg "test_legacy_" tests/` should return no results

#### Step 3: Migrate Async Tests (Batch 1: Lines 170-230)

- [ ] Update `test_server_initialization`
- [ ] Update `test_initialization_failure`
- [ ] Update `test_tool_without_client`
- [ ] Run: `uv run pytest tests/test_server.py::test_server_initialization -v`
- [ ] Run: `uv run pytest tests/test_server.py::test_initialization_failure -v`
- [ ] Run: `uv run pytest tests/test_server.py::test_tool_without_client -v`

#### Step 4: Migrate Parametrized Tests (Batch 2: Lines 263-325)

- [ ] Convert `test_search_tickets_with_filters` to sync
- [ ] Convert `test_search_tickets_pagination` to sync
- [ ] Run: `uv run pytest tests/test_server.py::test_search_tickets_with_filters -v`
- [ ] Run: `uv run pytest tests/test_server.py::test_search_tickets_pagination -v`

#### Step 5: Migrate Error Tests (Batch 3: Lines 332-385)

- [ ] Convert `test_get_ticket_with_invalid_id` to sync
- [ ] Convert `test_create_ticket_with_invalid_data` to sync
- [ ] Convert `test_search_with_malformed_response` to sync
- [ ] Run: `uv run pytest tests/test_server.py -k "invalid" -v`

#### Step 6: Migrate Tool Tests (Batch 4: Lines 392-575)

- [ ] Convert `test_search_tickets_tool` to sync
- [ ] Convert `test_get_ticket_tool` to sync
- [ ] Convert `test_create_ticket_tool` to sync
- [ ] Convert `test_add_article_tool` to sync
- [ ] Convert `test_get_user_tool` to sync
- [ ] Convert `test_tag_operations` to sync
- [ ] Convert `test_update_ticket_tool` to sync
- [ ] Run: `uv run pytest tests/test_server.py -k "tool" -v`

#### Step 7: Migrate Org/System Tests (Batch 5: Lines 579-861)

- [ ] Convert `test_get_organization_tool` to sync
- [ ] Convert `test_search_organizations_tool` to sync
- [ ] Convert `test_list_groups_tool` to sync
- [ ] Convert `test_list_ticket_states_tool` to sync
- [ ] Convert `test_list_ticket_priorities_tool` to sync
- [ ] Convert `test_get_current_user_tool` to sync
- [ ] Convert `test_search_users_tool` to sync
- [ ] Convert `test_get_ticket_stats_tool` to sync
- [ ] Run: `uv run pytest tests/test_server.py -k "organization or groups or states or priorities or current_user or search_users or stats" -v`

#### Step 8: Migrate Attachment Tests (Batch 6: Lines 1901-1932)

- [ ] Convert `test_get_article_attachments_legacy_function` to sync (rename)
- [ ] Convert `test_download_attachment_legacy_function` to sync (rename)
- [ ] Run: `uv run pytest tests/test_server.py -k "attachment" -v`

#### Step 9: Remove Unused Fixtures

- [ ] Delete `reset_client` fixture (lines 44-48)
- [ ] Run: `uv run pytest tests/test_server.py -v` (all tests)

#### Step 10: Remove Legacy Code from Server

- [ ] Delete lines 780-1098 in `mcp_zammad/server.py`
- [ ] Verify `def main()` remains at bottom
- [ ] Run: `uv run pytest tests/test_server.py -v` (should still pass)
- [ ] Verify no imports remain: `rg "from mcp_zammad.server import initialize" --type py`

#### Step 11: Update Documentation

- [ ] Delete `docs/MIGRATION_GUIDE.md`
- [ ] Delete `docs/LEGACY_WRAPPER_DEPRECATION.md`
- [ ] Edit `ARCHITECTURE.md` - remove lines 377-416
- [ ] Edit `CHANGELOG.md` - add breaking change notice

### Verification

#### Automated Tests

- [ ] Run full test suite: `uv run pytest tests/`
  - Expected: All tests pass (count may be ~54-60 after removing 18 legacy tests)
- [ ] Check coverage: `uv run pytest --cov=mcp_zammad --cov-report=term-missing`
  - Expected: Coverage ≥90% (should improve slightly)
- [ ] Run type checks: `uv run mypy mcp_zammad`
  - Expected: No errors
- [ ] Run linter: `uv run ruff check mcp_zammad tests`
  - Expected: No errors
- [ ] Run formatter check: `uv run ruff format --check mcp_zammad tests`
  - Expected: All files formatted
- [ ] Run quality check script: `./scripts/quality-check.sh`
  - Expected: All checks pass

#### Manual Verification

- [ ] Search for legacy imports: `rg "from mcp_zammad.server import (initialize|get_ticket|search_tickets|add_article|get_user)" --type py`
  - Expected: No matches (except in deleted docs)
- [ ] Search for module-level client: `rg "server.zammad_client" --type py`
  - Expected: No matches
- [ ] Check server.py structure: `rg "^def |^async def |^class " mcp_zammad/server.py`
  - Expected: Only `class ZammadMCPServer` and `def main()`
- [ ] Verify line count reduction: `wc -l mcp_zammad/server.py`
  - Expected: ~1100 lines → ~780 lines (reduction of ~320 lines)

#### Docker Build

- [ ] Build Docker image: `docker build -t test-zammad-mcp .`
  - Expected: Successful build
- [ ] Run container test: `docker run --rm test-zammad-mcp python -c "from mcp_zammad.server import ZammadMCPServer; print('OK')"`
  - Expected: Output "OK"

### Post-Migration

- [ ] Review all changes: `git diff main`
- [ ] Stage changes: `git add -A`
- [ ] Commit: `git commit -m "feat!: remove legacy wrapper functions (BREAKING CHANGE)"`
- [ ] Push branch: `git push -u origin phase3-remove-legacy-wrappers`
- [ ] Create PR with this plan linked
- [ ] Tag as v1.0.0 after merge

---

## Success Metrics

- ✅ **Code Reduction**: ~320 lines removed from server.py
- ✅ **Test Count**: ~54-60 tests (down from 72, after removing 18 legacy tests)
- ✅ **Coverage**: Maintained or improved (≥90%)
- ✅ **Architecture**: Single, consistent pattern (class-based only)
- ✅ **Type Safety**: No module-level globals or sentinel patterns
- ✅ **Build**: Docker image builds successfully
- ✅ **Quality**: All checks pass

---

## Rollback Plan

If critical issues are discovered post-migration:

1. **Immediate**: Revert commit

   ```bash
   git revert HEAD
   git push
   ```

1. **Document Issue**: Create GitHub issue with:
   - Error messages
   - Failed test output
   - Steps to reproduce

1. **Analysis**: Determine if issue is:
   - Test migration error (fix tests, try again)
   - Architectural problem (need redesign)
   - External dependency issue (wait for fix)

1. **Re-attempt**: Fix issues and re-run migration

---

## Notes

- **Estimated time**: 5 hours total
  - Test migration: 3-4 hours
  - Code removal: 15 minutes
  - Documentation: 30 minutes
  - Verification: 30-45 minutes

- **Breaking change**: This is a major version bump (v1.0.0)

- **Migration impact**: Only affects:
  - Internal test suite (already migrated)
  - Anyone directly importing legacy functions (unlikely - only for testing)
  - MCP users are NOT affected (protocol unchanged)

---

**Last Updated**: 2025-10-17
**Author**: Claude Code
**Review Status**: Pending
