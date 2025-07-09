# Command Documentation

This directory contains documentation and design documents for Claude commands. These files are **NOT** executed by Claude when running commands - they serve as reference material only.

## Files

### git_commitv2_parallel_design.md

- **Purpose**: Technical design document for the parallel agent git commit command
- **Usage**: Reference for understanding the implementation architecture
- **Status**: Documentation only - not used during command execution

### git_commitv2_precommit_examples.md

- **Purpose**: Examples and templates for handling pre-commit hook failures
- **Usage**: Reference for common failure patterns and fix strategies
- **Status**: Documentation only - fix agent templates could be manually copied if needed

## Important Note

The actual executable commands are in the parent directory (`.claude/commands/`). These documentation files are kept separate to avoid confusion about what gets executed versus what serves as reference material.
