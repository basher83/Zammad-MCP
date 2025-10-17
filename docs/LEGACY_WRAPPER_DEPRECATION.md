# Legacy Wrapper Deprecation Plan

## Executive Summary

This document outlines the deprecation strategy for the 19 legacy wrapper functions in `mcp_zammad/server.py` (lines 763-1098). These functions were created during the FastMCP migration to maintain backward compatibility with existing tests, but represent duplicated code that should be phased out.

## Current State

### Legacy Functions Inventory

The following module-level functions are marked for deprecation:

**Core Functions:**

- `initialize()` - Initialize Zammad client (wrapper for `ZammadMCPServer.initialize()`)
- `get_zammad_client` reference via sentinel pattern

**Ticket Operations (8 functions):**

- `search_tickets()` - Search for tickets
- `get_ticket()` - Get ticket by ID
- `create_ticket()` - Create new ticket
- `update_ticket()` - Update existing ticket
- `add_article()` - Add article to ticket
- `add_ticket_tag()` - Add tag to ticket
- `remove_ticket_tag()` - Remove tag from ticket
- `get_ticket_stats()` - Get ticket statistics

**Attachment Operations (2 functions):**

- `get_article_attachments()` - List article attachments
- `download_attachment()` - Download attachment

**User Operations (3 functions):**

- `get_user()` - Get user by ID
- `search_users()` - Search users
- `get_current_user()` - Get current authenticated user

**Organization Operations (2 functions):**

- `get_organization()` - Get organization by ID
- `search_organizations()` - Search organizations

**System Operations (3 functions):**

- `list_groups()` - List all groups
- `list_ticket_states()` - List ticket states
- `list_ticket_priorities()` - List priorities

### Architecture Rationale

**Why These Functions Exist:**

- Created during migration from module-level architecture to class-based `ZammadMCPServer`
- Maintain backward compatibility for existing test suite
- Use module-level `zammad_client` global variable (sentinel pattern)

**Why They Should Be Deprecated:**

- **Code Duplication**: ~335 lines of duplicated functionality
- **Maintenance Burden**: Every change to MCP tools requires updating wrappers
- **Architectural Inconsistency**: Mix of class-based and module-level patterns
- **No External Users**: Only used internally by test suite, not by MCP protocol

## Deprecation Timeline

### Phase 1: Immediate (Current Release - Completed ✅)

