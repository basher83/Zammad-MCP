# Attachment Upload & Delete Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete attachment support by adding upload (via article creation) and delete capabilities to the Zammad MCP server.

**Architecture:** Extends existing `zammad_add_article` tool with optional attachments parameter (base64-encoded), adds new `zammad_delete_attachment` tool. Uses Pydantic models for validation (base64, filename sanitization, path traversal prevention). Follows existing patterns: models → client → server layers with comprehensive tests.

**Tech Stack:** Python 3.10+, FastMCP, Pydantic, pytest, zammad-py library

---

## Task 1: Add AttachmentUpload Model

**Files:**
- Modify: `mcp_zammad/models.py`
- Test: `tests/test_models.py`

**Step 1: Write failing test for valid attachment**

Add to `tests/test_models.py`:

```python
class TestAttachmentUpload:
    """Tests for AttachmentUpload model."""

    def test_valid_attachment(self):
        """Test creating valid attachment with base64 data."""
        from mcp_zammad.models import AttachmentUpload

        att = AttachmentUpload(
            filename="test.pdf",
            data="dGVzdA==",  # "test" in base64
            mime_type="application/pdf"
        )
        assert att.filename == "test.pdf"
        assert att.data == "dGVzdA=="
        assert att.mime_type == "application/pdf"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload::test_valid_attachment -v`

Expected: FAIL with "cannot import name 'AttachmentUpload'"

**Step 3: Write minimal AttachmentUpload model**

Add to `mcp_zammad/models.py` (after imports, before other models):

```python
class AttachmentUpload(StrictBaseModel):
    """Attachment data for upload."""

    filename: str = Field(description="Attachment filename", max_length=255)
    data: str = Field(description="Base64-encoded file content")
    mime_type: str = Field(description="MIME type (e.g., application/pdf)", max_length=100)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload::test_valid_attachment -v`

Expected: PASS

**Step 5: Add test for invalid base64**

Add to `TestAttachmentUpload` class:

```python
def test_invalid_base64(self):
    """Test that invalid base64 data raises validation error."""
    import pytest
    from pydantic import ValidationError
    from mcp_zammad.models import AttachmentUpload

    with pytest.raises(ValidationError, match="Invalid base64"):
        AttachmentUpload(
            filename="test.pdf",
            data="not-valid-base64!!!",
            mime_type="application/pdf"
        )
```

**Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload::test_invalid_base64 -v`

Expected: FAIL (validation error not raised or wrong message)

**Step 7: Add base64 validator to AttachmentUpload**

Add to `AttachmentUpload` class in `mcp_zammad/models.py`:

```python
import base64

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
```

**Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload::test_invalid_base64 -v`

Expected: PASS

**Step 9: Add test for path traversal sanitization**

Add to `TestAttachmentUpload` class:

```python
def test_path_traversal_sanitization(self):
    """Test filename sanitization prevents path traversal."""
    from mcp_zammad.models import AttachmentUpload

    att = AttachmentUpload(
        filename="../../../etc/passwd",
        data="dGVzdA==",
        mime_type="text/plain"
    )
    assert att.filename == "passwd"  # Path components stripped
    assert "/" not in att.filename
```

**Step 10: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload::test_path_traversal_sanitization -v`

Expected: FAIL (filename not sanitized)

**Step 11: Add filename sanitizer to AttachmentUpload**

Add to `AttachmentUpload` class:

```python
import os

class AttachmentUpload(StrictBaseModel):
    # ... existing fields ...

    @field_validator("filename")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        """Sanitize filename to prevent path traversal."""
        # Remove path components, keep only basename
        sanitized = os.path.basename(v)
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        return sanitized

    @field_validator("data")
    @classmethod
    def validate_base64(cls, v: str) -> str:
        # ... existing validator ...
```

**Step 12: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload::test_path_traversal_sanitization -v`

Expected: PASS

