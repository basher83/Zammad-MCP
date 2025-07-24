#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Pre-tool-use hook for Claude Code to enforce efficient tool usage.

Goals:
1. Prevent dangerous operations (rm -rf, .env access)
2. Encourage modern, faster alternatives (rg over grep, fd over find, eza over ls)
3. Prevent common inefficiencies (useless cat)
4. Balance efficiency with practicality (allow legitimate uses)

The hook aims to increase development speed while maintaining safety.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any


def is_dangerous_rm_command(command: str) -> bool:
    """
    Comprehensive detection of dangerous rm commands.
    Matches various forms of rm -rf and similar destructive patterns.
    """
    # Normalize command by removing extra spaces and converting to lowercase
    normalized = " ".join(command.lower().split())

    # Pattern 1: Standard rm -rf variations
    patterns = [
        r"\brm\s+.*-[a-z]*r[a-z]*f",  # rm -rf, rm -fr, rm -Rf, etc.
        r"\brm\s+.*-[a-z]*f[a-z]*r",  # rm -fr variations
        r"\brm\s+--recursive\s+--force",  # rm --recursive --force
        r"\brm\s+--force\s+--recursive",  # rm --force --recursive
        r"\brm\s+-r\s+.*-f",  # rm -r ... -f
        r"\brm\s+-f\s+.*-r",  # rm -f ... -r
    ]

    # Check for dangerous patterns
    for pattern in patterns:
        if re.search(pattern, normalized):
            return True

    # Pattern 2: Check for rm with recursive flag targeting dangerous paths
    dangerous_paths = [
        r"/",  # Root directory
        r"/\*",  # Root with wildcard
        r"~",  # Home directory
        r"~/",  # Home directory path
        r"\$HOME",  # Home environment variable
        r"\.\.",  # Parent directory references
        r"\*",  # Wildcards in general rm -rf context
        r"\.",  # Current directory
        r"\.\s*$",  # Current directory at end of command
    ]

    if re.search(r"\brm\s+.*-[a-z]*r", normalized):  # If rm has recursive flag
        for path in dangerous_paths:
            if re.search(path, normalized):
                return True

    return False


