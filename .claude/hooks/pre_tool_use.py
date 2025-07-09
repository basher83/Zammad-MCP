#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///

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


def main() -> None:
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Check for .env file access (blocks access to sensitive environment files)
        if is_env_file_access(tool_name, tool_input):
            print("BLOCKED: Access to .env files containing sensitive data is prohibited", file=sys.stderr)
            print("Use .env.sample for template files instead", file=sys.stderr)
            sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude

        # Check for dangerous rm -rf commands and inefficient grep usage
        if tool_name == "Bash":
            command = tool_input.get("command", "")

            # Block rm -rf commands with comprehensive pattern matching
            if is_dangerous_rm_command(command):
                print("BLOCKED: Dangerous rm command detected and prevented", file=sys.stderr)
                sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude
                
            # Check for inefficient grep usage
            if should_use_ripgrep(command):
                print("BLOCKED: Use 'rg' (ripgrep) instead of 'grep' for better performance", file=sys.stderr)
                print("Ripgrep is faster and respects .gitignore by default", file=sys.stderr)
                print("Example: rg 'pattern' instead of grep -r 'pattern'", file=sys.stderr)
                sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude
                
            # Check for inefficient find usage
            if should_use_fd(command):
                print("BLOCKED: Use 'fd' instead of 'find' for better performance and usability", file=sys.stderr)
                print("fd is faster, has intuitive syntax, and respects .gitignore by default", file=sys.stderr)
                print("Examples:", file=sys.stderr)
                print("  fd 'pattern' instead of find . -name '*pattern*'", file=sys.stderr)
                print("  fd -e py instead of find . -name '*.py'", file=sys.stderr)
                print("  fd -t f instead of find . -type f", file=sys.stderr)
                sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude

        # Ensure log directory exists
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "pre_tool_use.json"

        # Read existing log data or initialize empty list
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

        sys.exit(0)

    except json.JSONDecodeError:
        # Gracefully handle JSON decode errors
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
