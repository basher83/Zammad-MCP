#!/usr/bin/env python3
"""
Shared utilities for UV scripts.

This module contains common functionality used across multiple UV scripts
to avoid code duplication and ensure consistency.
"""

from urllib.parse import urlparse


def normalize_zammad_url(url: str) -> str:
    """
    Normalize a Zammad URL to ensure it ends with /api/v1.

    Args:
        url: The Zammad instance URL

    Returns:
        The normalized URL ending with /api/v1

    Raises:
        ValueError: If the URL is invalid

    Examples:
        >>> normalize_zammad_url("https://example.zammad.com")
        'https://example.zammad.com/api/v1'

        >>> normalize_zammad_url("https://example.zammad.com/")
        'https://example.zammad.com/api/v1'

        >>> normalize_zammad_url("https://example.zammad.com/api/v1")
        'https://example.zammad.com/api/v1'
    """
    if not url:
        raise ValueError("URL cannot be empty")

    # Validate URL has a scheme
    parsed = urlparse(url)
    if not parsed.scheme:
        raise ValueError("URL must include protocol (http:// or https://)")

    if parsed.scheme not in ["http", "https"]:
        raise ValueError("URL must use http or https protocol")

    # Ensure URL ends with /api/v1
    if not url.endswith("/api/v1"):
        if url.endswith("/"):
            url = url[:-1]
        url = f"{url}/api/v1"

    return url
