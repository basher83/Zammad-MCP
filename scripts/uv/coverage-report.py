#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "coverage[toml]>=7.0.0",
#   "jinja2>=3.0.0",
#   "rich>=13.0.0",
#   "matplotlib>=3.5.0",
#   "click>=8.0.0",
#   "lxml>=4.9.0",
#   "defusedxml>=0.7.1",
# ]
# requires-python = ">=3.10"
# ///
"""
Generate beautiful, actionable coverage reports for Zammad MCP.

This script parses coverage data and generates various report formats:
- Terminal output with Rich formatting
- Markdown reports suitable for PR comments
- HTML dashboards with visualizations
- Coverage trend tracking over time

Usage:
    ./coverage-report.py                    # Default terminal output
    ./coverage-report.py --format markdown  # Generate PR-friendly markdown
    ./coverage-report.py --format html      # Generate HTML dashboard
    ./coverage-report.py --show-uncovered   # List uncovered lines
    ./coverage-report.py --compare-to 80    # Compare against target
    uv run coverage-report.py              # Run without making executable
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import click
import defusedxml.ElementTree as ET  # noqa: N817
import matplotlib.pyplot as plt
from jinja2 import Template
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console()


class FileCoverage(NamedTuple):
    """Coverage data for a single file."""

    filename: str
    statements: int
    missing: int
    covered: int
    coverage: float
    missing_lines: list[int]


class CoverageReport:
    """Coverage report data container."""

    def __init__(self, coverage_file: Path = Path("coverage.xml")):
        self.coverage_file = coverage_file
        self.files: list[FileCoverage] = []
        self.total_statements = 0
        self.total_covered = 0
        self.total_missing = 0
        self.overall_coverage = 0.0

    def parse(self) -> None:
        """Parse coverage XML file."""
        if not self.coverage_file.exists():
            console.print(f"[red]Error:[/red] Coverage file '{self.coverage_file}' not found")
            console.print("Run [cyan]uv run pytest --cov=mcp_zammad --cov-report=xml[/cyan] first")
            sys.exit(1)

        tree = ET.parse(self.coverage_file)
        root = tree.getroot()

        # Get overall coverage
        self.overall_coverage = float(root.attrib.get("line-rate", 0)) * 100

        # Parse packages and classes
        for package in root.findall(".//package"):
            for class_elem in package.findall("classes/class"):
                filename = class_elem.attrib["filename"]

                # Skip test files unless explicitly included
                if "test_" in filename or "_test.py" in filename:
                    continue

                lines = class_elem.findall("lines/line")
                total_lines = len(lines)
                covered_lines = sum(1 for line in lines if line.attrib.get("hits", "0") != "0")
                missing_lines = [int(line.attrib["number"]) for line in lines if line.attrib.get("hits", "0") == "0"]

                coverage = (covered_lines / total_lines * 100) if total_lines > 0 else 0

                self.files.append(
                    FileCoverage(
                        filename=filename,
                        statements=total_lines,
                        covered=covered_lines,
                        missing=total_lines - covered_lines,
                        coverage=coverage,
                        missing_lines=missing_lines,
                    )
                )

                self.total_statements += total_lines
                self.total_covered += covered_lines

        self.total_missing = self.total_statements - self.total_covered

        # Sort files by coverage (lowest first)
        self.files.sort(key=lambda f: f.coverage)


def format_coverage_percent(coverage: float, target: float = 80.0) -> Text:
    """Format coverage percentage with color based on target."""
    if coverage >= target:
        color = "green"
    elif coverage >= target * 0.75:  # 75% of target
        color = "yellow"
    else:
        color = "red"

    return Text(f"{coverage:.1f}%", style=color)


def generate_terminal_report(report: CoverageReport, show_uncovered: bool = False, target: float = 80.0) -> None:
    """Generate a rich terminal report."""
    # Overall summary panel
    summary_text = Text()
    summary_text.append("Overall Coverage: ")
    summary_text.append(format_coverage_percent(report.overall_coverage, target))
    summary_text.append(f"\nStatements: {report.total_statements}")
    summary_text.append(f"\nCovered: {report.total_covered}")
    summary_text.append(f"\nMissing: {report.total_missing}")

    console.print(Panel(summary_text, title="[bold]Coverage Summary[/bold]", border_style="blue"))

    # File coverage table
    table = Table(title="File Coverage", show_header=True)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Statements", justify="right")
    table.add_column("Missing", justify="right")
    table.add_column("Coverage", justify="right")
    table.add_column("Status", justify="center")

    for file in report.files:
        # Shorten filename for display
        display_name = file.filename
        if len(display_name) > 50:
            display_name = "..." + display_name[-47:]

        status = "✓" if file.coverage >= target else "✗"
        status_color = "green" if file.coverage >= target else "red"

        table.add_row(
            display_name,
            str(file.statements),
            str(file.missing),
            format_coverage_percent(file.coverage, target),
            Text(status, style=status_color),
        )

    console.print(table)

    # Show uncovered lines if requested
    if show_uncovered and report.files:
        console.print("\n[bold]Uncovered Lines:[/bold]")
        tree = Tree("[bold]Files with missing coverage[/bold]")

        for file in report.files:
            if file.missing > 0:
                file_branch = tree.add(f"[cyan]{file.filename}[/cyan] ({file.missing} lines)")

                # Group consecutive lines
                if file.missing_lines:
                    ranges = []
                    start = file.missing_lines[0]
                    end = start

                    for line in file.missing_lines[1:]:
                        if line == end + 1:
                            end = line
                        else:
                            ranges.append((start, end))
                            start = end = line
                    ranges.append((start, end))

                    # Display line ranges
                    range_strs = []
                    for start, end in ranges:
                        if start == end:
                            range_strs.append(str(start))
                        else:
                            range_strs.append(f"{start}-{end}")

                    file_branch.add(f"[dim]Lines: {', '.join(range_strs)}[/dim]")

        console.print(tree)

    # Coverage bar
    console.print("\n[bold]Coverage Distribution:[/bold]")
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Coverage", total=report.total_statements)
        progress.update(task, completed=report.total_covered)


def generate_markdown_report(report: CoverageReport, target: float = 80.0) -> str:
    """Generate a markdown report suitable for PR comments."""
    lines = []

    # Header
    lines.append("## 📊 Coverage Report\n")

    # Summary
    emoji = "✅" if report.overall_coverage >= target else "⚠️"
    lines.append(f"{emoji} **Overall Coverage**: {report.overall_coverage:.1f}%")
    lines.append(f"- **Statements**: {report.total_statements}")
    lines.append(f"- **Covered**: {report.total_covered}")
    lines.append(f"- **Missing**: {report.total_missing}\n")

    # File details
    lines.append("### File Coverage\n")
    lines.append("| File | Coverage | Missing | Status |")
    lines.append("|------|----------|---------|--------|")

    for file in report.files[:10]:  # Show top 10 files needing attention
        status = "✅" if file.coverage >= target else "❌"
        # Make path relative to project root
        display_path = file.filename.replace("mcp_zammad/", "")
        lines.append(f"| `{display_path}` | {file.coverage:.1f}% | {file.missing} | {status} |")

    if len(report.files) > 10:
        lines.append(f"\n*... and {len(report.files) - 10} more files*")

    # Target comparison
    lines.append(f"\n### Target: {target}%\n")
    if report.overall_coverage >= target:
        lines.append("🎉 **Target met!** Great job maintaining code coverage.")
    else:
        deficit = target - report.overall_coverage
        lines_needed = int((deficit / 100) * report.total_statements)
        lines.append(f"📈 **{deficit:.1f}% below target** - need to cover ~{lines_needed} more lines")

    # Suggestions
    if report.total_missing > 0:
        lines.append("\n### Next Steps\n")
        lines.append("Focus on files with the lowest coverage:")
        for i, file in enumerate(report.files[:3], 1):
            display_path = file.filename.replace("mcp_zammad/", "")
            lines.append(f"{i}. `{display_path}` - {file.missing} lines missing")

    return "\n".join(lines)


def generate_html_dashboard(report: CoverageReport, output_path: Path, target: float = 80.0) -> None:
    """Generate an HTML dashboard with visualizations."""
    # Create coverage chart
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    # Pie chart for overall coverage
    sizes = [report.total_covered, report.total_missing]
    colors = ["#4CAF50", "#f44336"]
    explode = (0.05, 0)

    ax1.pie(sizes, explode=explode, labels=["Covered", "Missing"], colors=colors, autopct="%1.1f%%", startangle=90)
    ax1.set_title("Overall Coverage")

    # Bar chart for file coverage
    files_to_show = min(10, len(report.files))
    file_names = [Path(f.filename).name for f in report.files[:files_to_show]]
    coverages = [f.coverage for f in report.files[:files_to_show]]

    bars = ax2.bar(range(files_to_show), coverages)

    # Color bars based on coverage
    for i, (bar, coverage) in enumerate(zip(bars, coverages, strict=False)):
        if coverage >= target:
            bar.set_color("#4CAF50")
        elif coverage >= target * 0.75:
            bar.set_color("#FFC107")
        else:
            bar.set_color("#f44336")

    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Coverage %")
    ax2.set_title("Files Needing Attention")
    ax2.set_xticks(range(files_to_show))
    ax2.set_xticklabels(file_names, rotation=45, ha="right")

    # Add target line
    ax2.axhline(y=target, color="blue", linestyle="--", alpha=0.7, label=f"Target ({target}%)")
    ax2.legend()

    plt.tight_layout()

    # Save chart
    chart_path = output_path.parent / "coverage_chart.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()

    # Generate HTML
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Coverage Report - Zammad MCP</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metric {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-label {
            color: #666;
            font-size: 0.9em;
        }
        .good { color: #4CAF50; }
        .warning { color: #FFC107; }
        .bad { color: #f44336; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .chart {
            text-align: center;
            margin: 30px 0;
        }
        .timestamp {
            text-align: right;
            color: #666;
            font-size: 0.9em;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Coverage Report - Zammad MCP</h1>
        
        <div class="summary">
            <div class="metric">
                <div class="metric-label">Overall Coverage</div>
                <div class="metric-value {{ coverage_class }}">{{ overall_coverage }}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Statements</div>
                <div class="metric-value">{{ total_statements }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Covered Lines</div>
                <div class="metric-value good">{{ total_covered }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Missing Lines</div>
                <div class="metric-value bad">{{ total_missing }}</div>
            </div>
        </div>
        
        <div class="chart">
            <img src="coverage_chart.png" alt="Coverage Chart" style="max-width: 100%;">
        </div>
        
        <h2>File Coverage Details</h2>
        <table>
            <thead>
                <tr>
                    <th>File</th>
                    <th>Statements</th>
                    <th>Missing</th>
                    <th>Coverage</th>
                </tr>
            </thead>
            <tbody>
                {% for file in files %}
                <tr>
                    <td><code>{{ file.filename }}</code></td>
                    <td>{{ file.statements }}</td>
                    <td>{{ file.missing }}</td>
                    <td class="{{ file.coverage_class }}">{{ file.coverage }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="timestamp">
            Generated on {{ timestamp }}
        </div>
    </div>
</body>
</html>
    """

    # Prepare template data
    def get_coverage_class(coverage: float) -> str:
        if coverage >= target:
            return "good"
        elif coverage >= target * 0.75:
            return "warning"
        else:
            return "bad"

    template_data = {
        "overall_coverage": f"{report.overall_coverage:.1f}",
        "coverage_class": get_coverage_class(report.overall_coverage),
        "total_statements": report.total_statements,
        "total_covered": report.total_covered,
        "total_missing": report.total_missing,
        "files": [
            {
                "filename": file.filename,
                "statements": file.statements,
                "missing": file.missing,
                "coverage": f"{file.coverage:.1f}",
                "coverage_class": get_coverage_class(file.coverage),
            }
            for file in report.files
        ],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Render and save HTML
    template = Template(html_template)
    html_content = template.render(**template_data)

    output_path.write_text(html_content)
    console.print(f"[green]✓[/green] HTML dashboard saved to {output_path}")
    console.print(f"[green]✓[/green] Coverage chart saved to {chart_path}")


def save_coverage_history(report: CoverageReport, history_file: Path = Path(".coverage_history.json")) -> None:
    """Save coverage data to history file for trend tracking."""
    history = []

    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
        except json.JSONDecodeError:
            console.print("[yellow]Warning:[/yellow] Could not parse history file, starting fresh")

    # Add current data
    history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "overall_coverage": report.overall_coverage,
            "total_statements": report.total_statements,
            "total_covered": report.total_covered,
            "total_missing": report.total_missing,
        }
    )

    # Keep only last 30 entries
    history = history[-30:]

    history_file.write_text(json.dumps(history, indent=2))


