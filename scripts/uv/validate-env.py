#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "httpx>=0.25.0",
#   "rich>=13.0.0",
#   "pydantic>=2.0.0",
#   "click>=8.0.0",
# ]
# requires-python = ">=3.10"
# ///
"""
Validate Zammad MCP Server environment configuration.

This script checks that the environment is properly configured for the Zammad MCP
server including:
- Environment variables are set correctly
- Zammad API is reachable
- Authentication credentials are valid
- Required permissions are available

Usage:
    ./validate-env.py              # Interactive mode with .env file
    ./validate-env.py --env-file custom.env
    ./validate-env.py --no-test-connection  # Skip connection test
    uv run validate-env.py         # Run without making executable
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import click
import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from utils import normalize_zammad_url

console = Console()


class ZammadConfig(BaseModel):
    """Zammad configuration model with validation."""

    url: str = Field(..., description="Zammad API URL")
    http_token: str | None = Field(None, description="HTTP API Token")
    oauth2_token: str | None = Field(None, description="OAuth2 Token")
    username: str | None = Field(None, description="Username for basic auth")
    password: str | None = Field(None, description="Password for basic auth")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate and normalize Zammad URL."""
        if not v:
            raise ValueError("Zammad URL is required")

        # Use shared utility for URL normalization
        return normalize_zammad_url(v)

    @property
    def has_auth(self) -> bool:
        """Check if any authentication method is configured."""
        return bool(self.http_token or self.oauth2_token or (self.username and self.password))

    @property
    def auth_method(self) -> str:
        """Get the configured authentication method."""
        if self.http_token:
            return "HTTP Token"
        elif self.oauth2_token:
            return "OAuth2 Token"
        elif self.username and self.password:
            return "Username/Password"
        else:
            return "None"


def load_environment(env_file: Path | None = None) -> dict[str, str | None]:
    """Load environment variables from file or system."""
    if env_file:
        if not env_file.exists():
            console.print(f"[red]Error:[/red] Environment file '{env_file}' not found")
            sys.exit(1)
        load_dotenv(env_file)
    else:
        # Try to load .env from current directory
        default_env = Path(".env")
        if default_env.exists():
            load_dotenv(default_env)
            console.print(f"[dim]Loaded environment from {default_env}[/dim]")

    return {
        "ZAMMAD_URL": os.getenv("ZAMMAD_URL"),
        "ZAMMAD_HTTP_TOKEN": os.getenv("ZAMMAD_HTTP_TOKEN"),
        "ZAMMAD_OAUTH2_TOKEN": os.getenv("ZAMMAD_OAUTH2_TOKEN"),
        "ZAMMAD_USERNAME": os.getenv("ZAMMAD_USERNAME"),
        "ZAMMAD_PASSWORD": os.getenv("ZAMMAD_PASSWORD"),
    }


def validate_config(env_vars: dict[str, str | None]) -> tuple[ZammadConfig | None, list[str]]:
    """Validate configuration and return config object and errors."""
    errors = []

    # Check for URL
    if not env_vars.get("ZAMMAD_URL"):
        errors.append("ZAMMAD_URL environment variable is not set")

    # Check for at least one auth method
    has_auth = any(
        [
            env_vars.get("ZAMMAD_HTTP_TOKEN"),
            env_vars.get("ZAMMAD_OAUTH2_TOKEN"),
            (env_vars.get("ZAMMAD_USERNAME") and env_vars.get("ZAMMAD_PASSWORD")),
        ]
    )

    if not has_auth:
        errors.append("No authentication method configured (need HTTP token, OAuth2 token, or username/password)")

    # Check for partial username/password
    if env_vars.get("ZAMMAD_USERNAME") and not env_vars.get("ZAMMAD_PASSWORD"):
        errors.append("ZAMMAD_USERNAME is set but ZAMMAD_PASSWORD is missing")
    elif env_vars.get("ZAMMAD_PASSWORD") and not env_vars.get("ZAMMAD_USERNAME"):
        errors.append("ZAMMAD_PASSWORD is set but ZAMMAD_USERNAME is missing")

    if errors:
        return None, errors

    # Try to create config object
    try:
        config = ZammadConfig(
            url=env_vars["ZAMMAD_URL"],
            http_token=env_vars.get("ZAMMAD_HTTP_TOKEN"),
            oauth2_token=env_vars.get("ZAMMAD_OAUTH2_TOKEN"),
            username=env_vars.get("ZAMMAD_USERNAME"),
            password=env_vars.get("ZAMMAD_PASSWORD"),
        )
        return config, []
    except ValidationError as e:
        errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        return None, errors


