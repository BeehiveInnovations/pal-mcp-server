# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 9.x.x   | :white_check_mark: |
| < 9.0   | :x:                |

## Important Disclaimer

PAL MCP is an open-source Model Context Protocol (MCP) server that acts as middleware between AI clients (Claude Code, Codex CLI, Cursor, etc.) and various AI model providers.

**Please understand the following:**

- **No Warranty**: This software is provided "AS IS" under the Apache 2.0 License, without warranties of any kind. See the [LICENSE](LICENSE) file for full terms.
- **User Responsibility**: The AI client (not PAL MCP) controls tool invocations and workflows. Users are responsible for reviewing AI-generated outputs and actions.
- **API Key Security**: You are responsible for securing your own API keys. Never commit keys to version control or share them publicly.
- **Third-Party Services**: PAL MCP connects to external AI providers (Google, OpenAI, Azure, etc.). Their terms of service and privacy policies apply to data sent through this server.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

### Preferred Method

Use [GitHub Security Advisories](https://github.com/BeehiveInnovations/pal-mcp-server/security/advisories/new) to report vulnerabilities privately.

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact
- Suggested fix (optional)

### What to Expect

- We will acknowledge your report and assess the issue
- Critical issues will be prioritized
- We'll keep you informed of progress as work proceeds

We cannot commit to specific response timelines, but we take security seriously.

### After Resolution

We welcome security researchers to submit a pull request with the fix. This is an open-source project and we appreciate community contributions to improve security.

## Disclosure Policy

We practice coordinated disclosure. Please allow reasonable time to address issues before public disclosure. We'll work with you on timing.

## Scope

### In Scope

- Authentication/authorization bypasses
- Injection vulnerabilities (command injection, prompt injection with security impact)
- Information disclosure (API keys, sensitive data leakage)
- Denial of service vulnerabilities in the MCP server itself
- Dependency vulnerabilities with exploitable impact

### Out of Scope

- Issues in upstream AI providers (report to Google, OpenAI, etc. directly)
- Issues in AI client software (report to Anthropic, OpenAI, Cursor, etc.)
- AI model behavior or outputs (this is controlled by the AI client and model providers)
- Social engineering attacks
- Rate limiting or resource exhaustion on third-party APIs

## Security Best Practices for Users

1. **Protect API Keys**: Store keys in `.env` files (gitignored) or environment variables
2. **Review AI Actions**: Always review AI-suggested code changes before applying
3. **Use Local Models**: For sensitive codebases, consider using Ollama with local models
4. **Network Security**: When self-hosting, ensure appropriate network controls
5. **Keep Updated**: Regularly update to the latest version for security fixes

## Recognition

We appreciate responsible disclosure and will credit security researchers in release notes (unless you prefer anonymity).
