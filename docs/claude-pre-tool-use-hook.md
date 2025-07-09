# Claude Code Pre-Tool-Use Hook Documentation

## Overview

The `.claude/hooks/pre_tool_use.py` script is a security and efficiency enforcement hook for Claude Code. It runs before every tool invocation to ensure safe and efficient command execution.

## Goals

1. **Prevent dangerous operations** - Block destructive commands that could harm your system
1. **Encourage modern, faster alternatives** - Suggest efficient tools over legacy ones
1. **Prevent common inefficiencies** - Block wasteful command patterns
1. **Balance efficiency with practicality** - Allow legitimate use cases

## Hook Behavior

The hook inspects commands before execution and can:

- **Block** dangerous or inefficient commands (exit code 2)
- **Allow** safe and efficient commands (exit code 0)
- **Log** all tool usage for debugging

## Command Categories

### 1. Dangerous Commands (Always Blocked)

#### Destructive `rm` Commands

**Blocked Examples:**

```bash
rm -rf /              # Deletes root filesystem
rm -rf ~              # Deletes home directory
rm -rf *              # Deletes everything in current directory
rm -rf ../..          # Deletes parent directories
rm --recursive --force /tmp
```

**Why:** These commands can cause irreversible data loss. The hook detects various forms of recursive + force deletion targeting dangerous paths.

**Allowed Alternative:**

```bash
rm -rf specific-folder/    # Targeting specific directories is allowed
rm file.txt               # Non-recursive deletion is allowed
```

#### Sensitive File Access

**Blocked Examples:**

```bash
cat .env              # Reading environment variables
echo "secret" > .env  # Writing to .env
cp .env backup/       # Copying .env files
```

**Why:** `.env` files contain sensitive credentials and should not be accessed directly.

**Allowed Alternative:**

```bash
cat .env.sample       # Template files are allowed
cat .env.example      # Example files are allowed
```

### 2. Inefficient File Search Commands

#### `grep` → `rg` (ripgrep)

**Blocked Examples:**

```bash
grep -r "pattern" .           # Recursive grep in current directory
grep "TODO" src/              # Searching in directory
find . -name "*.py" | xargs grep "import"
```

**Why:** `grep` is slower and doesn't respect `.gitignore` by default. Ripgrep (`rg`) is 10-100x faster for code searching.

**Allowed Examples:**

```bash
ps aux | grep python          # Process filtering - grep is appropriate
history | grep git            # Command history search - small dataset
echo "test" | grep "pattern"  # Piped from small output
dmesg | grep error           # System log filtering
grep -q "pattern" file       # Quiet mode for exit code checking
if grep -l "TODO" file; then # Conditional checking
```

**Suggested Alternative:**

```bash
rg "pattern"                  # Searches recursively, respects .gitignore
rg -t py "import"            # Search only Python files
rg -l "TODO"                 # List files containing pattern
```

#### `find` → `fd`

**Blocked Examples:**

```bash
find . -name "*.js"          # Find JavaScript files
find /home -type f           # Find all files
find . -name "*test*"        # Find files with 'test' in name
```

**Why:** `find` has complex syntax and is slower than `fd`. The `fd` command is more intuitive and respects `.gitignore`.

**Allowed Examples:**

```bash
# None - find commands for file searching are generally blocked
# Exception: Windows findstr is allowed as it's a different command
```

**Suggested Alternative:**

```bash
fd "\.js$"                   # Find JavaScript files
fd -t f                      # Find all files
fd test                      # Find files with 'test' in name
fd -e py                     # Find Python files by extension
```

#### `ls` → `eza`

**Blocked Examples:**

```bash
ls                           # Basic listing
ls -la                       # Long format with hidden files
ls -R                        # Recursive listing
```

**Why:** `eza` provides better output with colors, icons, git integration, and more features.

**Allowed Examples:**

```bash
ls -1                        # One file per line (script-friendly)
ls -1 *.txt                  # List specific files one per line
ls -d */                     # List only directories
ls *.log                     # List specific file patterns
for f in $(ls *.sh); do      # Using ls in for loops
ls | wc -l                   # Counting files
ls | grep pattern            # Filtering output
ls > /dev/null              # Existence checking
$(ls ...)                    # Command substitution
```

**Suggested Alternative:**

```bash
eza                          # Better formatted listing
eza -la                      # Long format with icons
eza --tree                   # Tree view instead of ls -R
eza --git -l                 # Show git status in listing
```

### 3. Inefficient Command Patterns

#### Useless `cat`

**Blocked Examples:**

```bash
cat file.txt | grep "pattern"     # Unnecessary cat
cat log.txt | head -n 10          # Cat piped to head
cat data.csv | awk '{print $1}'   # Cat piped to awk
cat config.json | sed 's/old/new/' # Cat piped to sed
```

**Why:** Most commands can read files directly. Using `cat` adds an unnecessary process and pipe.

**Allowed Examples:**

```bash
cat file1.txt file2.txt | grep    # Concatenating multiple files
cat *.log | sort                   # Concatenating with wildcards
cat - | process                    # Reading from stdin
cat << EOF | command               # Here documents
zcat file.gz | grep               # Compressed files
```

**Suggested Alternative:**

```bash
grep "pattern" file.txt            # Direct file reading
head -n 10 log.txt                # Head reads files directly
awk '{print $1}' data.csv         # Awk reads files directly
sed 's/old/new/' config.json      # Sed reads files directly
```

## Configuration

The hook is configured in `.claude/settings.local.json`:

**Note**: Ensure this file exists and is readable by the Claude Code environment.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "uv run .claude/hooks/pre_tool_use.py"
          }
        ]
      }
    ]
  }
}
```

## Logging

All tool invocations are logged to `logs/pre_tool_use.json` for debugging and auditing purposes.

## Design Philosophy

The hook follows these principles:

1. **Safety First**: Dangerous operations are always blocked
1. **Performance Matters**: Encourage tools that are 10-100x faster
1. **Practical Exceptions**: Common scripting patterns are allowed
1. **Educational**: Error messages explain why and suggest alternatives
1. **Non-Intrusive**: Silent pass-through for allowed commands

## Customization

To modify the hook behavior:

1. Edit `.claude/hooks/pre_tool_use.py`
1. Add patterns to `acceptable_*_uses` lists for exceptions
1. Add new check functions following the existing pattern
1. Test thoroughly to ensure legitimate uses aren't blocked

## Troubleshooting

If a legitimate command is blocked:

1. Check if it matches an acceptable use pattern
1. Consider if there's a more efficient alternative
1. Add an exception pattern if truly necessary
1. Report issues for common false positives

Remember: The goal is to make development faster and safer, not to create obstacles.