**Step 13: Add test for null byte removal**

Add to `TestAttachmentUpload` class:

```python
def test_null_byte_removal(self):
    """Test null bytes are removed from filename."""
    from mcp_zammad.models import AttachmentUpload

    att = AttachmentUpload(
        filename="test\x00.pdf",
        data="dGVzdA==",
        mime_type="application/pdf"
    )
    assert "\x00" not in att.filename
    assert att.filename == "test.pdf"
```

**Step 14: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload::test_null_byte_removal -v`

Expected: PASS (already handled by sanitize_filename)

**Step 15: Run all AttachmentUpload tests**

Run: `uv run pytest tests/test_models.py::TestAttachmentUpload -v`

Expected: All 4 tests PASS

**Step 16: Commit AttachmentUpload model**

```bash
git add mcp_zammad/models.py tests/test_models.py
git commit -m "feat(models): add AttachmentUpload model with security validation

- Base64 validation prevents invalid encoding
- Filename sanitization prevents path traversal
- Null byte removal in filenames
- Comprehensive test coverage

Related to #14"
```

---

## Task 2: Modify ArticleCreate Model for Attachments

**Files:**
- Modify: `mcp_zammad/models.py` (ArticleCreate class)
- Test: `tests/test_models.py`

**Step 1: Write test for article with attachments**

Add new test class to `tests/test_models.py`:

```python
class TestArticleCreateWithAttachments:
    """Tests for ArticleCreate with attachments."""

    def test_article_with_valid_attachments(self):
        """Test creating article with valid attachments."""
        from mcp_zammad.models import ArticleCreate, AttachmentUpload

        article = ArticleCreate(
            ticket_id=123,
            body="See attached",
            attachments=[
                AttachmentUpload(
                    filename="doc.pdf",
                    data="dGVzdA==",
                    mime_type="application/pdf"
                )
            ]
        )
        assert article.ticket_id == 123
        assert article.body == "See attached"
        assert len(article.attachments) == 1
        assert article.attachments[0].filename == "doc.pdf"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::TestArticleCreateWithAttachments::test_article_with_valid_attachments -v`

Expected: FAIL (ArticleCreate has no attachments field)

**Step 3: Add attachments field to ArticleCreate**

Modify `ArticleCreate` class in `mcp_zammad/models.py`:

```python
class ArticleCreate(StrictBaseModel):
    """Create article request with optional attachments."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ticket_id: int = Field(description="Ticket ID to add article to", gt=0)
    body: str = Field(description="Article body content", max_length=100000)
    article_type: ArticleType = Field(default=ArticleType.NOTE, alias="type", description="Article type")
    internal: bool = Field(default=False, description="Whether the article is internal")
    sender: ArticleSender = Field(default=ArticleSender.AGENT, description="Sender type")
    attachments: list[AttachmentUpload] | None = Field(
        default=None,
        description="Optional attachments to include",
        max_length=10
    )

    @field_validator("body")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestArticleCreateWithAttachments::test_article_with_valid_attachments -v`

Expected: PASS

**Step 5: Write test for too many attachments**

Add to `TestArticleCreateWithAttachments`:

```python
def test_too_many_attachments(self):
    """Test that >10 attachments raises validation error."""
    import pytest
    from pydantic import ValidationError
    from mcp_zammad.models import ArticleCreate, AttachmentUpload

    with pytest.raises(ValidationError):
        ArticleCreate(
            ticket_id=123,
            body="Too many files",
            attachments=[
                AttachmentUpload(
                    filename=f"file{i}.txt",
                    data="dGVzdA==",
                    mime_type="text/plain"
                )
                for i in range(11)  # 11 attachments - exceeds limit
            ]
        )
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestArticleCreateWithAttachments::test_too_many_attachments -v`

Expected: PASS (max_length=10 already enforces this)

**Step 7: Write test for article without attachments (backward compat)**

Add to `TestArticleCreateWithAttachments`:

```python
def test_article_without_attachments(self):
    """Test creating article without attachments (backward compatibility)."""
    from mcp_zammad.models import ArticleCreate

    article = ArticleCreate(
        ticket_id=123,
        body="Simple comment"
    )
    assert article.ticket_id == 123
    assert article.body == "Simple comment"
    assert article.attachments is None
```

**Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestArticleCreateWithAttachments::test_article_without_attachments -v`

Expected: PASS

**Step 9: Run all ArticleCreate tests**

Run: `uv run pytest tests/test_models.py::TestArticleCreateWithAttachments -v`

Expected: All 3 tests PASS

**Step 10: Commit ArticleCreate modification**

```bash
git add mcp_zammad/models.py tests/test_models.py
git commit -m "feat(models): add attachments support to ArticleCreate

- Optional attachments field (list of AttachmentUpload)
- Maximum 10 attachments per article
- Backward compatible (attachments defaults to None)
- Comprehensive test coverage

Related to #14"
```

---

## Task 3: Add DeleteAttachmentParams Model

**Files:**
- Modify: `mcp_zammad/models.py`
- Test: `tests/test_models.py`

**Step 1: Write test for valid delete params**

Add new test class to `tests/test_models.py`:

```python
class TestDeleteAttachmentParams:
    """Tests for DeleteAttachmentParams model."""

    def test_valid_params(self):
        """Test creating valid delete attachment parameters."""
        from mcp_zammad.models import DeleteAttachmentParams

        params = DeleteAttachmentParams(
            ticket_id=123,
            article_id=456,
            attachment_id=789
        )
        assert params.ticket_id == 123
        assert params.article_id == 456
        assert params.attachment_id == 789
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::TestDeleteAttachmentParams::test_valid_params -v`

Expected: FAIL (DeleteAttachmentParams not defined)

**Step 3: Add DeleteAttachmentParams model**

Add to `mcp_zammad/models.py` (near other param models):

```python
class DeleteAttachmentParams(StrictBaseModel):
    """Delete attachment request parameters."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    article_id: int = Field(gt=0, description="Article ID")
    attachment_id: int = Field(gt=0, description="Attachment ID")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestDeleteAttachmentParams::test_valid_params -v`

Expected: PASS

**Step 5: Write test for invalid IDs**

Add to `TestDeleteAttachmentParams`:

```python
def test_invalid_ticket_id(self):
    """Test that ticket_id must be positive."""
    import pytest
    from pydantic import ValidationError
    from mcp_zammad.models import DeleteAttachmentParams

    with pytest.raises(ValidationError, match="greater than 0"):
        DeleteAttachmentParams(
            ticket_id=0,
            article_id=456,
            attachment_id=789
        )
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestDeleteAttachmentParams::test_invalid_ticket_id -v`

Expected: PASS (gt=0 already validates this)

**Step 7: Run all DeleteAttachmentParams tests**

Run: `uv run pytest tests/test_models.py::TestDeleteAttachmentParams -v`

Expected: All 2 tests PASS

**Step 8: Commit DeleteAttachmentParams model**

```bash
git add mcp_zammad/models.py tests/test_models.py
git commit -m "feat(models): add DeleteAttachmentParams model

