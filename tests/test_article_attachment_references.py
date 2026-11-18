"""Exercise attachment reuse through the public MCP boundary."""

import base64
from unittest.mock import patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_zammad.server import ZammadMCPServer
from tests.attachment_reference_support import created_article, source_article


async def call_article(client, **parameters):
    """Invoke the registered MCP tool with a supplied client capability."""
    server = ZammadMCPServer()
    with patch("mcp_zammad.server.ZammadClient", return_value=client):
        async with Client(server.mcp) as mcp:
            return await mcp.call_tool("zammad_add_article", {"ticket_id": 41, "body": "See attached", **parameters})


@pytest.mark.asyncio
async def test_mcp_reuses_attachment_without_model_base64(attachment_api):
    client, api = attachment_api
    result = await call_article(
        client,
        article_type="email",
        to="recipient@example.invalid",
        source_article_id=72,
        attachment_ids=[91],
    )
    assert not result.is_error
    payload = api.ticket_article.create.call_args.args[0]
    assert payload["attachments"] == [
        {
            "filename": "report.pdf",
            "data": base64.b64encode(b"%PDF-1.7").decode(),
            "mime-type": "application/pdf",
        }
    ]
    assert payload["to"] == "recipient@example.invalid"
    assert "source_article_id" not in payload
    assert "attachment_ids" not in payload
    assert "JVBERi0xLjc=" not in str(result)


@pytest.mark.parametrize("field,value", [("ticket_id", 42), ("id", 74)])
def test_client_rejects_unrelated_source_article(attachment_api, field, value):
    client, api = attachment_api
    article = source_article()
    article[field] = value
    api.ticket_article.find.side_effect = lambda _identifier: article
    with pytest.raises(ValueError, match="Source article"):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article.create.assert_not_called()
    api.ticket_article_attachment.download.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("ticket_id", [True, False, "41", 41.0])
async def test_mcp_rejects_coerced_target_id_with_references(attachment_api, ticket_id):
    client, api = attachment_api
    with pytest.raises(ToolError, match="strictly positive integer"):
        await call_article(client, ticket_id=ticket_id, source_article_id=72, attachment_ids=[91])
    api.ticket_article.find.assert_not_called()
    api.ticket_article_attachment.download.assert_not_called()
    api.ticket_article.create.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_sanitizes_invalid_created_article_without_retry(attachment_api):
    client, api = attachment_api
    response = created_article()
    response["id"] = "JVBERi0xLjc= fictional-secret"
    api.ticket_article.create.return_value = response
    with pytest.raises(ToolError, match=r"outcome unknown\. Do not retry automatically") as error:
        await call_article(client, source_article_id=72, attachment_ids=[91])
    assert "JVBERi0xLjc=" not in str(error.value)
    assert "fictional-secret" not in str(error.value)
    assert api.ticket_article.create.call_count == 1