@click.command()
@click.option(
    "--coverage-file",
    type=click.Path(exists=False, path_type=Path),
    default="coverage.xml",
    help="Path to coverage XML file",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "markdown", "html"]),
    default="terminal",
    help="Output format",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file (for markdown/html formats)",
)
@click.option(
    "--show-uncovered",
    is_flag=True,
    help="Show uncovered lines in terminal output",
)
@click.option(
    "--compare-to",
    "target",
    type=float,
    default=80.0,
    help="Target coverage percentage",
)
@click.option(
    "--save-history",
    is_flag=True,
    help="Save coverage data to history file",
)
def main(
    coverage_file: Path,
    output_format: str,
    output: Path | None,
    show_uncovered: bool,
    target: float,
    save_history: bool,
):
    """Generate beautiful, actionable coverage reports."""

    console.print(
        Panel.fit("[bold]Coverage Report Generator[/bold]\n" f"Analyzing {coverage_file}...", border_style="blue")
    )

    # Parse coverage data
    report = CoverageReport(coverage_file)
    try:
        report.parse()
    except Exception as e:
        console.print(f"[red]Error parsing coverage file:[/red] {e}")
        sys.exit(1)

    # Save history if requested
    if save_history:
        save_coverage_history(report)
        console.print("[dim]Coverage history updated[/dim]")

    # Generate appropriate report
    if output_format == "terminal":
        generate_terminal_report(report, show_uncovered, target)

    elif output_format == "markdown":
        markdown_content = generate_markdown_report(report, target)

        if output:
            output.write_text(markdown_content)
            console.print(f"[green]✓[/green] Markdown report saved to {output}")
        else:
            console.print("\n" + markdown_content)

    elif output_format == "html":
        if not output:
            output = Path("coverage_report.html")

        generate_html_dashboard(report, output, target)

    # Exit with appropriate code
    if report.overall_coverage < target:
        console.print(f"\n[yellow]Coverage {report.overall_coverage:.1f}% is below target {target}%[/yellow]")
        sys.exit(1)
    else:
        console.print(f"\n[green]Coverage {report.overall_coverage:.1f}% meets target {target}%[/green]")


if __name__ == "__main__":
    main()