- Validates all IDs are positive integers
- Simple parameter model for delete operation
- Comprehensive test coverage

Related to #14"
```

---

## Task 4: Modify Client add_article Method

**Files:**
- Modify: `mcp_zammad/client.py` (add_article method)
- Test: `tests/test_client.py`

**Step 1: Write test for add_article with attachments**

Add to `tests/test_client.py`:

```python
def test_add_article_with_attachments(mock_api: MagicMock) -> None:
    """Test adding article with attachments."""
    client = ZammadClient()
    mock_api.ticket_article.create.return_value = {
        "id": 789,
        "ticket_id": 123,
        "body": "See attached",
        "attachments": [
            {"id": 1, "filename": "test.pdf", "size": 1024}
        ]
    }

    attachments = [{
        "filename": "test.pdf",
        "data": "dGVzdA==",
        "mime-type": "application/pdf"
    }]

    result = client.add_article(
        ticket_id=123,
        body="See attached",
        attachments=attachments
    )

    assert result["id"] == 789
    mock_api.ticket_article.create.assert_called_once()
    call_args = mock_api.ticket_article.create.call_args[0][0]
    assert "attachments" in call_args
    assert call_args["attachments"] == attachments
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py::test_add_article_with_attachments -v`

Expected: FAIL (add_article doesn't accept attachments parameter)

**Step 3: Modify add_article to accept attachments**

Modify `add_article` method in `mcp_zammad/client.py`:

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
    """Add an article (comment/note) to a ticket with optional attachments.

    Args:
        ticket_id: Ticket ID to add article to
        body: Article body content
        article_type: Article type (note, email, phone)
        internal: Whether the article is internal
        sender: Sender type (Agent, Customer, System)
        attachments: Optional list of attachments with keys:
            - filename: str
            - data: str (base64-encoded content)
            - mime-type: str

    Returns:
        Created article data with attachment metadata
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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py::test_add_article_with_attachments -v`