def is_env_file_access(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """
    Check if any tool is trying to access .env files containing sensitive data.
    """
    if tool_name in ["Read", "Edit", "MultiEdit", "Write", "Bash"]:
        # Check file paths for file-based tools
        if tool_name in ["Read", "Edit", "MultiEdit", "Write"]:
            file_path = tool_input.get("file_path", "")
            if ".env" in file_path and not file_path.endswith(".env.sample"):
                return True

        # Check bash commands for .env file access
        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            # Pattern to detect .env file access (but allow .env.sample)
            env_patterns = [
                r"\b\.env\b(?!\.sample)",  # .env but not .env.sample
                r"cat\s+.*\.env\b(?!\.sample)",  # cat .env
                r"echo\s+.*>\s*\.env\b(?!\.sample)",  # echo > .env
                r"touch\s+.*\.env\b(?!\.sample)",  # touch .env
                r"cp\s+.*\.env\b(?!\.sample)",  # cp .env
                r"mv\s+.*\.env\b(?!\.sample)",  # mv .env
            ]

            for pattern in env_patterns:
                if re.search(pattern, command):
                    return True

    return False


def should_use_ripgrep(command: str) -> bool:
    """
    Check if the command uses grep when ripgrep (rg) would be more efficient.
    Returns True if grep is used for searching code/files.
    """
    # Normalize command
    normalized = command.strip()

    # Check if command starts with or contains grep as a command
    # But allow grep in file paths or as arguments
    grep_patterns = [
        r"^grep\s",  # Command starts with grep
        r";\s*grep\s",  # grep after semicolon
        r"&&\s*grep\s",  # grep after &&
        r"\|\s*grep\s",  # grep after pipe
        r"^\s*grep\s",  # grep with leading whitespace
    ]

    for pattern in grep_patterns:
        if re.search(pattern, normalized):
            # Check if it's not just grepping from a small stream (like ps output)
            # These are cases where grep might be acceptable
            acceptable_grep_uses = [
                r"ps\s+.*\|\s*grep",  # ps aux | grep process
                r"history\s*\|\s*grep",  # history | grep command
                r"echo\s+.*\|\s*grep",  # echo "text" | grep pattern
                r"--version.*\|\s*grep",  # command --version | grep
                r"dmesg.*\|\s*grep",  # dmesg | grep (system logs)
                r"systemctl.*\|\s*grep",  # systemctl | grep (service status)
                r"grep\s+-[a-zA-Z]*[qcl]",  # grep -q (quiet), -c (count), -l (files with matches)
                r"grep\s+--quiet",  # grep --quiet (exit code checking)
                r"test.*grep",  # grep in test conditions
                r"if.*grep",  # grep in if statements
                r".*\|\s*xargs\s+grep",  # piped to xargs grep
            ]

            for acceptable in acceptable_grep_uses:
                if re.search(acceptable, normalized):
                    return False

            return True

    return False


def should_use_fd(command: str) -> bool:
    """
    Check if the command uses find when fd would be more efficient.
    Returns True if find is used for searching files/directories.
    """
    # Normalize command
    normalized = command.strip()

    # Check if command uses find as a command
    find_patterns = [
        r"^find\s",  # Command starts with find
        r";\s*find\s",  # find after semicolon
        r"&&\s*find\s",  # find after &&
        r"\|\s*find\s",  # find after pipe
        r"^\s*find\s",  # find with leading whitespace
    ]

    for pattern in find_patterns:
        if re.search(pattern, normalized):
            # Check if it's the 'find' command and not just a word in a string
            # Exclude cases where 'find' might be part of another command or path
            if "findstr" in normalized:  # Windows findstr command
                return False

            # Common find usage patterns that should use fd instead
            find_usage_patterns = [
                r"find\s+\.",  # find . (current directory)
                r"find\s+/",  # find /path
                r"find\s+~",  # find ~ (home directory)
                r"find\s+\$",  # find with variables
                r"find\s+['\"]",  # find with quoted paths
                r"find\s+.*-name",  # find with -name
                r"find\s+.*-type",  # find with -type
                r"find\s+.*-iname",  # find with -iname
                r"find\s+.*-path",  # find with -path
                r"find\s+.*-regex",  # find with -regex
            ]

            for usage in find_usage_patterns:
                if re.search(usage, normalized):
                    return True

            # If it's just 'find' followed by a path or option, it's likely file search
            if re.match(r"^find\s+[^|;&]+$", normalized.strip()):
                return True

    return False


def has_inefficient_cat(command: str) -> bool:
    """
    Check if the command uses cat inefficiently (cat file | grep/awk/sed).
    Returns True if cat is used unnecessarily.
    """
    # Normalize command
    normalized = command.strip()

    # Pattern for inefficient cat usage: cat file | tool
    inefficient_patterns = [
        r"cat\s+[^|<>]+\|\s*grep",  # cat file | grep
        r"cat\s+[^|<>]+\|\s*awk",  # cat file | awk
        r"cat\s+[^|<>]+\|\s*sed",  # cat file | sed
        r"cat\s+[^|<>]+\|\s*head",  # cat file | head
        r"cat\s+[^|<>]+\|\s*tail",  # cat file | tail
        r"cat\s+[^|<>]+\|\s*sort",  # cat file | sort
        r"cat\s+[^|<>]+\|\s*uniq",  # cat file | uniq
        r"cat\s+[^|<>]+\|\s*wc",  # cat file | wc
        r"cat\s+[^|<>]+\|\s*cut",  # cat file | cut
    ]

    for pattern in inefficient_patterns:
        if re.search(pattern, normalized):
            # Check for exceptions where cat might be needed
            acceptable_cat_uses = [
                r"cat\s+-",  # cat - (reading from stdin)
                r"cat\s+.*<<",  # cat with heredoc
                r"cat\s+.*\*",  # cat with wildcards (concatenating multiple files)
                r"cat\s+[^|]+\s+[^|]+\|",  # cat file1 file2 | (concatenating)
                r"zcat",  # zcat (compressed files)
                r"cat.*\.gz\s*\|",  # cat of gzipped files
            ]

            for acceptable in acceptable_cat_uses:
                if re.search(acceptable, normalized):
                    return False

            return True

    return False


def should_use_eza(command: str) -> bool:
    """
    Check if the command uses ls when eza would be more feature-rich.
    Returns True if ls is used for listing files/directories.
    """
    # Normalize command
    normalized = command.strip()

    # Check if command uses ls as a command
    ls_patterns = [
        r"^ls\b",  # Command starts with ls
        r";\s*ls\b",  # ls after semicolon
        r"&&\s*ls\b",  # ls after &&
        r"\|\s*ls\b",  # ls after pipe (though this is less common)
        r"^\s*ls\b",  # ls with leading whitespace
    ]

    for pattern in ls_patterns:
        if re.search(pattern, normalized):
            # Allow some specific ls usages that might be in scripts or specific contexts
            # For example, ls in command substitution or when output is being processed
            acceptable_ls_uses = [
                r"ls.*\|\s*wc",  # ls | wc -l (counting files)
                r"ls.*\|\s*grep",  # ls | grep pattern (filtering)
                r"ls.*\>\s*/dev/null",  # ls > /dev/null (checking existence)
                r"\$\(.*ls.*\)",  # $(ls ...) command substitution
                r"`.*ls.*`",  # `ls ...` command substitution
                r"ls\s+-1",  # ls -1 (one per line, often needed for scripts)
                r"ls\s+.*-1",  # ls with other flags and -1
                r"ls\s+-d\s+\*/",  # ls -d */ (list only directories)
                r"ls\s+.*\.log",  # ls *.log (specific file patterns for scripts)
                r"for\s+.*in\s+.*ls",  # for loops using ls output
            ]

            for acceptable in acceptable_ls_uses:
                if re.search(acceptable, normalized):
                    return False

            return True

    return False


def print_blocked_message(reason: str, examples: list[str] | None = None) -> None:
    """Print a standardized blocked message with optional examples."""
    print(f"BLOCKED: {reason}", file=sys.stderr)
    if examples:
        for example in examples:
            print(example, file=sys.stderr)
    print("See docs/claude-pre-tool-use-hook.md for more details and exceptions", file=sys.stderr)


def validate_env_file_access(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Validate and block .env file access if needed. Returns True if blocked."""
    if is_env_file_access(tool_name, tool_input):
        print_blocked_message(
            "Access to .env files containing sensitive data is prohibited",
            ["Use .env.sample for template files instead"],
        )
        return True
    return False


def validate_bash_command(command: str) -> bool:
    """Validate bash command for dangerous or inefficient patterns. Returns True if blocked."""
    # Check for dangerous rm -rf commands
    if is_dangerous_rm_command(command):
        print_blocked_message("Dangerous rm command detected and prevented")
        return True

    # Check for inefficient grep usage
    if should_use_ripgrep(command):
        print_blocked_message(
            "Use 'rg' (ripgrep) instead of 'grep' for better performance",
            [
                "Ripgrep is faster and respects .gitignore by default",
                "Example: rg 'pattern' instead of grep -r 'pattern'",
            ],
        )
        return True

    # Check for inefficient find usage
    if should_use_fd(command):
        print_blocked_message(
            "Use 'fd' instead of 'find' for better performance and usability",
            [
                "fd is faster, has intuitive syntax, and respects .gitignore by default",
                "Examples:",
                "  fd 'pattern' instead of find . -name '*pattern*'",
                "  fd -e py instead of find . -name '*.py'",
                "  fd -t f instead of find . -type f",
            ],
        )
        return True

    # Check for ls usage when eza would be better
    if should_use_eza(command):
        print_blocked_message(
            "Use 'eza' instead of 'ls' for better output and features",
            [
                "eza provides colors, icons, git status, tree view, and more",
                "Examples:",
                "  eza instead of ls",
                "  eza -la instead of ls -la",
                "  eza --tree instead of ls -R",
                "  eza --git -l for git status integration",
            ],
        )
        return True

    # Check for inefficient cat usage
    if has_inefficient_cat(command):
        print_blocked_message(
            "Inefficient use of 'cat' detected",
            [
                "Most commands can read files directly without cat",
                "Examples:",
                "  grep 'pattern' file instead of cat file | grep 'pattern'",
                "  awk '{print $1}' file instead of cat file | awk '{print $1}'",
                "  sed 's/old/new/' file instead of cat file | sed 's/old/new/'",
                "  head -n 10 file instead of cat file | head -n 10",
            ],
        )
        return True

    return False


def log_tool_usage(input_data: dict[str, Any]) -> None:
    """Log tool usage to JSON file."""
    # Ensure log directory exists
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "pre_tool_use.json"

    # Read existing log data
    if log_path.exists():
        with open(log_path) as f:
            try:
                log_data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                log_data = []
    else:
        log_data = []

    # Append new data
    log_data.append(input_data)

    # Write back to file with formatting
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)


def main() -> None:
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Check for .env file access
        if validate_env_file_access(tool_name, tool_input):
            sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude

        # Check for dangerous or inefficient bash commands
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if validate_bash_command(command):
                sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude

        # Log the tool usage
        log_tool_usage(input_data)

        sys.exit(0)

    except json.JSONDecodeError:
        # Gracefully handle JSON decode errors
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
