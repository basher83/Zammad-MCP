"""Helper functions for generating MCP tool docstrings per best practices."""


def _build_args_section(args_doc: dict[str, str]) -> list[str]:
    """Build the Args section of a docstring."""
    lines = ["Args:"]
    for param, desc in args_doc.items():
        lines.append(f"    {param}: {desc}")
    lines.append("")
    return lines


def _build_returns_section(return_schema: dict[str, str]) -> list[str]:
    """Build the Returns section with schema."""
    lines = ["Returns:", "    Formatted string with the following schema:", "", "    {"]
    for field, type_desc in return_schema.items():
        lines.append(f'        "{field}": {type_desc},')
    lines.extend(["    }", ""])
    return lines


def _build_examples_section(
    examples: list[str], use_when: list[str] | None, dont_use_when: list[str] | None
) -> list[str]:
    """Build the Examples section."""
    # Collect all example lines
    all_examples: list[str] = []
    all_examples.extend(f"    - Use when: {ex}" for ex in (use_when or []))
    all_examples.extend(f"    - Don't use when: {ex}" for ex in (dont_use_when or []))
    all_examples.extend(f"    - {ex}" for ex in examples)

    # Return empty if no examples
    if not all_examples:
        return []

    return ["Examples:", *all_examples, ""]


def _build_errors_section(errors: list[str]) -> list[str]:
    """Build the Error Handling section."""
    if not errors:
        return []
    lines = ["Error Handling:"]
    lines.extend(f"    - {error}" for error in errors)
    return lines


def format_tool_docstring(
    summary: str,
    args_doc: dict[str, str],
    return_schema: dict[str, str],
    examples: list[str],
    errors: list[str],
    use_when: list[str] | None = None,
    dont_use_when: list[str] | None = None,
) -> str:
    """Format complete MCP tool docstring with all required sections.

    Args:
        summary: One-line tool description
        args_doc: Parameter name -> description mapping
        return_schema: Field name -> type description for return value
        examples: List of usage examples
        errors: List of error scenarios and messages
        use_when: Optional list of when to use this tool
        dont_use_when: Optional list of when NOT to use this tool

    Returns:
        Formatted docstring following MCP Python best practices
    """
    lines = [summary, ""]
    lines.extend(_build_args_section(args_doc))
    lines.extend(_build_returns_section(return_schema))
    lines.extend(_build_examples_section(examples, use_when, dont_use_when))
    lines.extend(_build_errors_section(errors))
    return "\n".join(lines)
