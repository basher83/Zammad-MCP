# Attachment Upload & Delete Feature Design

**Date:** 2025-01-16
**Issue:** #14 - Feature: Add attachment support for tickets
**Status:** Approved for implementation

## Overview

This design completes the attachment support feature by adding upload and delete capabilities to the existing download and list functionality. The implementation maintains consistency with existing patterns while adding comprehensive security validation.

## Design Decisions

### 1. Upload Approach: Extend Existing Article Tool

**Decision:** Modify the existing `zammad_add_article` tool to accept optional attachments rather than creating a separate upload tool.

**Rationale:**

- Matches Zammad API design (attachments belong to articles)
- Reduces code duplication and tool proliferation
- Simpler user experience (upload while commenting)
- Maintains backward compatibility (attachments parameter is optional)

### 2. File Content Format: Base64 Encoding

**Decision:** Accept base64-encoded file content directly from MCP clients.

**Rationale:**

- MCP protocol works best with JSON/string data
- Matches existing download pattern (returns base64)
- Standard approach for binary data in JSON APIs
- Client handles encoding, server validates and passes through

### 3. Deletion Approach: Direct Deletion Tool

**Decision:** Implement `zammad_delete_attachment` as a standalone tool requiring ticket_id, article_id, and attachment_id.

**Rationale:**

- Completes CRUD operations for attachments
- Matches granularity of existing download/list tools
- The zammad_py library already supports destroy operation
- Clear, explicit purpose

## Architecture

### Data Flow

```text
LLM/Client
  ↓ (base64 file content)
MCP Tool (zammad_add_article)
  ↓ (validates via Pydantic)
ArticleCreate Model
  ↓ (AttachmentUpload models)
Client Layer (add_article)
  ↓ (dict conversion)
Zammad API (ticket_article.create)
```

### Component Structure

```text
models.py
├── AttachmentUpload (new)
│   ├── Base64 validation
│   ├── Filename sanitization
│   └── Path traversal prevention
├── ArticleCreate (modified)
│   └── Optional attachments field
└── DeleteAttachmentParams (new)

client.py
├── add_article (modified)
│   └── Accepts optional attachments
└── delete_attachment (new)

server.py
├── zammad_add_article (modified)
│   └── Handles attachment conversion
└── zammad_delete_attachment (new)
    └── AttachmentDeletionError handling
```

## Implementation Details

### 1. Models & Data Structures

#### New: AttachmentUpload Model

```python
class AttachmentUpload(StrictBaseModel):
    """Attachment data for upload."""

    filename: str = Field(description="Attachment filename", max_length=255)
    data: str = Field(description="Base64-encoded file content")
    mime_type: str = Field(description="MIME type (e.g., application/pdf)", max_length=100)

    @field_validator("data")
    @classmethod
    def validate_base64(cls, v: str) -> str:
        """Validate base64 encoding."""
        try:
            base64.b64decode(v, validate=True)
            return v
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {e}")

    @field_validator("filename")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        """Sanitize filename to prevent path traversal."""
        sanitized = os.path.basename(v)
        sanitized = sanitized.replace('\x00', '')
        return sanitized
```

#### Modified: ArticleCreate Model

```python
class ArticleCreate(StrictBaseModel):
    """Create article request with optional attachments."""

    # ... existing fields ...
    attachments: list[AttachmentUpload] | None = Field(
        default=None,
        description="Optional attachments to include",
        max_length=10
    )
```

#### New: DeleteAttachmentParams Model

```python
class DeleteAttachmentParams(StrictBaseModel):
    """Delete attachment request."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    article_id: int = Field(gt=0, description="Article ID")
    attachment_id: int = Field(gt=0, description="Attachment ID")
```

### 2. Client Layer

#### Modified: add_article Method

```python
def add_article(
    self,
    ticket_id: int,
    body: str,
    article_type: str = "note",
    internal: bool = False,
    sender: str = "Agent",
    attachments: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Add an article with optional attachments.

    Args:
        attachments: Optional list with keys:
            - filename: str
            - data: str (base64-encoded)
            - mime-type: str
    """
    article_data = {
        "ticket_id": ticket_id,
        "body": body,
        "type": article_type,
        "internal": internal,
        "sender": sender,
    }

    if attachments:
        article_data["attachments"] = attachments

    return dict(self.api.ticket_article.create(article_data))
```

#### New: delete_attachment Method

```python
def delete_attachment(
    self,
    ticket_id: int,
    article_id: int,
    attachment_id: int
) -> bool:
    """Delete an attachment from a ticket article."""
    result = self.api.ticket_article_attachment.destroy(
        attachment_id, article_id, ticket_id
    )
    return bool(result)
```

### 3. MCP Server Layer

#### Modified: zammad_add_article Tool

