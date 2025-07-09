#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "click>=8.0.0",
#   "rich>=13.0.0",
#   "python-dotenv>=1.0.0",
#   "httpx>=0.25.0",
#   "zammad-py>=3.2.0",
#   "questionary>=2.0.0",
# ]
# requires-python = ">=3.10"
# ///
"""
Interactive Zammad API test client.

This script provides an interactive CLI for testing Zammad API connections
and operations without starting the full MCP server. It's useful for:
- Testing authentication credentials
- Exploring API endpoints
- Debugging connection issues
- Performance testing
- Learning the Zammad API

Usage:
    ./test-zammad.py                    # Interactive mode
    ./test-zammad.py --operation list-tickets --limit 5
    ./test-zammad.py --benchmark        # Run performance tests
    ./test-zammad.py --env-file prod.env
    uv run test-zammad.py              # Run without making executable
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import questionary
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.tree import Tree
from utils import normalize_zammad_url
from zammad_py import ZammadAPI

console = Console()


class ZammadTestClient:
    """Interactive Zammad API test client."""

    def __init__(self, env_file: Path | None = None):
        self.env_file = env_file or Path(".env")
        self.client: ZammadAPI | None = None
        self.connected = False
        self.user_info: dict[str, Any] | None = None

    def load_config(self) -> bool:
        """Load configuration from environment."""
        if self.env_file.exists():
            load_dotenv(self.env_file)
            console.print(f"[dim]Loaded configuration from {self.env_file}[/dim]")

        self.url = os.getenv("ZAMMAD_URL", "")
        self.http_token = os.getenv("ZAMMAD_HTTP_TOKEN")
        self.oauth2_token = os.getenv("ZAMMAD_OAUTH2_TOKEN")
        self.username = os.getenv("ZAMMAD_USERNAME")
        self.password = os.getenv("ZAMMAD_PASSWORD")

        if not self.url:
            console.print("[red]Error:[/red] ZAMMAD_URL not configured")
            return False

        # Normalize URL to ensure it ends with /api/v1
        try:
            self.url = normalize_zammad_url(self.url)
        except ValueError as e:
            console.print(f"[red]Error:[/red] Invalid URL: {e}")
            return False

        return True

    def connect(self) -> bool:
        """Connect to Zammad API."""
        try:
            if self.http_token:
                self.client = ZammadAPI(url=self.url, http_token=self.http_token)
                auth_method = "HTTP Token"
            elif self.oauth2_token:
                self.client = ZammadAPI(url=self.url, oauth2_token=self.oauth2_token)
                auth_method = "OAuth2 Token"
            elif self.username and self.password:
                self.client = ZammadAPI(url=self.url, username=self.username, password=self.password)
                auth_method = "Username/Password"
            else:
                console.print("[red]Error:[/red] No authentication credentials configured")
                return False

            # Test connection
            start_time = time.time()
            self.user_info = self.client.user.me()
            elapsed = time.time() - start_time

            self.connected = True
            console.print(f"[green]✓[/green] Connected using {auth_method} ({elapsed:.2f}s)")
            return True

        except Exception as e:
            console.print(f"[red]✗[/red] Connection failed: {e}")
            return False

    def display_user_info(self) -> None:
        """Display authenticated user information."""
        if not self.user_info:
            return

        table = Table(title="Authenticated User", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("ID", str(self.user_info.get("id")))
        table.add_row("Login", self.user_info.get("login", "N/A"))
        table.add_row("Email", self.user_info.get("email", "N/A"))
        table.add_row("Name", f"{self.user_info.get('firstname', '')} {self.user_info.get('lastname', '')}")
        table.add_row("Active", "✓" if self.user_info.get("active") else "✗")

        # Roles
        role_ids = self.user_info.get("role_ids", [])
        if role_ids:
            table.add_row("Roles", f"{len(role_ids)} role(s)")

        console.print(table)

    def list_tickets(self, limit: int = 10, state: str | None = None) -> None:
        """List tickets with optional filtering."""
        console.print("\n[bold]Fetching tickets...[/bold]")

        try:
            start_time = time.time()

            # Build search query
            search_params = {"limit": limit}
            if state:
                search_params["query"] = f"state.name:{state}"

            tickets = self.client.ticket.search(search_params)
            elapsed = time.time() - start_time

            if not tickets:
                console.print("[yellow]No tickets found[/yellow]")
                return

            # Create table
            table = Table(title=f"Tickets (fetched in {elapsed:.2f}s)")
            table.add_column("ID", style="cyan", width=6)
            table.add_column("Number", style="blue")
            table.add_column("Title", style="white", max_width=40)
            table.add_column("State", style="yellow")
            table.add_column("Priority", style="magenta")
            table.add_column("Customer", style="dim")
            table.add_column("Created", style="dim")

            for ticket in tickets[:limit]:
                created = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
                created_str = created.strftime("%Y-%m-%d %H:%M")

                table.add_row(
                    str(ticket["id"]),
                    ticket.get("number", ""),
                    ticket.get("title", ""),
                    ticket.get("state", ""),
                    ticket.get("priority", ""),
                    ticket.get("customer", ""),
                    created_str,
                )

            console.print(table)
            console.print(f"\n[dim]Showing {len(tickets)} of {len(tickets)} tickets[/dim]")

        except Exception as e:
            console.print(f"[red]Error fetching tickets:[/red] {e}")

    def get_ticket_details(self, ticket_id: int) -> None:
        """Get detailed ticket information."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Fetching ticket #{ticket_id}...", total=None)

                start_time = time.time()
                ticket = self.client.ticket.find(ticket_id)
                articles = self.client.ticket_article.by_ticket(ticket_id)
                elapsed = time.time() - start_time

            # Display ticket info
            console.print(
                Panel.fit(
                    f"[bold]Ticket #{ticket.get('number', ticket_id)}[/bold]\n{ticket.get('title', 'No title')}",
                    border_style="blue",
                )
            )

            # Ticket details
            details = Table(show_header=False)
            details.add_column("Property", style="cyan")
            details.add_column("Value")

            details.add_row("State", ticket.get("state", ""))
            details.add_row("Priority", ticket.get("priority", ""))
            details.add_row("Group", ticket.get("group", ""))
            details.add_row("Customer", ticket.get("customer", ""))
            details.add_row("Owner", ticket.get("owner", "Unassigned"))
            details.add_row("Created", ticket.get("created_at", ""))
            details.add_row("Updated", ticket.get("updated_at", ""))

            console.print(details)

            # Articles
            if articles:
                console.print(f"\n[bold]Articles ({len(articles)}):[/bold]")

                for i, article in enumerate(articles, 1):
                    tree = Tree(f"[bold]Article {i}[/bold]")
                    tree.add(f"From: {article.get('from', 'Unknown')}")
                    tree.add(f"Type: {article.get('type', 'Unknown')}")
                    tree.add(f"Created: {article.get('created_at', '')}")

                    # Show body preview
                    body = article.get("body", "").strip()
                    if body:
                        preview = body[:200] + "..." if len(body) > 200 else body
                        tree.add(f"Body: {preview}")

                    console.print(tree)

            console.print(f"\n[dim]Fetched in {elapsed:.2f}s[/dim]")

        except Exception as e:
            console.print(f"[red]Error fetching ticket:[/red] {e}")

    def create_test_ticket(self) -> None:
        """Create a test ticket interactively."""
        console.print("\n[bold]Create Test Ticket[/bold]")

        # Get ticket details
        title = questionary.text("Title:", default="Test ticket from API").ask()

        if not title:
            return

        # Get available groups
        try:
            groups = self.client.group.all()
            group_choices = [g["name"] for g in groups if g.get("active")]

            group = questionary.select(
                "Group:", choices=group_choices, default=group_choices[0] if group_choices else None
            ).ask()

            if not group:
                return

        except Exception:
            group = questionary.text("Group:", default="Users").ask()

        article_body = questionary.text(
            "Initial message:", multiline=True, default="This is a test ticket created via the API test client."
        ).ask()

        if not article_body:
            return

        # Create ticket
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Creating ticket...", total=None)

                start_time = time.time()
                if not self.user_info:
                    console.print("[red]Error:[/red] User information not available")
                    return
                ticket_data = {
                    "title": title,
                    "group": group,
                    "customer_id": self.user_info["id"],  # Use current user as customer
                    "article": {"body": article_body, "type": "note", "internal": False},
                }

                ticket = self.client.ticket.create(ticket_data)
                elapsed = time.time() - start_time

            console.print("\n[green]✓[/green] Ticket created successfully!")
            console.print(f"  ID: {ticket['id']}")
            console.print(f"  Number: {ticket['number']}")
            console.print(f"  Created in: {elapsed:.2f}s")

        except Exception as e:
            console.print(f"[red]Error creating ticket:[/red] {e}")

    def search_users(self, query: str) -> None:
        """Search for users."""
        try:
            start_time = time.time()
            users = self.client.user.search({"query": query, "limit": 10})
            elapsed = time.time() - start_time

            if not users:
                console.print("[yellow]No users found[/yellow]")
                return

            table = Table(title=f"Users matching '{query}' ({elapsed:.2f}s)")
            table.add_column("ID", style="cyan")
            table.add_column("Login", style="blue")
            table.add_column("Name", style="white")
            table.add_column("Email", style="dim")
            table.add_column("Active", justify="center")

            for user in users:
                name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
                table.add_row(
                    str(user["id"]),
                    user.get("login", ""),
                    name or "N/A",
                    user.get("email", ""),
                    "✓" if user.get("active") else "✗",
                )

            console.print(table)

        except Exception as e:
            console.print(f"[red]Error searching users:[/red] {e}")

    def run_benchmark(self) -> None:
        """Run performance benchmark tests."""
        console.print("\n[bold]Running Performance Benchmark[/bold]")

        tests = [
            ("Get current user", lambda: self.client.user.me()),
            ("List first 10 tickets", lambda: self.client.ticket.search({"limit": 10})),
            ("List groups", lambda: self.client.group.all()),
            ("List ticket states", lambda: self.client.ticket_state.all()),
            ("List priorities", lambda: self.client.ticket_priority.all()),
        ]

        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            for test_name, test_func in tests:
                task = progress.add_task(f"Testing: {test_name}", total=None)

                try:
                    # Run test 3 times and average
                    times = []
                    for _ in range(3):
                        start = time.time()
                        test_func()
                        times.append(time.time() - start)

                    avg_time = sum(times) / len(times)
                    min_time = min(times)
                    max_time = max(times)

                    results.append(
                        {"test": test_name, "avg": avg_time, "min": min_time, "max": max_time, "status": "✓"}
                    )

                except Exception as e:
                    results.append({"test": test_name, "avg": 0, "min": 0, "max": 0, "status": "✗", "error": str(e)})

                progress.remove_task(task)

        # Display results
        table = Table(title="Benchmark Results")
        table.add_column("Test", style="cyan")
        table.add_column("Avg Time", justify="right", style="yellow")
        table.add_column("Min", justify="right", style="dim")
        table.add_column("Max", justify="right", style="dim")
        table.add_column("Status", justify="center")

        for result in results:
            if result["status"] == "✓":
                table.add_row(
                    result["test"],
                    f"{result['avg']:.3f}s",
                    f"{result['min']:.3f}s",
                    f"{result['max']:.3f}s",
                    "[green]✓[/green]",
                )
            else:
                table.add_row(result["test"], "-", "-", "-", f"[red]✗[/red] {result.get('error', '')}")

        console.print(table)

        # Summary
        successful = sum(1 for r in results if r["status"] == "✓")
        total_avg = sum(r["avg"] for r in results if r["status"] == "✓")

        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Successful tests: {successful}/{len(tests)}")
        if successful > 0:
            console.print(f"  Total average time: {total_avg:.3f}s")
            console.print(f"  Average per operation: {total_avg / successful:.3f}s")

    def interactive_mode(self) -> None:
        """Run in interactive mode."""
        console.print(
            Panel.fit("[bold]Zammad API Test Client[/bold]\nInteractive mode - explore the API", border_style="blue")
        )

        while True:
            choices = [
                "List tickets",
                "Get ticket details",
                "Create test ticket",
                "Search users",
                "List groups",
                "List ticket states",
                "List priorities",
                "Run benchmark",
                "Show API info",
                "Exit",
            ]

            action = questionary.select("\nWhat would you like to do?", choices=choices).ask()

            if not action or action == "Exit":
                break

            try:
                if action == "List tickets":
                    limit = questionary.text("How many tickets?", default="10", validate=lambda x: x.isdigit()).ask()

                    state = questionary.text("Filter by state (optional):", default="").ask()

                    self.list_tickets(int(limit), state if state else None)

                elif action == "Get ticket details":
                    ticket_id = questionary.text("Ticket ID:", validate=lambda x: x.isdigit()).ask()

                    if ticket_id:
                        self.get_ticket_details(int(ticket_id))

                elif action == "Create test ticket":
                    self.create_test_ticket()

                elif action == "Search users":
                    query = questionary.text("Search query:", default="admin").ask()

                    if query:
                        self.search_users(query)

                elif action == "List groups":
                    groups = self.client.group.all()
                    table = Table(title="Groups")
                    table.add_column("ID", style="cyan")
                    table.add_column("Name", style="white")
                    table.add_column("Active", justify="center")

                    for group in groups:
                        table.add_row(str(group["id"]), group.get("name", ""), "✓" if group.get("active") else "✗")
                    console.print(table)

                elif action == "List ticket states":
                    states = self.client.ticket_state.all()
                    table = Table(title="Ticket States")
                    table.add_column("ID", style="cyan")
                    table.add_column("Name", style="white")
                    table.add_column("State Type", style="yellow")

                    for state in states:
                        table.add_row(
                            str(state["id"]), state.get("name", ""), state.get("state_type", {}).get("name", "")
                        )
                    console.print(table)

                elif action == "List priorities":
                    priorities = self.client.ticket_priority.all()
                    table = Table(title="Ticket Priorities")
                    table.add_column("ID", style="cyan")
                    table.add_column("Name", style="white")
                    table.add_column("Active", justify="center")

                    for priority in priorities:
                        table.add_row(
                            str(priority["id"]), priority.get("name", ""), "✓" if priority.get("active") else "✗"
                        )
                    console.print(table)

                elif action == "Run benchmark":
                    self.run_benchmark()

                elif action == "Show API info":
                    info = {
                        "API URL": self.url,
                        "Auth Method": (
                            "HTTP Token"
                            if self.http_token
                            else "OAuth2 Token"
                            if self.oauth2_token
                            else "Username/Password"
                        ),
                        "Connected": "Yes" if self.connected else "No",
                        "User": self.user_info.get("email", "Unknown") if self.user_info else "N/A",
                    }

                    table = Table(title="API Configuration", show_header=False)
                    table.add_column("Property", style="cyan")
                    table.add_column("Value", style="white")

                    for key, value in info.items():
                        table.add_row(key, value)

                    console.print(table)

            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled[/yellow]")
                continue
            except Exception as e:
                console.print(f"\n[red]Error:[/red] {e}")
                continue


