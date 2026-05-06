# Codacy MCP

This plugin exposes Codacy through `plugins/zammad-mcp/.mcp.json` using the upstream Codacy MCP server package:

```json
{
  "mcpServers": {
    "codacy": {
      "command": "npx",
      "args": ["-y", "@codacy/codacy-mcp"],
      "env": {
        "CODACY_ACCOUNT_TOKEN": "${CODACY_ACCOUNT_TOKEN}"
      }
    }
  }
}
```

`CODACY_ACCOUNT_TOKEN` must be available in the user's environment before the server can authenticate. Do not commit a real token or place one in this plugin.

The upstream README documents Node.js and `npx` as requirements. For local analysis, Codacy's server can also use the Codacy CLI; if it is not available, the server attempts to install it.
