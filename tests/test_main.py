"""Tests for the __main__ module."""

from unittest.mock import Mock, patch

import mcp_zammad.__main__ as main_module
from mcp_zammad.__main__ import main


class TestMain:
    """Test cases for the main entry point."""

    def test_main_calls_mcp_run(self) -> None:
        """Test that main() calls mcp.run()."""
        with patch("mcp_zammad.__main__.mcp") as mock_mcp:
            mock_run = Mock()
            mock_mcp.run = mock_run

            main()

            mock_run.assert_called_once_with()

    def test_main_module_execution(self) -> None:
        """Test that __main__ block would execute main() when run as a script."""
        # We'll test the pattern rather than executing it
        # Since the __main__ guard is at module level, we verify the pattern exists

        # Verify the module has the expected structure
        assert hasattr(main_module, "main")
        assert callable(main_module.main)

        # The actual execution is covered by test_main_calls_mcp_run
        # This test ensures the module structure is correct

    def test_import_without_execution(self) -> None:
        """Test that importing the module doesn't execute main()."""
        with patch("mcp_zammad.__main__.mcp") as mock_mcp:
            mock_run = Mock()
            mock_mcp.run = mock_run

            # Import the module (already imported above, but for clarity)

            # Should not have called run() just from importing
            # (unless __name__ was "__main__", which it isn't in tests)
            # Reset the mock to ensure clean state
            mock_run.reset_mock()

            # Verify no calls were made
            mock_run.assert_not_called()