@click.command()
@click.option(
    "--env-file", type=click.Path(exists=False, path_type=Path), help="Path to environment file (default: .env)"
)
@click.option(
    "--operation",
    type=click.Choice(["list-tickets", "list-users", "list-groups", "benchmark", "info"]),
    help="Run specific operation (non-interactive)",
)
@click.option("--limit", type=int, default=10, help="Limit results for list operations")
@click.option("--benchmark", is_flag=True, help="Run performance benchmark")
def main(env_file: Path | None, operation: str | None, limit: int, benchmark: bool):
    """Interactive Zammad API test client."""

    client = ZammadTestClient(env_file)

    # Load configuration
    if not client.load_config():
        sys.exit(1)

    # Connect to API
    console.print(Panel.fit(f"[bold]Connecting to Zammad[/bold]\n{client.url}", border_style="blue"))

    if not client.connect():
        sys.exit(1)

    # Display user info
    client.display_user_info()

    # Handle operations
    if benchmark or operation == "benchmark":
        client.run_benchmark()
    elif operation == "list-tickets":
        client.list_tickets(limit)
    elif operation == "list-groups":
        if not client.client:
            console.print("[red]Error:[/red] Not connected to Zammad API")
            sys.exit(1)
        groups = client.client.group.all()
        for group in groups[:limit]:
            console.print(f"  {group['id']}: {group['name']}")
    elif operation == "info":
        # Info already displayed
        # Info already displayed
        pass
    else:
        # Interactive mode
        client.interactive_mode()

    console.print("\n[dim]Goodbye![/dim]")


if __name__ == "__main__":
    main()
