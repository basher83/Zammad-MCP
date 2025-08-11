# Security Policy

## Supported Versions

We actively support the following versions of Zammad MCP Server with security updates:

| Version | Supported          | Security Updates | End of Life |
| ------- | ------------------ | ---------------- | ----------- |
| 0.1.x   | :white_check_mark: | Active           | TBD         |
| 0.0.x   | :x:                | None             | 2024-12-31  |
| main    | :white_check_mark: | Development      | N/A         |

**Note**: We recommend always using the latest stable release for production environments.

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 1. Private Disclosure

**Do NOT create a public GitHub issue for security vulnerabilities.**

Instead, please use one of these methods:

- **GitHub Security Advisories** (Preferred): [Report a vulnerability](https://github.com/basher83/Zammad-MCP/security/advisories/new) via GitHub's private vulnerability reporting
- **Email**: For urgent security matters, contact repository maintainers directly
- **Encrypted Email**: For sensitive reports, use GPG encryption (key available on request)

### 2. What to Include

When reporting a vulnerability, please provide:

- **Vulnerability Type**: (e.g., SSRF, XSS, SQL Injection, Authentication Bypass)
- **Affected Components**: Full paths of source files and functions
- **Description**: Clear explanation of the vulnerability
- **Steps to Reproduce**:
  1. Detailed step-by-step instructions
  2. Include code samples or scripts if applicable
  3. Expected vs actual behavior
- **Impact Assessment**:
  - Severity (Critical/High/Medium/Low)
  - Potential attack scenarios
  - Affected users or data
- **Proof of Concept**: Include PoC code if available
- **Suggested Fix**: Your recommended mitigation (optional)
- **Contact Information**: For coordinated disclosure

### 3. Response Timeline

We commit to the following response times:

- **Initial Response**: Within 48 hours of report (acknowledgment)
- **Initial Assessment**: Within 7 days (severity determination)
- **Fix Development Timeline**:
  - Critical (CVSS 9.0-10.0): Within 14 days
  - High (CVSS 7.0-8.9): Within 30 days
  - Medium (CVSS 4.0-6.9): Within 60 days
  - Low (CVSS 0.1-3.9): Within 90 days
- **Patch Release**: Within 24 hours of fix completion (best-effort)
- **Disclosure**:
  - Coordinated disclosure with reporter
  - Default: 90 days from initial report
  - May be expedited for actively exploited vulnerabilities

## Security Best Practices

### For Users

#### API Token Security

- **Use API tokens instead of username/password** when possible
- **Store tokens securely** using environment variables or secure credential storage
- **Rotate tokens regularly** (recommended: every 90 days)
- **Limit token scope** to minimum required permissions
- **Never commit tokens** to version control

#### Environment Configuration

```bash
# ✅ Good: Use environment variables
export ZAMMAD_HTTP_TOKEN="your-token-here"

# ❌ Bad: Hard-coded in configuration files
ZAMMAD_HTTP_TOKEN=abc123token
```

#### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "zammad": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/basher83/zammad-mcp.git", "mcp-zammad"],
      "env": {
        "ZAMMAD_URL": "https://your-instance.zammad.com/api/v1",
        "ZAMMAD_HTTP_TOKEN": "your-api-token"
      }
    }
  }
}
```

**Security Notes:**

- Ensure Claude Desktop configuration files have restricted permissions
- Use different tokens for different environments (dev/staging/prod)
- Monitor token usage in Zammad's admin interface

#### Network Security

- **Use HTTPS only** - ensure your Zammad URL uses `https://`
- **Verify SSL certificates** - don't disable SSL verification
- **Network isolation** - run in isolated environments when possible
- **Firewall rules** - restrict outbound connections to necessary endpoints only

### For Developers

#### Secure Development

- **Input validation** - validate all user inputs and API responses
- **Error handling** - don't expose sensitive information in error messages
- **Logging** - sanitize logs to prevent credential leakage
- **Dependencies** - keep dependencies updated and scan for vulnerabilities

#### Code Security Guidelines

```python
# ✅ Good: Sanitized logging
logger.info(f"Request to {url.split('?')[0]}")  # Remove query parameters

# ❌ Bad: Exposing credentials
logger.debug(f"Full request: {url}")  # May contain tokens in URL
```

#### Testing Security

- Test with minimal permissions
- Use separate test instances
- Never use production credentials in tests
- Implement security tests in CI/CD pipeline

## Data Handling

### Customer Data Protection

- **Data minimization** - only access necessary ticket/user data
- **Temporary storage** - avoid storing customer data locally
- **Memory management** - clear sensitive data from memory when possible
- **Compliance** - follow GDPR, CCPA, and other applicable regulations

### API Response Handling

```python
# ✅ Good: Clear sensitive data
response_data = api_call()
process_data(response_data)
del response_data  # Clear from memory

# ✅ Good: Limit data exposure
filtered_data = {k: v for k, v in data.items()
                if k not in ['password', 'token', 'secret']}
```

## Zammad Instance Security

### Instance Configuration

- Keep Zammad updated to the latest version
- Use strong authentication methods
- Enable audit logging
- Configure proper user permissions
- Regular security audits

### API Token Management

- Create dedicated tokens for MCP integration
- Use descriptive token names (e.g., "MCP-Server-Production")
- Regularly review and rotate tokens
- Monitor token usage in Zammad logs
- Revoke unused or compromised tokens immediately

### Permission Guidelines