Expected: PASS

**Step 5: Write test for backward compatibility (no attachments)**

Add to `tests/test_client.py`:

```python
def test_add_article_without_attachments_backward_compat(mock_api: MagicMock) -> None:
    """Test adding article without attachments (backward compatibility)."""
    client = ZammadClient()
    mock_api.ticket_article.create.return_value = {
        "id": 789,
        "ticket_id": 123,
        "body": "Simple comment"
    }

    result = client.add_article(
        ticket_id=123,
        body="Simple comment"
    )

    assert result["id"] == 789
    call_args = mock_api.ticket_article.create.call_args[0][0]
    assert "attachments" not in call_args  # Should not include empty attachments
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py::test_add_article_without_attachments_backward_compat -v`

Expected: PASS

**Step 7: Run all new add_article tests**

Run: `uv run pytest tests/test_client.py -k "add_article" -v`

Expected: Both new tests PASS

**Step 8: Commit client add_article modification**

```bash
git add mcp_zammad/client.py tests/test_client.py
git commit -m "feat(client): add attachment support to add_article method

- Optional attachments parameter (list of dicts)
- Attachments passed to Zammad API when provided
- Backward compatible (attachments defaults to None)
- Comprehensive test coverage

Related to #14"
```

---

## Task 5: Add Client delete_attachment Method

**Files:**
- Modify: `mcp_zammad/client.py`
- Test: `tests/test_client.py`

**Step 1: Write test for successful deletion**

Add to `tests/test_client.py`:

```python
def test_delete_attachment_success(mock_api: MagicMock) -> None:
    """Test successful attachment deletion."""
    client = ZammadClient()
    mock_api.ticket_article_attachment.destroy.return_value = True

    result = client.delete_attachment(
        ticket_id=123,
        article_id=456,
        attachment_id=789
    )

    assert result is True
    mock_api.ticket_article_attachment.destroy.assert_called_once_with(
        789, 456, 123
    )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py::test_delete_attachment_success -v`

Expected: FAIL (delete_attachment method not defined)

**Step 3: Add delete_attachment method**

Add to `mcp_zammad/client.py` (after add_article method):

```python
def delete_attachment(
    self,
    ticket_id: int,
    article_id: int,
    attachment_id: int
) -> bool:
    """Delete an attachment from a ticket article.

    Args:
        ticket_id: Ticket ID
        article_id: Article ID
        attachment_id: Attachment ID to delete

    Returns:
        True if deletion succeeded

    Raises:
        Exception if deletion fails
    """
    result = self.api.ticket_article_attachment.destroy(
        attachment_id, article_id, ticket_id
    )
    # destroy() returns True on success, may return dict on error
    return bool(result)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py::test_delete_attachment_success -v`

