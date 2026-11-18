"""Preserve attachment bytes through the real SDK and authenticated HTTP boundary."""

import base64
import json
from unittest.mock import Mock

import pytest
import requests

from mcp_zammad.client import ZammadClient
from tests.attachment_reference_support import created_article, source_article


@pytest.fixture
def attachment_http(monkeypatch):
    """Supply mocked HTTP transport while retaining real SDK response handling."""
    send = Mock()
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    client = ZammadClient(url="https://example.invalid/api/v1/", http_token="fictional-token")
    return client, send


def http_response(content, status=200):
    """Return a real buffered HTTP response without network access."""
    response = requests.Response()
    response.status_code = status
    response._content = content
    response.headers["Content-Type"] = "application/json"
    return response


@pytest.mark.parametrize("content", [b"1", b'{"a":1}', b"[1,2]", b'"hello"'])
def test_reference_preserves_json_shaped_attachment_bytes(attachment_http, content):
    client, send = attachment_http
    article = source_article()
    article["attachments"][0]["size"] = len(content)
    metadata = json.dumps(article).encode()
    send.side_effect = [
        http_response(metadata),
        http_response(content),
        http_response(metadata),
        http_response(json.dumps(created_article()).encode()),
    ]
    result = client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    assert result["id"] == 73
    requests_sent = [call.args[0] for call in send.call_args_list]
    uploaded = json.loads(requests_sent[-1].body)["attachments"][0]
    assert base64.b64decode(uploaded["data"]) == content
    assert [request.method for request in requests_sent] == ["GET", "GET", "GET", "POST"]
    assert requests_sent[1].url == "https://example.invalid/api/v1/ticket_attachment/41/72/91"
    assert all(request.headers["Authorization"] == "Token token=fictional-token" for request in requests_sent)
    assert send.call_args_list[1].kwargs["timeout"] == 30.0
    assert send.call_args_list[1].kwargs["verify"] is True


@pytest.mark.parametrize("boundary", ["download", "write"])
def test_reference_http_errors_hide_content_and_never_retry_writes(attachment_http, boundary):
    client, send = attachment_http
    metadata = json.dumps(source_article()).encode()
    failure = http_response(b"Authorization: fictional-secret JVBERi0xLjc=", 403 if boundary == "download" else 503)
    send.side_effect = (
        [http_response(metadata), failure]
        if boundary == "download"
        else [http_response(metadata), http_response(b"%PDF-1.7"), http_response(metadata), failure]
    )
    with pytest.raises(ValueError) as error:
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    assert "fictional-secret" not in str(error.value)
    assert "JVBERi0xLjc=" not in str(error.value)
    assert error.value.__suppress_context__
    methods = [call.args[0].method for call in send.call_args_list]
    assert methods.count("POST") == (1 if boundary == "write" else 0)
    assert len(methods) == (4 if boundary == "write" else 2)
    if boundary == "write":
        assert "outcome unknown. Do not retry automatically" in str(error.value)
