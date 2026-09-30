"""The package advertises the same version that its distribution metadata declares."""

from importlib.metadata import version

import mcp_zammad


def test_dunder_version_matches_distribution_metadata() -> None:
    assert mcp_zammad.__version__ == version("mcp-zammad")