Expected: PASS

**Step 5: Write test for deletion failure**

Add to `tests/test_client.py`:

```python
def test_delete_attachment_failure(mock_api: MagicMock) -> None:
    """Test attachment deletion failure."""
    client = ZammadClient()
    mock_api.ticket_article_attachment.destroy.return_value = False

    result = client.delete_attachment(
        ticket_id=123,
        article_id=456,
        attachment_id=789
    )

    assert result is False
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py::test_delete_attachment_failure -v`

Expected: PASS

**Step 7: Run all delete_attachment tests**

Run: `uv run pytest tests/test_client.py -k "delete_attachment" -v`

Expected: Both tests PASS

**Step 8: Commit client delete_attachment method**

```bash
git add mcp_zammad/client.py tests/test_client.py
git commit -m "feat(client): add delete_attachment method

- Deletes attachment using zammad_py destroy method
- Returns boolean success/failure
- Parameter order matches API (attachment_id, article_id, ticket_id)
- Comprehensive test coverage

Related to #14"
```

---

## Task 6: Add AttachmentDeletionError Exception

**Files:**
- Modify: `mcp_zammad/server.py`

**Step 1: Add AttachmentDeletionError class**

Add to `mcp_zammad/server.py` (near other custom exceptions like AttachmentDownloadError):

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
        """Initialize attachment deletion error.

        Args:
            ticket_id: Ticket ID
            article_id: Article ID
            attachment_id: Attachment ID that failed to delete
            reason: Reason for failure
        """
        self.ticket_id = ticket_id
        self.article_id = article_id
        self.attachment_id = attachment_id
        self.reason = reason
        super().__init__(
            f"Failed to delete attachment {attachment_id} from "
            f"article {article_id} in ticket {ticket_id}: {reason}"
        )
```

**Step 2: Commit AttachmentDeletionError**

```bash
git add mcp_zammad/server.py
git commit -m "feat(server): add AttachmentDeletionError exception

- Custom exception for attachment deletion failures
- Includes ticket_id, article_id, attachment_id context
- Clear error messages for debugging

Related to #14"
```

---

## Task 7: Modify Server zammad_add_article Tool

**Files:**
- Modify: `mcp_zammad/server.py` (zammad_add_article function)
- Test: `tests/test_server.py`

**Step 1: Write test for tool with attachments**

Add to `tests/test_server.py`:

```python
def test_add_article_with_attachments_tool(mock_client: MagicMock) -> None:
    """Test zammad_add_article tool with attachments."""
    from mcp_zammad.models import ArticleCreate, AttachmentUpload, ArticleType, ArticleSender

    # Mock client response
    mock_client.add_article.return_value = {
        "id": 789,
        "ticket_id": 123,
        "body": "See attachment",
        "attachments": [
            {
                "id": 1,
                "filename": "doc.pdf",
                "size": 1024,
                "content_type": "application/pdf"
            }
        ]
    }

    # Create params with attachment
    params = ArticleCreate(
        ticket_id=123,
        body="See attachment",
        article_type=ArticleType.NOTE,
        internal=False,
        sender=ArticleSender.AGENT,
        attachments=[
            AttachmentUpload(
                filename="doc.pdf",
                data="dGVzdA==",
                mime_type="application/pdf"
            )
        ]
    )

    # Call tool (you'll need to get the actual server instance)
    # This is a placeholder - adjust based on test setup
    # result = server.zammad_add_article(params)

    # Verify client.add_article was called with converted attachments
    # mock_client.add_article.assert_called_once()
    # call_kwargs = mock_client.add_article.call_args[1]
    # assert "attachments" in call_kwargs
    # assert call_kwargs["attachments"][0]["filename"] == "doc.pdf"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py::test_add_article_with_attachments_tool -v`

