#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "click>=8.0.0",
#   "rich>=13.0.0",
#   "python-dotenv>=1.0.0",
#   "questionary>=2.0.0",
#   "httpx>=0.25.0",
# ]
# requires-python = ">=3.10"
# ///
"""
Interactive development setup wizard for Zammad MCP Server.

This script guides new contributors through the complete setup process including:
- System requirements verification
- UV installation (if needed)
- Virtual environment creation
- Interactive .env configuration
- Dependency installation
- Initial validation and testing

Usage:
    ./dev-setup.py              # Run interactive setup
    ./dev-setup.py --quick      # Quick setup with defaults
    ./dev-setup.py --check-only # Only check requirements
    uv run dev-setup.py        # Run without making executable
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import click
import questionary
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


class SetupWizard:
    """Interactive setup wizard for Zammad MCP development."""

    def __init__(self, quick_mode: bool = False):
        self.quick_mode = quick_mode
        self.project_root = Path.cwd()
        self.env_file = self.project_root / ".env"
        self.env_example = self.project_root / ".env.example"
        self.checks_passed = True

    def run(self) -> None:
        """Run the complete setup wizard."""
        console.print(
            Panel.fit(
                "[bold]🚀 Zammad MCP Development Setup Wizard[/bold]\nLet's get your development environment ready!",
                border_style="blue",
            )
        )

        # Step 1: Check system requirements
        if not self.check_system_requirements():
            return

        # Step 2: Check/install UV
        if not self.check_uv_installation():
            return

        # Step 3: Setup virtual environment
        if not self.setup_virtual_environment():
            return

        # Step 4: Configure environment
        if not self.configure_environment():
            return

        # Step 5: Install dependencies
        if not self.install_dependencies():
            return

        # Step 6: Run validation
        if not self.validate_setup():
            return

        # Step 7: Show next steps
        self.show_next_steps()

    def check_system_requirements(self) -> bool:
        """Check system requirements."""
        console.print("\n[bold]📋 Checking System Requirements[/bold]")

        requirements = Table(show_header=True)
        requirements.add_column("Requirement", style="cyan")
        requirements.add_column("Status", justify="center")
        requirements.add_column("Details", style="dim")

        # Check Python version
        python_version = sys.version_info
        python_ok = python_version >= (3, 10)
        requirements.add_row(
            "Python 3.10+",
            "✅" if python_ok else "❌",
            f"Found {python_version.major}.{python_version.minor}.{python_version.micro}",
        )

        # Check Git
        git_installed = shutil.which("git") is not None
        requirements.add_row("Git", "✅" if git_installed else "❌", "Required for version control")

        # Check operating system
        # Check operating system
        os_name = platform.system()
        os_supported = os_name in ["Linux", "Darwin", "Windows"]
        os_status = "✅" if os_supported else "⚠️"
        os_details = f"{os_name} ({platform.machine()})"
        if not os_supported:
            os_details += " - Untested, may still work"
        requirements.add_row("Operating System", os_status, os_details)
        # Check project structure
        required_files = ["pyproject.toml", "README.md", "mcp_zammad/__init__.py"]
        files_exist = all((self.project_root / f).exists() for f in required_files)
        requirements.add_row("Project Structure", "✅" if files_exist else "❌", "Required project files")

        console.print(requirements)

        all_ok = python_ok and git_installed and files_exist
        if not all_ok:
            console.print("\n[red]❌ Some requirements are not met.[/red]")
            if not python_ok:
                console.print("  • Install Python 3.10 or higher")
            if not git_installed:
                console.print("  • Install Git")
            if not files_exist:
                console.print("  • Ensure you're in the project root directory")
            return False

        console.print("\n[green]✅ All system requirements met![/green]")
        return True

    def check_uv_installation(self) -> bool:
        """Check if UV is installed and offer to install if not."""
        console.print("\n[bold]🔧 Checking UV Installation[/bold]")

        uv_path = shutil.which("uv")
        if uv_path:
            # Get UV version
            try:
                result = subprocess.run(["uv", "--version"], capture_output=True, text=True, check=False)
                version = result.stdout.strip()
                console.print(f"[green]✅ UV is installed:[/green] {version}")
                console.print(f"   Path: {uv_path}")
                return True
            except Exception:
                pass

        console.print("[yellow]⚠️  UV is not installed[/yellow]")
        console.print("[dim]UV is required for Python dependency management in this project.[/dim]")

        if self.quick_mode or questionary.confirm("Would you like to install UV now?", default=True).ask():
            return self.install_uv()
        else:
            console.print("\n[red]UV is required to continue.[/red]")
            console.print("Install it manually: https://github.com/astral-sh/uv")
            return False

    def install_uv(self) -> bool:
        """Install UV package manager."""
        console.print("\n[bold]Installing UV...[/bold]")

        system = platform.system()

        # Security notice
        console.print("\n[yellow]⚠️  Security Notice:[/yellow]")
        console.print("This will download and execute an installation script from the internet.")
        console.print("UV is the official Python package manager from Astral (creators of Ruff).")
        console.print("Learn more: https://github.com/astral-sh/uv\n")

        try:
            if system in ["Linux", "Darwin"]:
                # Unix-like systems
                console.print("[yellow]Running UV installer from https://astral.sh[/yellow]")
                console.print("[dim]This will download and execute an installation script.[/dim]")
                cmd = "curl -LsSf https://astral.sh/uv/install.sh | sh"
                subprocess.run(cmd, shell=True, check=True)

                # Add to PATH for current session
                home = Path.home()
                cargo_bin = home / ".cargo" / "bin"
                if cargo_bin.exists():
                    os.environ["PATH"] = f"{cargo_bin}:{os.environ.get('PATH', '')}"
                    console.print("\n[yellow]Note: PATH updated for current session only.[/yellow]")
                    console.print("[dim]Add ~/.cargo/bin to your shell's PATH permanently.[/dim]")

            elif system == "Windows":
                # Windows
                console.print("[yellow]Running UV installer from https://astral.sh[/yellow]")
                console.print("[dim]This will download and execute an installation script.[/dim]")
                cmd = 'powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
                subprocess.run(cmd, shell=True, check=True)
            else:
                console.print(f"[red]Unsupported system: {system}[/red]")
                return False

            # Verify installation
            if shutil.which("uv"):
                console.print("[green]✅ UV installed successfully![/green]")
                return True
            else:
                console.print("[yellow]⚠️  UV installed but not in PATH.[/yellow]")
                console.print("Please restart your terminal or add UV to your PATH.")
                return False

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to install UV: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
            return False

    def setup_virtual_environment(self) -> bool:
        """Setup Python virtual environment."""
        console.print("\n[bold]🐍 Setting Up Virtual Environment[/bold]")

        venv_path = self.project_root / ".venv"

        if venv_path.exists():
            console.print("[yellow]Virtual environment already exists[/yellow]")
            if not self.quick_mode and questionary.confirm("Would you like to recreate it?", default=False).ask():
                console.print("Removing existing virtual environment...")
                shutil.rmtree(venv_path)
            else:
                console.print("[green]✅ Using existing virtual environment[/green]")
                return True

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Creating virtual environment...", total=None)
                subprocess.run(["uv", "venv"], check=True, capture_output=True)

            console.print("[green]✅ Virtual environment created[/green]")

            # Show activation instructions
            system = platform.system()
            if system == "Windows":
                activate_cmd = ".venv\\Scripts\\activate"
            else:
                activate_cmd = "source .venv/bin/activate"

            console.print(f"\n[dim]To activate: {activate_cmd}[/dim]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to create virtual environment: {e}[/red]")
            return False

    def configure_environment(self) -> bool:
        """Configure .env file interactively."""
        console.print("\n[bold]⚙️  Configuring Environment[/bold]")

        # Check for existing .env
        if self.env_file.exists():
            console.print("[yellow]Found existing .env file[/yellow]")
            if (
                not self.quick_mode
                and not questionary.confirm("Would you like to reconfigure it?", default=False).ask()
            ):
                console.print("[green]✅ Using existing configuration[/green]")
                return True

        # Copy from example if it doesn't exist
        if not self.env_file.exists() and self.env_example.exists():
            console.print("Creating .env from .env.example...")
            shutil.copy(self.env_example, self.env_file)

        # Interactive configuration
        if self.quick_mode:
            console.print("[yellow]Quick mode: Using default configuration[/yellow]")
            console.print("[yellow]Please edit .env file manually with your Zammad credentials[/yellow]")
            return True

        console.print("\n[bold]Let's configure your Zammad connection:[/bold]")

        # Get Zammad URL
        current_url = os.getenv("ZAMMAD_URL", "")
        zammad_url = questionary.text(
            "Zammad instance URL:",
            default=current_url if current_url else "https://your-instance.zammad.com/api/v1",
            validate=lambda x: len(x) > 0 and x.startswith(("http://", "https://")),
        ).ask()

        if not zammad_url:
            return False

        # Normalize URL to ensure it ends with /api/v1
        try:
            from utils import normalize_zammad_url

            zammad_url = normalize_zammad_url(zammad_url)
        except (ImportError, ValueError) as e:
            console.print(f"[red]Error normalizing URL:[/red] {e}")
            return False

        # Choose authentication method
        auth_method = questionary.select(
            "Authentication method:", choices=["API Token (recommended)", "OAuth2 Token", "Username/Password"]
        ).ask()

        if not auth_method:
            return False

        # Get credentials based on method
        env_vars = {"ZAMMAD_URL": zammad_url}

        if auth_method == "API Token (recommended)":
            token = questionary.password("API Token:", validate=lambda x: len(x) > 0).ask()
            if token:
                env_vars["ZAMMAD_HTTP_TOKEN"] = token

        elif auth_method == "OAuth2 Token":
            token = questionary.password("OAuth2 Token:", validate=lambda x: len(x) > 0).ask()
            if token:
                env_vars["ZAMMAD_OAUTH2_TOKEN"] = token

        else:  # Username/Password
            username = questionary.text("Username:", validate=lambda x: len(x) > 0).ask()
            password = questionary.password("Password:", validate=lambda x: len(x) > 0).ask()
            if username and password:
                env_vars["ZAMMAD_USERNAME"] = username
                env_vars["ZAMMAD_PASSWORD"] = password

        # Write to .env file
        console.print("\nSaving configuration...")
        for key, value in env_vars.items():
            set_key(self.env_file, key, value)

        console.print("[green]✅ Environment configured[/green]")
        return True

    def install_dependencies(self) -> bool:
        """Install project dependencies."""
        console.print("\n[bold]📦 Installing Dependencies[/bold]")

        try:
            # Install main dependencies
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Installing project dependencies...", total=None)

                result = subprocess.run(
                    ["uv", "pip", "install", "-e", ".[dev]"], capture_output=True, text=True, check=False
                )

                if result.returncode != 0:
                    console.print(f"[red]Error: {result.stderr}[/red]")
                    return False

            console.print("[green]✅ Dependencies installed[/green]")

            # Show installed packages summary
            result = subprocess.run(["uv", "pip", "list"], capture_output=True, text=True, check=False)

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                # Count relevant packages
                mcp_packages = [l for l in lines if "mcp" in l.lower()]
                dev_packages = [l for l in lines if any(p in l.lower() for p in ["pytest", "ruff", "mypy"])]

                console.print(f"\n[dim]Installed {len(lines)} packages[/dim]")
                console.print(f"[dim]Including {len(mcp_packages)} MCP-related packages[/dim]")
                console.print(f"[dim]And {len(dev_packages)} development tools[/dim]")

            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to install dependencies: {e}[/red]")
            return False

    def validate_setup(self) -> bool:
        """Validate the setup by running checks."""
        console.print("\n[bold]✓ Validating Setup[/bold]")

        if self.quick_mode:
            console.print("[yellow]Quick mode: Skipping validation[/yellow]")
            return True

        # Load environment
        load_dotenv(self.env_file)

        # Try to import the package
        console.print("Checking package installation...")
        try:
            import mcp_zammad

            console.print("[green]✅ Package imports successfully[/green]")
        except ImportError as e:
            console.print(f"[red]❌ Import error: {e}[/red]")
            return False

        # Run environment validation if available
        validate_script = self.project_root / "scripts" / "uv" / "validate-env.py"
        if validate_script.exists():
            console.print("\nRunning environment validation...")
            try:
                result = subprocess.run(
                    ["uv", "run", str(validate_script), "--no-test-connection"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    console.print("[green]✅ Environment validation passed[/green]")
                else:
                    console.print("[yellow]⚠️  Environment validation had issues[/yellow]")
                    console.print("[dim]Run ./scripts/uv/validate-env.py for details[/dim]")
            except Exception as e:
                console.print(f"[yellow]Could not run validation: {e}[/yellow]")

        # Quick syntax check
        console.print("\nRunning quick syntax check...")
        try:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "py_compile", "mcp_zammad/server.py"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                console.print("[green]✅ Python syntax check passed[/green]")
            else:
                console.print(f"[red]❌ Syntax error: {result.stderr}[/red]")
                return False

        except Exception as e:
            console.print(f"[yellow]Could not run syntax check: {e}[/yellow]")

        return True

    def show_next_steps(self) -> None:
        """Show next steps for development."""
        console.print("\n" + "=" * 50)
        console.print(
            Panel.fit(
                "[bold green]🎉 Setup Complete![/bold green]\n\nYour development environment is ready.",
                border_style="green",
            )
        )

        console.print("\n[bold]📝 Next Steps:[/bold]\n")

        steps = [
            (
                "1. Activate virtual environment",
                ".venv\\Scripts\\activate" if platform.system() == "Windows" else "source .venv/bin/activate",
            ),
            ("2. Validate Zammad connection", "./scripts/uv/validate-env.py"),
            ("3. Run the MCP server", "uv run python -m mcp_zammad"),
            ("4. Run tests", "uv run pytest"),
            ("5. Check code quality", "./scripts/quality-check.sh"),
        ]

        for step, command in steps:
            console.print(f"  {step}")
            console.print(f"     [cyan]{command}[/cyan]\n")

        console.print("\n[bold]📚 Useful Resources:[/bold]")
        console.print("  • Project README: [link]README.md[/link]")
        console.print("  • Architecture docs: [link]ARCHITECTURE.md[/link]")
        console.print("  • Contributing guide: [link]CONTRIBUTING.md[/link]")
        console.print("  • MCP docs: [link]https://modelcontextprotocol.io[/link]")

        console.print("\n[bold]💡 Tips:[/bold]")
        console.print("  • Use [cyan]uv run[/cyan] to run any Python command in the project environment")
        console.print("  • Check [cyan].env[/cyan] file if you need to update credentials")
        console.print("  • Join discussions in GitHub Issues for questions")

        console.print("\n[dim]Happy coding! 🚀[/dim]")


@click.command()
@click.option(
    "--quick",
    is_flag=True,
    help="Quick setup with minimal prompts",
)
@click.option(
    "--check-only",
    is_flag=True,
    help="Only check requirements without setup",
)
def main(quick: bool, check_only: bool):
    """Interactive development setup wizard for Zammad MCP Server."""

    wizard = SetupWizard(quick_mode=quick)

    if check_only:
        console.print(
            Panel.fit(
                "[bold]🔍 Requirement Check Mode[/bold]\nChecking system requirements only...", border_style="blue"
            )
        )
        wizard.check_system_requirements()
        wizard.check_uv_installation()
    else:
        try:
            wizard.run()
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Setup cancelled by user[/yellow]")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]Unexpected error: {e}[/red]")
            console.print("[dim]Please report this issue on GitHub[/dim]")
            sys.exit(1)


if __name__ == "__main__":
    main()
