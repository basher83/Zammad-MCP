#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pip-audit>=2.6.0",
#   "bandit[sarif]>=1.7.6",
#   "rich>=13.0.0",
#   "pydantic>=2.0.0",
#   "click>=8.0.0",
#   "semgrep>=1.35.0",
# ]
# requires-python = ">=3.10"
# ///
"""
Unified security scanner for Zammad MCP Server.

This script runs multiple security tools and consolidates their output into
actionable reports with clear remediation guidance.

Security tools included:
- pip-audit: Checks for known vulnerabilities in dependencies
- bandit: Static security analysis for Python code
- semgrep: Advanced static analysis with security rules

Usage:
    ./security-scan.py                    # Run all security scans
    ./security-scan.py --tool pip-audit   # Run specific tool only
    ./security-scan.py --format sarif     # Output in SARIF format
    ./security-scan.py --severity high    # Show only high severity issues
    ./security-scan.py --fix              # Apply automatic fixes where possible
    uv run security-scan.py              # Run without making executable
"""

import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from enum import Enum
from pathlib import Path

import click
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


class Severity(str, Enum):
    """Security issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityIssue(BaseModel):
    """Individual security issue."""

    tool: str
    severity: Severity
    title: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    cwe_id: str | None = None
    cve_id: str | None = None
    package: str | None = None
    installed_version: str | None = None
    fixed_version: str | None = None
    remediation: str | None = None
    confidence: str | None = None


class SecurityReport(BaseModel):
    """Consolidated security report."""

    scan_timestamp: datetime = Field(default_factory=datetime.now)
    project_path: Path
    issues: list[SecurityIssue] = Field(default_factory=list)
    tools_run: list[str] = Field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def issues_by_severity(self) -> dict[Severity, int]:
        counts = defaultdict(int)
        for issue in self.issues:
            counts[issue.severity] += 1
        return dict(counts)

    @property
    def issues_by_tool(self) -> dict[str, int]:
        counts = defaultdict(int)
        for issue in self.issues:
            counts[issue.tool] += 1
        return dict(counts)

    def filter_by_severity(self, min_severity: Severity) -> list[SecurityIssue]:
        """Filter issues by minimum severity."""
        severity_order = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        min_index = severity_order.index(min_severity)

        return [issue for issue in self.issues if severity_order.index(issue.severity) >= min_index]


class SecurityScanner:
    """Unified security scanner orchestrator."""

    def __init__(self, project_path: Path = Path.cwd()):
        self.project_path = project_path
        self.report = SecurityReport(project_path=project_path)

    def run_all_scans(self, tools: list[str] | None = None) -> SecurityReport:
        """Run all or specified security scans."""
        available_tools = {
            "pip-audit": self.run_pip_audit,
            "bandit": self.run_bandit,
            "semgrep": self.run_semgrep,
        }

        tools_to_run = tools if tools else list(available_tools.keys())

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            for tool_name in tools_to_run:
                if tool_name in available_tools:
                    task = progress.add_task(f"Running {tool_name}...", total=None)
                    try:
                        available_tools[tool_name]()
                        self.report.tools_run.append(tool_name)
                    except Exception as e:
                        console.print(f"[yellow]Warning: {tool_name} failed: {e}[/yellow]")
                    progress.remove_task(task)
                else:
                    console.print(f"[yellow]Unknown tool: {tool_name}[/yellow]")

        return self.report

    def run_pip_audit(self) -> None:
        """Run pip-audit for dependency vulnerabilities."""
        try:
            result = subprocess.run(
                ["uv", "run", "pip-audit", "--format", "json", "--desc"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                check=False,
            )

            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                vulnerabilities = data.get("vulnerabilities", [])

                for vuln in vulnerabilities:
                    # Map pip-audit severity to our severity
                    severity_map = {
                        "CRITICAL": Severity.CRITICAL,
                        "HIGH": Severity.HIGH,
                        "MODERATE": Severity.MEDIUM,
                        "MEDIUM": Severity.MEDIUM,
                        "LOW": Severity.LOW,
                        "UNKNOWN": Severity.INFO,
                    }

                    # Get the highest severity from all vulns
                    vuln_severity = Severity.INFO
                    for v in vuln.get("vulns", []):
                        fix_versions = v.get("fix_versions", [])
                        severity_str = fix_versions[0].get("severity", "UNKNOWN") if fix_versions else "UNKNOWN"
                        sev = severity_map.get(severity_str, Severity.INFO)
                        if sev == Severity.CRITICAL:
                            vuln_severity = sev
                            break
                        elif (
                            sev == Severity.HIGH
                            and vuln_severity != Severity.CRITICAL
                            or sev == Severity.MEDIUM
                            and vuln_severity not in [Severity.CRITICAL, Severity.HIGH]
                            or sev == Severity.LOW
                            and vuln_severity == Severity.INFO
                        ):
                            vuln_severity = sev

                    # Extract CVE/details
                    cve_ids = []
                    descriptions = []
                    for v in vuln.get("vulns", []):
                        if v.get("id"):
                            cve_ids.append(v["id"])
                        if v.get("description"):
                            descriptions.append(v["description"])

                    # Extract fix version safely
                    vulns = vuln.get("vulns", [])
                    fix_version = None
                    if vulns and vulns[0].get("fix_versions"):
                        fix_version = vulns[0]["fix_versions"][0]

                    issue = SecurityIssue(
                        tool="pip-audit",
                        severity=vuln_severity,
                        title=f"Vulnerable dependency: {vuln['name']}",
                        description=descriptions[0] if descriptions else f"Known vulnerability in {vuln['name']}",
                        package=vuln["name"],
                        installed_version=vuln["version"],
                        fixed_version=fix_version,
                        cve_id=", ".join(cve_ids) if cve_ids else None,
                        remediation=f"Upgrade to {fix_version or 'a newer version'}",
                    )
                    self.report.issues.append(issue)

        except json.JSONDecodeError:
            console.print("[yellow]pip-audit output was not valid JSON[/yellow]")
        except Exception as e:
            console.print(f"[yellow]pip-audit error: {e}[/yellow]")

    def run_bandit(self) -> None:
        """Run bandit for static code analysis."""
        try:
            # Run bandit with JSON output
            result = subprocess.run(
                ["uv", "run", "bandit", "-r", "mcp_zammad", "-f", "json", "-ll"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                check=False,
            )

            if result.stdout:
                data = json.loads(result.stdout)

                # Map bandit severity and confidence
                severity_map = {
                    "HIGH": Severity.HIGH,
                    "MEDIUM": Severity.MEDIUM,
                    "LOW": Severity.LOW,
                }

                for finding in data.get("results", []):
                    issue = SecurityIssue(
                        tool="bandit",
                        severity=severity_map.get(finding["issue_severity"], Severity.INFO),
                        title=finding["issue_text"],
                        description=f"{finding['test_name']}: {finding['issue_text']}",
                        file_path=finding["filename"],
                        line_number=finding["line_number"],
                        cwe_id=f"CWE-{finding['issue_cwe']['id']}" if finding.get("issue_cwe") else None,
                        confidence=finding["issue_confidence"],
                        remediation="Review code and apply appropriate security measures",
                    )
                    self.report.issues.append(issue)

        except json.JSONDecodeError:
            console.print("[yellow]Bandit output was not valid JSON[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Bandit error: {e}[/yellow]")

    def run_semgrep(self) -> None:
        """Run semgrep for advanced static analysis."""
        try:
            # Run semgrep with auto config
            result = subprocess.run(
                ["uv", "run", "semgrep", "--config=auto", "--json", "mcp_zammad/"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                env={**os.environ, "SEMGREP_ENABLE_VERSION_CHECK": "0"},
                check=False,
            )

            if result.stdout:
                data = json.loads(result.stdout)

                # Map semgrep severity
                severity_map = {
                    "ERROR": Severity.HIGH,
                    "WARNING": Severity.MEDIUM,
                    "INFO": Severity.LOW,
                }

                for finding in data.get("results", []):
                    # Extract severity from metadata
                    metadata = finding.get("extra", {}).get("metadata", {})
                    severity_str = metadata.get("severity", "INFO")

                    issue = SecurityIssue(
                        tool="semgrep",
                        severity=severity_map.get(severity_str, Severity.INFO),
                        title=finding.get("extra", {}).get("message", "Security issue found"),
                        description=finding.get("extra", {}).get("metadata", {}).get("description", ""),
                        file_path=finding["path"],
                        line_number=finding["start"]["line"],
                        cwe_id=metadata.get("cwe"),
                        remediation=metadata.get("fix", "Review and fix the security issue"),
                    )
                    self.report.issues.append(issue)

        except json.JSONDecodeError:
            console.print("[yellow]Semgrep output was not valid JSON[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Semgrep error: {e}[/yellow]")


def display_report(report: SecurityReport, min_severity: Severity = Severity.INFO) -> None:
    """Display security report in rich terminal format."""
    # Summary panel
    summary_parts = []
    summary_parts.append(f"Total Issues: {report.total_issues}")

    # Issues by severity
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        count = report.issues_by_severity.get(sev, 0)
        if count > 0:
            color = {
                Severity.CRITICAL: "red",
                Severity.HIGH: "red",
                Severity.MEDIUM: "yellow",
                Severity.LOW: "blue",
                Severity.INFO: "dim",
            }[sev]
            summary_parts.append(f"[{color}]{sev.value.title()}: {count}[/{color}]")

    console.print(
        Panel(
            " | ".join(summary_parts),
            title="[bold]Security Scan Summary[/bold]",
            border_style="red" if report.issues_by_severity.get(Severity.CRITICAL, 0) > 0 else "yellow",
        )
    )

    # Filter issues by severity
    filtered_issues = report.filter_by_severity(min_severity)

    if not filtered_issues:
        console.print("\n[green]✅ No security issues found![/green]")
        return

    # Group issues by severity
    issues_by_severity = defaultdict(list)
    for issue in filtered_issues:
        issues_by_severity[issue.severity].append(issue)

    # Display issues by severity
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        issues = issues_by_severity.get(severity, [])
        if not issues:
            continue

        # Severity header
        color = {
            Severity.CRITICAL: "red",
            Severity.HIGH: "red",
            Severity.MEDIUM: "yellow",
            Severity.LOW: "blue",
            Severity.INFO: "dim",
        }[severity]

        console.print(f"\n[bold {color}]{severity.value.upper()} SEVERITY ISSUES ({len(issues)})[/bold {color}]")

        # Create table for this severity
        table = Table(show_header=True, show_lines=True)
        table.add_column("Tool", style="cyan", width=12)
        table.add_column("Issue", style="white")
        table.add_column("Location", style="dim")
        table.add_column("Details", style="dim", width=40)

        for issue in issues:
            location = ""
            if issue.file_path:
                location = issue.file_path
                if issue.line_number:
                    location += f":{issue.line_number}"
            elif issue.package:
                location = f"{issue.package} {issue.installed_version or ''}"

            details = []
            if issue.cve_id:
                details.append(f"CVE: {issue.cve_id}")
            if issue.cwe_id:
                details.append(f"{issue.cwe_id}")
            if issue.confidence:
                details.append(f"Confidence: {issue.confidence}")
            if issue.fixed_version:
                details.append(f"Fix: {issue.fixed_version}")

            table.add_row(issue.tool, issue.title, location, "\n".join(details))

        console.print(table)

        # Show remediation for critical/high issues
        if severity in [Severity.CRITICAL, Severity.HIGH]:
            for issue in issues:
                if issue.remediation:
                    console.print(f"\n💡 [bold]Remediation:[/bold] {issue.remediation}")


def generate_sarif_report(report: SecurityReport) -> dict:
    """Generate SARIF format report for GitHub integration."""
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Zammad MCP Security Scanner",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/basher83/zammad-mcp",
                        "rules": [],
                    }
                },
                "results": [],
            }
        ],
    }

    # Map severity to SARIF level
    level_map = {
        Severity.CRITICAL: "error",
        Severity.HIGH: "error",
        Severity.MEDIUM: "warning",
        Severity.LOW: "note",
        Severity.INFO: "note",
    }

    for i, issue in enumerate(report.issues):
        rule_id = f"{issue.tool}-{i}"

        # Add rule
        rule = {
            "id": rule_id,
            "name": issue.title,
            "shortDescription": {"text": issue.title},
            "fullDescription": {"text": issue.description},
            "help": {"text": issue.remediation or "Review and fix the security issue"},
        }

        if issue.cwe_id:
            rule["properties"] = {"tags": [issue.cwe_id]}

        sarif["runs"][0]["tool"]["driver"]["rules"].append(rule)

        # Add result
        result = {"ruleId": rule_id, "level": level_map[issue.severity], "message": {"text": issue.description}}

        # Add location if available
        if issue.file_path and issue.line_number:
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": issue.file_path},
                        "region": {"startLine": issue.line_number, "startColumn": 1},
                    }
                }
            ]

        sarif["runs"][0]["results"].append(result)

    return sarif


@click.command()
@click.option(
    "--tool",
    multiple=True,
    type=click.Choice(["pip-audit", "bandit", "semgrep"]),
    help="Run specific tool(s) only",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "json", "sarif"]),
    default="terminal",
    help="Output format",
)
@click.option("--output", type=click.Path(path_type=Path), help="Output file (for json/sarif formats)")
@click.option(
    "--severity", type=click.Choice([s.value for s in Severity]), default="info", help="Minimum severity to report"
)
@click.option("--fix", is_flag=True, help="Apply automatic fixes where possible (experimental)")
def main(tool: tuple[str], output_format: str, output: Path | None, severity: str, fix: bool):
    """Run unified security scans for Zammad MCP Server."""

    console.print(Panel.fit("[bold]🔒 Security Scanner[/bold]\nRunning security analysis...", border_style="blue"))

    # Run scans
    scanner = SecurityScanner()
    report = scanner.run_all_scans(list(tool) if tool else None)

    # Apply fixes if requested
    if fix:
        console.print("\n[yellow]Automatic fixes not yet implemented[/yellow]")
        console.print("For now, please apply fixes manually based on the report")

    # Output results
    min_severity = Severity(severity)

    if output_format == "terminal":
        display_report(report, min_severity)

        # Exit code based on severity
        critical_high = report.issues_by_severity.get(Severity.CRITICAL, 0) + report.issues_by_severity.get(
            Severity.HIGH, 0
        )
        if critical_high > 0:
            console.print(f"\n[red]Found {critical_high} critical/high severity issues![/red]")
            sys.exit(1)

    elif output_format == "json":
        # Filter by severity for JSON output
        filtered_report = SecurityReport(
            scan_timestamp=report.scan_timestamp,
            project_path=report.project_path,
            issues=report.filter_by_severity(min_severity),
            tools_run=report.tools_run,
        )

        json_output = filtered_report.model_dump_json(indent=2)

        if output:
            output.write_text(json_output)
            console.print(f"[green]✓[/green] JSON report saved to {output}")
        else:
            print(json_output)

    elif output_format == "sarif":
        sarif_data = generate_sarif_report(report)
        sarif_json = json.dumps(sarif_data, indent=2)

        if output:
            output.write_text(sarif_json)
            console.print(f"[green]✓[/green] SARIF report saved to {output}")
        else:
            print(sarif_json)

    # Summary for non-terminal outputs
    if output_format != "terminal":
        console.print(f"\n[bold]Summary:[/bold] {report.total_issues} issues found")
        for sev, count in report.issues_by_severity.items():
            console.print(f"  {sev.value}: {count}")


if __name__ == "__main__":
    main()