async def test_connection(config: ZammadConfig) -> tuple[bool, str, dict[str, Any] | None]:
    """Test connection to Zammad API."""
    headers = {"User-Agent": "Zammad-MCP-Validator/1.0"}

    # Add authentication headers
    if config.http_token:
        headers["Authorization"] = f"Token token={config.http_token}"
    elif config.oauth2_token:
        headers["Authorization"] = f"Bearer {config.oauth2_token}"

    auth = None
    if config.username and config.password:
        auth = (config.username, config.password)

    try:
        async with httpx.AsyncClient() as client:
            # Test API endpoint
            response = await client.get(f"{config.url}/users/me", headers=headers, auth=auth, timeout=10.0)

            if response.status_code == 200:
                user_data = response.json()
                return True, "Connection successful", user_data
            elif response.status_code == 401:
                return False, "Authentication failed - invalid credentials", None
            elif response.status_code == 403:
                return False, "Authorization failed - insufficient permissions", None
            else:
                return False, f"Unexpected response: {response.status_code}", None

    except httpx.ConnectTimeout:
        return False, "Connection timeout - server not reachable", None
    except httpx.ConnectError as e:
        return False, f"Connection failed: {e!s}", None
    except Exception as e:
        return False, f"Unexpected error: {e!s}", None


def display_config(config: ZammadConfig, env_source: str):
    """Display configuration details."""
    table = Table(title="Zammad Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Parse base URL for display
    parsed = urlparse(config.url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    table.add_row("Environment Source", env_source)
    table.add_row("Zammad Instance", base_url)
    table.add_row("API Endpoint", config.url)
    table.add_row("Authentication Method", config.auth_method)

    if config.http_token:
        masked_token = config.http_token[:8] + "..." + config.http_token[-4:]
        table.add_row("HTTP Token", f"[dim]{masked_token}[/dim]")

    if config.oauth2_token:
        masked_token = config.oauth2_token[:8] + "..." + config.oauth2_token[-4:]
        table.add_row("OAuth2 Token", f"[dim]{masked_token}[/dim]")

    if config.username:
        table.add_row("Username", config.username)
        table.add_row("Password", "[dim]****[/dim]" if config.password else "[red]Not set[/red]")

    console.print(table)


def display_user_info(user_data: dict[str, Any]):
    """Display authenticated user information."""
    table = Table(title="Authenticated User", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("User ID", str(user_data.get("id", "N/A")))
    table.add_row("Login", user_data.get("login", "N/A"))
    table.add_row("Email", user_data.get("email", "N/A"))
    table.add_row("First Name", user_data.get("firstname", "N/A"))
    table.add_row("Last Name", user_data.get("lastname", "N/A"))
    table.add_row("Active", "✓" if user_data.get("active") else "✗")

    # Display roles if available
    roles = user_data.get("role_ids", [])
    if roles:
        table.add_row("Roles", f"{len(roles)} role(s)")

    # Display groups if available
    groups = user_data.get("group_ids", {})
    if groups:
        table.add_row("Groups", f"{len(groups)} group(s)")

    console.print(table)


@click.command()
@click.option(
    "--env-file",
    type=click.Path(exists=False, path_type=Path),
    help="Path to environment file (default: .env)",
)
@click.option(
    "--no-test-connection",
    is_flag=True,
    help="Skip connection test",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
def main(env_file: Path | None, no_test_connection: bool, output_json: bool):
    """Validate Zammad MCP Server environment configuration."""

    if not output_json:
        console.print(
            Panel.fit(
                "[bold]Zammad MCP Environment Validator[/bold]\nChecking your environment configuration...",
                border_style="blue",
            )
        )

    # Load environment
    env_source = str(env_file) if env_file else ".env or system environment"
    env_vars = load_environment(env_file)

    # Validate configuration
    config, errors = validate_config(env_vars)

    if errors:
        if output_json:
            print(json.dumps({"valid": False, "errors": errors}))
        else:
            console.print("\n[red]Configuration Errors:[/red]")
            for error in errors:
                console.print(f"  • {error}")
        sys.exit(1)

    if not output_json:
        console.print("\n[green]✓[/green] Configuration syntax is valid")
        display_config(config, env_source)

    # Test connection
    if not no_test_connection:
        if not output_json:
            console.print("\n[bold]Testing Zammad Connection...[/bold]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
            disable=output_json,
        ) as progress:
            progress.add_task("Connecting to Zammad API...", total=None)

            success, message, user_data = asyncio.run(test_connection(config))

        if success:
            if output_json:
                print(json.dumps({"valid": True, "connection": True, "user": user_data}))
            else:
                console.print(f"\n[green]✓[/green] {message}")
                if user_data:
                    display_user_info(user_data)
                console.print("\n[bold green]Environment is ready for Zammad MCP Server![/bold green]")
        else:
            if output_json:
                print(json.dumps({"valid": True, "connection": False, "error": message}))
            else:
                console.print(f"\n[red]✗[/red] {message}")
                console.print("\n[yellow]Configuration is valid but connection failed.[/yellow]")
                console.print("Please check:")
                console.print("  • Is the Zammad instance running and accessible?")
                console.print("  • Are the credentials correct?")
                console.print("  • Is the API endpoint correct? (should end with /api/v1)")
            sys.exit(1)
    elif output_json:
        print(json.dumps({"valid": True, "connection": "skipped"}))
    else:
        console.print("\n[yellow]Connection test skipped[/yellow]")
        console.print("\n[green]Environment configuration appears valid[/green]")


if __name__ == "__main__":
    main()
