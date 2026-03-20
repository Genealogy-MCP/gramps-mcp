# Security Policy

## Supported Versions

Only the current release receives security fixes. No LTS versions are maintained.

| Version | Supported |
| ------- | --------- |
| 2.1.x   | Yes       |
| < 2.1   | No        |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Use [GitHub Private Security Advisories](https://github.com/Genealogy-MCP/gramps-mcp/security/advisories/new)
to report any vulnerability confidentially.

### What to expect

- **Acknowledgement:** within 7 days of submission.
- **Coordinated disclosure window:** 90 days from acknowledgement. We will work with
  you to develop and release a fix before any public disclosure.
- **If accepted:** a patched release will be published and you will be credited in the
  changelog (unless you prefer to remain anonymous).
- **If declined:** you will receive a clear explanation of why the report does not
  qualify as a security vulnerability in this project.

### Scope

This server runs locally and communicates with a self-hosted Gramps Web API instance
that you control. Reports relevant to credential handling, injection vulnerabilities in
tool inputs, data leakage in MCP responses, or transport security are in scope.
