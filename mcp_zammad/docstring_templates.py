"""Helper functions for generating MCP tool docstrings per best practices."""


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

    # Args section
    lines.append("Args:")
    for param, desc in args_doc.items():
        lines.append(f"    {param} (str): {desc}")
    lines.append("")

    # Returns section with schema
    lines.append("Returns:")
    lines.append("    Formatted string with the following schema:")
    lines.append("")
    lines.append("    {")
    for field, type_desc in return_schema.items():
        lines.append(f'        "{field}": {type_desc},')
    lines.append("    }")
    lines.append("")

    # Examples section
    if use_when or dont_use_when or examples:
        lines.append("Examples:")
        if use_when:
            for example in use_when:
                lines.append(f"    - Use when: {example}")
        if dont_use_when:
            for example in dont_use_when:
                lines.append(f"    - Don't use when: {example}")
        for example in examples:
            lines.append(f"    - {example}")
        lines.append("")

    # Error handling section
    if errors:
        lines.append("Errors:")
        for error in errors:
            lines.append(f"    - {error}")

    return "\n".join(lines)