```python
@self.mcp.tool()
def zammad_add_article(params: ArticleCreate) -> str:
    """Add article/comment with optional attachments.

    Use Cases:
        - Add comments with file attachments
        - Upload documentation to tickets
        - Internal notes with supporting files

    Error Handling:
        - Validates base64 encoding
        - Sanitizes filenames (path traversal prevention)
        - Limits to 10 attachments per article
    """
    client = self.get_client()

    attachments_data = None
    if params.attachments:
        attachments_data = [
            {
                "filename": att.filename,
                "data": att.data,
                "mime-type": att.mime_type,
            }
            for att in params.attachments
        ]

    article = client.add_article(
        ticket_id=params.ticket_id,
        body=params.body,
        article_type=params.article_type.value,
        internal=params.internal,
        sender=params.sender.value,
        attachments=attachments_data,
    )

    return self._format_article(article)
```

#### New: zammad_delete_attachment Tool

```python
@self.mcp.tool()
def zammad_delete_attachment(params: DeleteAttachmentParams) -> str:
    """Delete an attachment from a ticket article.

    Use Cases:
        - Remove incorrect uploads
        - Clean up sensitive files
        - Manage storage

    Note:
        Requires appropriate Zammad permissions.
    """
    client = self.get_client()

    try:
        success = client.delete_attachment(
            ticket_id=params.ticket_id,
            article_id=params.article_id,
            attachment_id=params.attachment_id,
        )

        if success:
            return (
                f"Successfully deleted attachment {params.attachment_id} "
                f"from article {params.article_id} in ticket {params.ticket_id}"
            )
        else:
            return f"Failed to delete attachment {params.attachment_id}"

    except Exception as e:
        raise AttachmentDeletionError(
            ticket_id=params.ticket_id,
            article_id=params.article_id,
            attachment_id=params.attachment_id,
            reason=str(e),
        )
```

## Security Considerations

### Input Validation

1. **Base64 Validation**: Validates encoding before processing to prevent malformed data
2. **Filename Sanitization**: Strips path components using `os.path.basename()` to prevent path traversal attacks
3. **Null Byte Removal**: Removes null bytes from filenames to prevent injection attacks
4. **Size Limits**: Restricts to 10 attachments per article to prevent resource exhaustion

### Error Handling

**Error Scenarios:**

1. **Invalid base64**: Pydantic validator catches and returns clear error
2. **Path traversal**: Automatic sanitization in validator
3. **Too many attachments**: Pydantic `max_length` validation
4. **API failures**: Wrapped in custom exceptions with context
5. **Permission denied**: Clear error messages with all IDs for debugging

**New Exception:**

```python
class AttachmentDeletionError(Exception):
    """Raised when attachment deletion fails."""

    def __init__(
        self,
        ticket_id: int,
        article_id: int,
        attachment_id: int,
        reason: str
    ):
        self.ticket_id = ticket_id
        self.article_id = article_id
        self.attachment_id = attachment_id
        self.reason = reason
        super().__init__(
            f"Failed to delete attachment {attachment_id} from "
            f"article {article_id} in ticket {ticket_id}: {reason}"
        )
```

## Testing Strategy

### Model Tests (tests/test_models.py)

- Valid attachment creation
- Invalid base64 rejection
- Path traversal sanitization
- Null byte removal
- Article with attachments
- Too many attachments rejection (>10)

### Client Tests (tests/test_client.py)

- Add article with attachments
- Add article without attachments (backward compatibility)
- Delete attachment success
- Delete attachment failure
- API error handling

### Server Tests (tests/test_server.py)

- Tool invocation with attachments
- Tool invocation without attachments
- Attachment data formatting
- Delete attachment success message
- Delete attachment error handling
- AttachmentDeletionError scenarios

### Coverage Target

Maintain 90%+ test coverage (currently at 90.08%)

## Backward Compatibility

### Breaking Changes

None. All changes are additive:
- `attachments` parameter is optional in `add_article`
- New tool `zammad_delete_attachment` doesn't affect existing tools
- Existing tests and functionality remain unchanged

### Migration Path

No migration required. Existing code continues to work without modification.

## Success Criteria

- [ ] Can upload attachments with articles (base64 encoded)
- [ ] Can delete attachments by ID
- [ ] Base64 validation prevents invalid data
- [ ] Filename sanitization prevents path traversal
- [ ] Maximum 10 attachments enforced per article
- [ ] Clear error messages for all failure scenarios
- [ ] 90%+ test coverage maintained
- [ ] All existing tests pass
- [ ] Documentation updated (README, CLAUDE.md)

## References

- Issue #14: Feature: Add attachment support for tickets
- Zammad API Documentation: https://docs.zammad.org/en/latest/api/ticket/articles.html
- Existing implementation: commit 72c0a49 (download/list features)
- Security patterns: Issue #17 (URL validation, input sanitization)
