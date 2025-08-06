# GitHub MCP Server for Claude Code

## Prerequisites

- Docker installed
- GitHub Personal Access Token with appropriate repository permissions
- Claude Code or compatible MCP client

## Docker CLI Options

### Dynamic Toolsets (Experimental)

```bash
docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=<your-token> \
  -e GITHUB_DYNAMIC_TOOLSETS=1 \
  ghcr.io/github/github-mcp-server
```

### Default (All Tools Enabled)

```bash
docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=<your-token> \
  ghcr.io/github/github-mcp-server
```

### Specific Toolsets

```bash
docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=<your-token> \
  -e GITHUB_TOOLSETS="repos,issues,pull_requests,actions,code_security" \
  ghcr.io/github/github-mcp-server
```

- `repos` - Repository management
- `issues` - Issue management  
- `pull_requests` - Pull request operations
- `actions` - GitHub Actions integration
- `code_security` - Security scanning access
- `experiments` - Beta features
- `all` - Enable all toolsets

### Available Toolsets

## Claude Code Configuration

### Dynamic Toolsets (.mcp.json)

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "-e", "GITHUB_DYNAMIC_TOOLSETS=1",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {}
    }
  }
}
```

### Default Configuration (.mcp.json)

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "docker", 
      "args": [
        "run", "-i", "--rm",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {}
    }
  }
}
```

### Specific Toolsets (.mcp.json)

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio", 
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "-e", "GITHUB_TOOLSETS=repos,issues,pull_requests,actions,code_security",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {}
    }
  }
}
```

## Environment Setup

Set your GitHub token as an environment variable:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=<your-token>
```

Reference: [GitHub MCP Server](https://github.com/github/github-mcp-server)