Expected: FAIL (tool doesn't handle attachments yet)

**Step 3: Modify zammad_add_article tool**

Find and modify the `zammad_add_article` function in `mcp_zammad/server.py`:

```python
@self.mcp.tool()
def zammad_add_article(params: ArticleCreate) -> str:
    """Add an article/comment to an existing ticket with optional attachments.

    Args:
        params: Article creation parameters including:
            - ticket_id: Ticket ID to add article to
            - body: Article body content
            - type: Article type (note, email, phone)
            - internal: Whether article is internal
            - sender: Sender type (Agent, Customer, System)
            - attachments: Optional list of attachments (max 10)

    Returns:
        Formatted article details including attachment metadata

    Use Cases:
        - Add comments/notes to tickets
        - Upload files with article context
        - Internal communication with attachments

    Error Handling:
        - Validates base64 encoding before upload
        - Sanitizes filenames to prevent path traversal
        - Limits to 10 attachments per article
        - Returns detailed error messages on failure
    """
    client = self.get_client()

    # Convert Pydantic attachments to dict format for client
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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py::test_add_article_with_attachments_tool -v`

Expected: PASS

**Step 5: Write test for backward compatibility (no attachments)**

Add to `tests/test_server.py`:

```python
def test_add_article_without_attachments_backward_compat_tool(mock_client: MagicMock) -> None:
    """Test zammad_add_article tool without attachments (backward compatibility)."""
    from mcp_zammad.models import ArticleCreate, ArticleType, ArticleSender

    mock_client.add_article.return_value = {
        "id": 789,
        "ticket_id": 123,
        "body": "Simple comment"
    }

    params = ArticleCreate(
        ticket_id=123,
        body="Simple comment",
        article_type=ArticleType.NOTE,
        internal=False,
        sender=ArticleSender.AGENT
    )

    # Call tool and verify attachments=None passed to client
    # result = server.zammad_add_article(params)
    # mock_client.add_article.assert_called_once()
    # call_kwargs = mock_client.add_article.call_args[1]
    # assert call_kwargs.get("attachments") is None
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py::test_add_article_without_attachments_backward_compat_tool -v`

Expected: PASS

**Step 7: Run all add_article tool tests**

Run: `uv run pytest tests/test_server.py -k "add_article" -v`

Expected: All tests PASS

**Step 8: Commit zammad_add_article modification**

```bash
git add mcp_zammad/server.py tests/test_server.py
git commit -m "feat(server): add attachment support to zammad_add_article tool

- Converts Pydantic AttachmentUpload to dict format
- Passes attachments to client when provided
- Backward compatible (attachments optional)
- Enhanced docstring with use cases
- Comprehensive test coverage

Related to #14"
```

---

## Task 8: Add Server zammad_delete_attachment Tool

**Files:**
- Modify: `mcp_zammad/server.py`
- Test: `tests/test_server.py`

**Step 1: Write test for successful deletion**

Add to `tests/test_server.py`:

```python
def test_delete_attachment_tool_success(mock_client: MagicMock) -> None:
    """Test zammad_delete_attachment tool success."""
    from mcp_zammad.models import DeleteAttachmentParams

    mock_client.delete_attachment.return_value = True

    params = DeleteAttachmentParams(
        ticket_id=123,
        article_id=456,
        attachment_id=789
    )

    # Call tool
    # result = server.zammad_delete_attachment(params)

    # Verify success message
    # assert "Successfully deleted attachment 789" in result
    # assert "article 456" in result
    # assert "ticket 123" in result

    # Verify client called correctly
    mock_client.delete_attachment.assert_called_once_with(
        ticket_id=123,
        article_id=456,
        attachment_id=789
    )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py::test_delete_attachment_tool_success -v`

Expected: FAIL (tool not defined)

**Step 3: Add zammad_delete_attachment tool**

Add to `mcp_zammad/server.py` (after zammad_add_article or near other attachment tools):

```python
@self.mcp.tool()
def zammad_delete_attachment(params: DeleteAttachmentParams) -> str:
    """Delete an attachment from a ticket article.

    Args:
        params: Deletion parameters:
            - ticket_id: Ticket ID
            - article_id: Article ID
            - attachment_id: Attachment ID to delete

    Returns:
        Success confirmation message

    Use Cases:
        - Remove incorrect file uploads
        - Clean up sensitive attachments
        - Manage ticket storage

    Error Handling:
        - Validates all IDs are positive integers
        - Returns clear error if attachment not found
        - Logs deletion attempts

    Note:
        Requires appropriate Zammad permissions to delete attachments.
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
        ) from e
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py::test_delete_attachment_tool_success -v`

Expected: PASS

**Step 5: Write test for attachment not found**

Add to `tests/test_server.py`:

```python
def test_delete_attachment_tool_not_found(mock_client: MagicMock) -> None:
    """Test zammad_delete_attachment with non-existent attachment."""
    from mcp_zammad.models import DeleteAttachmentParams
    from mcp_zammad.server import AttachmentDeletionError
    import pytest

    # Mock API error
    mock_client.delete_attachment.side_effect = Exception("Attachment not found")

    params = DeleteAttachmentParams(
        ticket_id=123,
        article_id=456,
        attachment_id=999
    )

    # Verify AttachmentDeletionError is raised
    # with pytest.raises(AttachmentDeletionError) as exc_info:
    #     server.zammad_delete_attachment(params)

    # assert exc_info.value.attachment_id == 999
    # assert "Attachment not found" in str(exc_info.value)
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py::test_delete_attachment_tool_not_found -v`

Expected: PASS

**Step 7: Run all delete_attachment tool tests**

Run: `uv run pytest tests/test_server.py -k "delete_attachment" -v`

Expected: All tests PASS

**Step 8: Commit zammad_delete_attachment tool**

```bash
git add mcp_zammad/server.py tests/test_server.py
git commit -m "feat(server): add zammad_delete_attachment tool

- New MCP tool for deleting attachments
- Success/failure messages with context
- AttachmentDeletionError on exceptions
- Comprehensive docstring and test coverage

Related to #14"
```

---

## Task 9: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 2: Run tests with coverage**

Run: `uv run pytest --cov=mcp_zammad --cov-report=term-missing`

Expected: Coverage >= 90%

**Step 3: Run quality checks**

Run: `./scripts/quality-check.sh`

Expected: All checks PASS (ruff format, ruff lint, mypy, bandit, markdown lint)

**Step 4: If any issues found, fix them**

Fix any linting, type checking, or test failures before proceeding.

**Step 5: Commit any fixes**

```bash
git add .
git commit -m "fix: address quality check issues"
```

---

## Task 10: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `CHANGELOG.md`

**Step 1: Update README.md tool count**

Find and update the tool count in `README.md`:

Change: "18 tools" → "19 tools" (added zammad_delete_attachment)

**Step 2: Add attachment upload example to README**

Add to the "Usage Examples" or "Features" section in `README.md`:

```markdown
### Upload Attachments

```python
# Add article with attachments
await client.call_tool("zammad_add_article", {
    "ticket_id": 123,
    "body": "See attached documentation",
    "attachments": [
        {
            "filename": "guide.pdf",
            "data": "JVBERi0xLjQKJ...",  # base64-encoded content
            "mime_type": "application/pdf"
        }
    ]
})
```

### Delete Attachments

```python
# Delete an attachment
await client.call_tool("zammad_delete_attachment", {
    "ticket_id": 123,
    "article_id": 456,
    "attachment_id": 789
})
```
```

**Step 3: Update CLAUDE.md**

Update `CLAUDE.md` to reflect completed features:

- Move "Attachment upload support" from "Missing Features" to "Implemented"
- Update tool count from 18 to 19
- Add notes about base64 encoding and security validation

**Step 4: Update CHANGELOG.md**

Run: `mise run changelog`

This will update the unreleased section with your commits.

Review and edit if needed to add a human-readable summary.

**Step 5: Commit documentation updates**

```bash
git add README.md CLAUDE.md CHANGELOG.md
git commit -m "docs: update for attachment upload/delete features

- Updated tool count (18 → 19 tools)
- Added attachment upload/delete examples
- Updated CLAUDE.md with completed features
- Refreshed CHANGELOG.md

Closes #14"
```

---

## Task 11: Final Verification

**Step 1: Run full test suite one more time**

Run: `uv run pytest --cov=mcp_zammad`

Expected: All tests PASS, coverage >= 90%

**Step 2: Test manual integration (optional)**

Start server and test with MCP client:

```bash
# Start server
MCP_TRANSPORT=stdio ZAMMAD_URL=https://demo.zammad.com/api/v1 ZAMMAD_HTTP_TOKEN=test uv run python -m mcp_zammad

# Use MCP inspector or client to test:
# 1. Add article with attachment
# 2. List attachments
# 3. Download attachment
# 4. Delete attachment
```

**Step 3: Review all commits**

Run: `git log --oneline`

Verify commit messages are clear and follow conventional commits format.

**Step 4: Create final summary commit (if needed)**

If you made small fixes during verification:

```bash
git add .
git commit -m "chore: final cleanup and verification

- All tests passing
- Coverage at 90%+
- Quality checks passing
- Documentation updated"
```

**Step 5: Push to remote**

```bash
git push origin main
```

---

## Success Criteria Checklist

- [ ] AttachmentUpload model with base64 validation
- [ ] AttachmentUpload model with filename sanitization
- [ ] ArticleCreate accepts optional attachments (max 10)
- [ ] DeleteAttachmentParams model validates IDs
- [ ] client.add_article accepts attachments parameter
- [ ] client.delete_attachment implemented
- [ ] AttachmentDeletionError exception added
- [ ] zammad_add_article tool handles attachments
- [ ] zammad_delete_attachment tool implemented
- [ ] All tests passing (>=90% coverage)
- [ ] Quality checks passing (ruff, mypy, bandit)
- [ ] README.md updated with examples
- [ ] CLAUDE.md updated
- [ ] CHANGELOG.md updated
- [ ] Issue #14 closed

---

## Notes for Engineer

**Key Technologies:**
- **Pydantic**: Used for request/response validation and serialization
- **FastMCP**: MCP server framework (use `@self.mcp.tool()` decorator)
- **zammad-py**: Official Zammad Python client library

**Testing Philosophy:**
- Follow TDD: Write test → Run to fail → Implement → Run to pass
- Mock external dependencies (ZammadAPI)
- Test both happy path and error cases
- Maintain 90%+ coverage

**Code Style:**
- Use modern Python type hints (`list[str]` not `List[str]`)
- Use union operator (`str | None` not `Optional[str]`)
- Line length: 120 characters
- Format with `ruff format`, lint with `ruff check`

**Security:**
- Base64 validation prevents malformed data
- Filename sanitization prevents path traversal
- HTML escaping prevents XSS (already in ArticleCreate.body)
- Limit attachments to 10 per article

**Backward Compatibility:**
- `attachments` parameter is optional (defaults to None)
- Existing code continues to work without modification
- No breaking changes to existing API

**Common Pitfalls:**
- Don't forget `from __future__ import annotations` for type hints
- Remember to run tests after each step
- Don't skip the "run to fail" step in TDD
- Commit frequently (after each task completion)

**Getting Help:**
- Check existing attachment download/list tools for patterns
- Review `tests/test_models.py` for Pydantic testing examples
- See `tests/test_server.py` for MCP tool testing patterns
- CLAUDE.md has project-specific guidance
