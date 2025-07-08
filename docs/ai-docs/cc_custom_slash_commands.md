# Create custom slash commands

Claude Code supports custom slash commands that you can create to quickly execute specific prompts or tasks.

For more details, see the [Slash commands](/en/docs/claude-code/slash-commands) reference page.

## Create project-specific commands

Suppose you want to create reusable slash commands for your project that all team members can use.

<Steps>
  <Step title="Create a commands directory in your project">
    ```bash
    mkdir -p .claude/commands
    ```
  </Step>

  <Step title="Create a Markdown file for each command">
    ```bash
    echo "Analyze the performance of this code and suggest three specific optimizations:" > .claude/commands/optimize.md
    ```
  </Step>

  <Step title="Use your custom command in Claude Code">
    ```
    > /optimize
    ```
  </Step>
</Steps>

<Tip>
  Tips:

* Command names are derived from the filename (e.g., `optimize.md` becomes `/optimize`)
* You can organize commands in subdirectories (e.g., `.claude/commands/frontend/component.md` creates `/component` with "(project:frontend)" shown in the description)
* Project commands are available to everyone who clones the repository
* The Markdown file content becomes the prompt sent to Claude when the command is invoked
</Tip>

## Add command arguments with \$ARGUMENTS

Suppose you want to create flexible slash commands that can accept additional input from users.

<Steps>
  <Step title="Create a command file with the $ARGUMENTS placeholder">
    ```bash
    echo "Find and fix issue #$ARGUMENTS. Follow these steps: 1.
    Understand the issue described in the ticket 2. Locate the relevant code in
    our codebase 3. Implement a solution that addresses the root cause 4. Add
    appropriate tests 5. Prepare a concise PR description" >
    .claude/commands/fix-issue.md
    ```
  </Step>

  <Step title="Use the command with an issue number">
    In your Claude session, use the command with arguments.

    ```
    > /fix-issue 123 
    ```

    This will replace \$ARGUMENTS with "123" in the prompt.
  </Step>
</Steps>

<Tip>
  Tips:

* The \$ARGUMENTS placeholder is replaced with any text that follows the command
* You can position \$ARGUMENTS anywhere in your command template
* Other useful applications: generating test cases for specific functions, creating documentation for components, reviewing code in particular files, or translating content to specified languages
</Tip>

## Create personal slash commands

Suppose you want to create personal slash commands that work across all your projects.

<Steps>
  <Step title="Create a commands directory in your home folder">
    ```bash
    mkdir -p ~/.claude/commands
    ```
  </Step>

  <Step title="Create a Markdown file for each command">
    ```bash
    echo "Review this code for security vulnerabilities, focusing on:" >
    ~/.claude/commands/security-review.md
    ```
  </Step>

  <Step title="Use your personal custom command">
    ```
    > /security-review
    ```
  </Step>
</Steps>

<Tip>
  Tips:

* Personal commands show "(user)" in their description when listed with `/help`
* Personal commands are only available to you and not shared with your team
* Personal commands work across all your projects
* You can use these for consistent workflows across different codebases
</Tip>