Recommended minimum permissions for MCP tokens:

- `ticket.agent` - For ticket operations
- `user.agent` - For user lookups (if needed)
- `organization.agent` - For organization data (if needed)

Avoid granting admin permissions unless absolutely necessary.

## Incident Response

### If You Suspect a Security Breach

1. **Immediate Actions**
   - Revoke potentially compromised API tokens
   - Change any exposed credentials
   - Check Zammad audit logs for suspicious activity

1. **Assessment**
   - Determine scope of potential exposure
   - Identify affected systems and data
   - Document timeline of events

1. **Notification**
   - Report to this project's maintainers
   - Notify your organization's security team
   - Consider customer notification if data was exposed

1. **Recovery**
   - Implement security fixes
   - Update credentials and tokens
   - Monitor for continued suspicious activity

## Vulnerability Management

### Security Scanning Tools

This project employs multiple layers of security scanning:

#### Static Analysis

- ✅ **Bandit**: Identifies common security issues in Python code (active in CI)
- ✅ **CodeQL**: GitHub's automatic security analysis (enabled by default)
- ✅ **Codacy**: Comprehensive static analysis and code quality (active in CI)
- ⏳ **Semgrep**: Pattern-based vulnerability detection (integration pending)

#### Dependency Scanning

- ✅ **Dependabot**: Automated dependency updates (active)
- ✅ **pip-audit**: Python package vulnerability detection (active in CI)
- ✅ **Safety**: Known vulnerability database checks (active in CI)
- ⏳ **Renovate**: Automated dependency management (integration pending)

#### Container Security

- ⏳ **Trivy**: Container image vulnerability scanning (integration pending)
- ⏳ **Docker Scout**: Supply chain security analysis (integration pending)
- ⏳ **Hadolint**: Dockerfile best practices (integration pending)

### Running Security Scans Locally

```bash
# Run all security checks
./scripts/quality-check.sh

# Individual security scans
uv run pip-audit               # Check for vulnerable packages
uv run bandit -r mcp_zammad    # Static security analysis
# uv run semgrep --config=auto .  # Pattern-based scanning (pending setup)
uv run safety check --output json  # Vulnerability database check

# Docker image scanning
docker scout cves ghcr.io/basher83/zammad-mcp:latest
```

## GitHub Actions Security

### Required Secrets

For the security scanning workflow to function properly, configure the following secrets in your repository:

- **`SAFETY_API_KEY`**: Required for the Safety vulnerability scanner
  - Sign up at <https://safetycli.com/resources/plans>
  - Add the key to Settings → Secrets → Actions
- **`CODACY_PROJECT_TOKEN`**: For Codacy security analysis (optional)
  - Available from your Codacy project settings
- **`GITHUB_TOKEN`**: Automatically provided by GitHub Actions

### Security Workflow

The repository includes automated security scanning that runs on:

- Every push to main branch
- All pull requests
- Weekly scheduled scans (Mondays at 09:00 UTC)
- Manual workflow dispatch

### Pre-commit Hooks

Install pre-commit hooks for local security checks:

```bash
# Install pre-commit
uv pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

The repository includes a comprehensive `.pre-commit-config.yaml` with security-focused hooks:

```yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    hooks:
      - id: bandit
        args: ["-f", "json"]
        exclude: ^tests/

  - repo: https://github.com/semgrep/semgrep
    hooks:
      - id: semgrep
        args: ["--config=auto", "--error"]

  - repo: local
    hooks:
      - id: pip-audit
        name: pip-audit
        entry: uv
        args: ["run", "pip-audit", "--format=json"]
```

This configuration ensures security checks run automatically on every commit.

## CVE Process

### CVE Assignment

For qualifying vulnerabilities, we will:

1. Request CVE assignment through GitHub Security Advisories
2. Coordinate with reporter on CVE details
3. Include CVE in release notes and advisories
4. Update this document with CVE references

### Severity Scoring

We use CVSS v3.1 for vulnerability scoring:

- **Critical** (9.0-10.0): Remote code execution, authentication bypass
- **High** (7.0-8.9): Privilege escalation, data exposure
- **Medium** (4.0-6.9): Cross-site scripting, denial of service
- **Low** (0.1-3.9): Information disclosure, minor issues

## Security Contact

For security-related questions or concerns:

- **Security Issues**: [Report via GitHub Security Advisories](https://github.com/basher83/Zammad-MCP/security/advisories/new)
- **General Security Questions**: [Create a GitHub Discussion](https://github.com/basher83/Zammad-MCP/discussions)
- **Urgent Security Matters**: Contact repository maintainers directly

## Acknowledgments

We appreciate security researchers and users who help keep this project secure. Responsible disclosure helps protect all users of the Zammad MCP Server.

### Hall of Fame

Security researchers who have helped improve our security will be acknowledged here (with their permission).

### Bounty Program

While we don't currently offer monetary rewards, we provide:

- Public acknowledgment (with permission)
- CVE credit for qualifying vulnerabilities
- Contribution recognition in release notes

## Updates to This Policy

This security policy may be updated periodically. Major changes will be announced through:

- GitHub Releases
- Repository announcements
- Security advisories (if applicable)

---

**Last Updated**: 2025-08-11
**Version**: 1.1.0

**Changelog**:

- v1.1.0 (2025-08-11): Enhanced vulnerability reporting, added CVE process, expanded security tools documentation
- v1.0.0 (2025-07-08): Initial security policy
