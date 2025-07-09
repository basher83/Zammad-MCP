# Security Policy

## Supported Versions

We actively support the following versions of Zammad MCP Server with security updates:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| 0.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 1. Private Disclosure

**Do NOT create a public GitHub issue for security vulnerabilities.**

Instead, please use one of these methods:

- **GitHub Security Advisories** (Preferred): Use the "Report a vulnerability" button in the Security tab of this repository
- **Email**: Send details to the repository maintainer at [contact email - update this]
- **Encrypted Email**: For sensitive reports, use GPG encryption (key available on request)

### 2. What to Include

When reporting a vulnerability, please provide:

- A clear description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Any suggested fixes or mitigations
- Your contact information for follow-up

### 3. Response Timeline

We commit to the following response times:

- **Initial Response**: Within 48 hours of report
- **Assessment**: Within 7 days
- **Fix Development**: Within 30 days for critical issues, 90 days for others
- **Disclosure**: Coordinated disclosure after fix is available

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

## Security Contact

For security-related questions or concerns:

- **Security Issues**: Use GitHub Security Advisories
- **General Security Questions**: Create a GitHub Discussion
- **Urgent Security Matters**: Contact repository maintainers directly

## Acknowledgments

We appreciate security researchers and users who help keep this project secure. Responsible disclosure helps protect all users of the Zammad MCP Server.

### Hall of Fame

Security researchers who have helped improve our security will be acknowledged here (with their permission).

## Updates to This Policy

This security policy may be updated periodically. Major changes will be announced through:
- GitHub Releases
- Repository announcements
- Security advisories (if applicable)

---

**Last Updated**: 2025-07-08
**Version**: 1.0