**Status:** COMPLETED
**Release:** Unreleased (included in issue #12 fix)

- ✅ Fix correctness issues (get_ticket_stats pagination)
- ✅ Add performance metrics and logging
- ✅ Update tests to verify correct behavior
- ✅ Document optimization in ARCHITECTURE.md

### Phase 2: Deprecation Warnings (v0.2.0)

**Target Release:** v0.2.0
**Timeline:** Next minor release after issue #12 fix
**Breaking Changes:** None (warnings only)

**Implementation Tasks:**

1. **Add Deprecation Warnings to All Legacy Functions**

   ```python
   import warnings

   def search_tickets(*args, **kwargs):
       """Search for tickets (DEPRECATED - use ZammadMCPServer)."""
       warnings.warn(
           "Legacy wrapper functions are deprecated and will be removed in v1.0.0. "
           "Use ZammadMCPServer class directly instead. "
           "See docs/MIGRATION_GUIDE.md for details.",
           DeprecationWarning,
           stacklevel=2
       )
       if zammad_client is None:
           raise RuntimeError("Zammad client not initialized")
       # ... existing implementation
   ```

2. **Update Documentation**
   - Add deprecation notices to docstrings
   - Create MIGRATION_GUIDE.md with migration examples
   - Update CHANGELOG.md with deprecation announcement
   - Add FAQ section addressing common migration questions

3. **Update Tests to Suppress Warnings**

   ```python
   @pytest.mark.filterwarnings("ignore::DeprecationWarning")
   async def test_legacy_search_tickets():
       # ... test implementation
   ```

4. **Communication**
   - Add deprecation notice to README.md
   - Create GitHub discussion thread
   - Add warning to CLAUDE.md

**Acceptance Criteria:**

- [ ] All 19 legacy functions emit DeprecationWarning
- [ ] MIGRATION_GUIDE.md created with examples
- [ ] All existing tests still pass (with warnings suppressed)
- [ ] CHANGELOG.md documents deprecation
- [ ] README.md includes deprecation notice

### Phase 3: Removal (v1.0.0)

**Target Release:** v1.0.0 (Major version bump)
**Timeline:** 3-6 months after v0.2.0 release
**Breaking Changes:** YES - legacy functions removed

**Pre-Removal Checklist:**

1. **Test Migration (Critical)**
   - Migrate all tests from legacy wrappers to `ZammadMCPServer` class
   - Ensure no external code depends on legacy wrappers
   - Run full test suite with legacy functions removed
   - Update test documentation

2. **Remove Legacy Code**
   - Delete lines 763-1098 from `mcp_zammad/server.py`
   - Remove `_UNINITIALIZED` sentinel constant
   - Remove `zammad_client` global variable
   - Clean up imports and type hints

3. **Update Documentation**
   - Remove deprecation notices (no longer applicable)
   - Update ARCHITECTURE.md to reflect simplified design
   - Update examples in README.md
   - Archive MIGRATION_GUIDE.md (keep for reference)

4. **Verification**
   - All tests pass without legacy wrappers
   - Test coverage maintained or improved
   - No references to deprecated functions in code or docs
   - Docker image builds successfully

**Acceptance Criteria:**

- [ ] All legacy wrapper functions removed
- [ ] Test suite migrated to ZammadMCPServer class
- [ ] All tests pass (coverage >90%)
- [ ] Documentation updated
- [ ] CHANGELOG.md documents breaking changes
- [ ] Release notes include migration guide link

## Migration Guide Preview

### Before (Legacy Wrapper - Deprecated)

```python
from mcp_zammad import server

# Initialize
await server.initialize()

# Use legacy wrapper
tickets = server.search_tickets(state="open")
user = server.get_user(123)
```

### After (Recommended Approach)

```python
from mcp_zammad.server import ZammadMCPServer

# Create server instance
mcp_server = ZammadMCPServer()
await mcp_server.initialize()

# Get client
client = mcp_server.get_client()

# Use client methods directly
tickets_data = client.search_tickets(state="open")
tickets = [Ticket(**t) for t in tickets_data]

user_data = client.get_user(123)
user = User(**user_data)
```

### Test Migration Example

**Before:**

```python
from mcp_zammad.server import get_ticket, initialize

async def test_old_way():
    await initialize()
    ticket = get_ticket(123)
    assert ticket.id == 123
```

**After:**

```python
from mcp_zammad.server import ZammadMCPServer
from unittest.mock import Mock

def test_new_way():
    server = ZammadMCPServer()
    server.client = Mock()
    server.client.get_ticket.return_value = {"id": 123, ...}

    client = server.get_client()
    ticket_data = client.get_ticket(123)
    ticket = Ticket(**ticket_data)
    assert ticket.id == 123
```

## Risk Assessment

### Low Risk

- **Internal-Only Impact**: Only affects test suite, not end users
- **Gradual Migration**: 6+ month timeline allows thorough testing
- **Clear Communication**: Deprecation warnings and docs provide guidance

### Medium Risk

- **Test Suite Complexity**: 72 tests need migration (manageable)
- **Documentation Updates**: Multiple files need updates

### Mitigation Strategies

1. **Extended Timeline**: 3-6 months between v0.2.0 and v1.0.0
2. **Comprehensive Migration Guide**: Detailed examples for all use cases
3. **Automated Testing**: CI/CD catches any breaking changes
4. **Rollback Plan**: Keep legacy code in git history if needed

## Success Metrics

### Phase 2 (v0.2.0)

- ✅ Zero regression in functionality
- ✅ All tests pass with deprecation warnings
- ✅ Migration guide published
- ✅ Community awareness (GitHub discussion, README notice)

### Phase 3 (v1.0.0)

- ✅ 335 lines of code removed
- ✅ Zero legacy wrapper references in codebase
- ✅ Test coverage maintained (>90%)
- ✅ Zero reported issues from migration

## Action Items

### Immediate (Before v0.2.0 Release)

1. Review and approve this deprecation plan
2. Create tracking issue on GitHub (#TBD)
3. Add milestone for v0.2.0 and v1.0.0

### For v0.2.0 Development

1. Implement deprecation warnings (estimated: 2-3 hours)
2. Create MIGRATION_GUIDE.md (estimated: 3-4 hours)
3. Update all documentation (estimated: 2 hours)
4. Test deprecation workflow (estimated: 1 hour)

### For v1.0.0 Development

1. Migrate all tests (estimated: 8-12 hours)
2. Remove legacy code (estimated: 1 hour)
3. Update documentation (estimated: 2 hours)
4. Final testing and verification (estimated: 2-3 hours)

## References

- **Original Issue**: #12 (Performance optimization)
- **Implementation PR**: TBD
- **Related Docs**:
  - ARCHITECTURE.md - Architecture patterns
  - CONTRIBUTING.md - Development guidelines
  - CLAUDE.md - Project-specific guidance

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-17 | Claude Code | Initial deprecation plan |

---

**Status**: 📋 Draft - Pending approval
**Next Review**: Before v0.2.0 release planning
