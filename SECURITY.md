# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do not open a public issue for security vulnerabilities.**

Instead, please email the maintainer directly or use GitHub's private vulnerability reporting feature.

## Scope

This project processes sensitive support data (sosreport, supportconfig) that may contain:

- Hostnames, IP addresses, subscription IDs
- Customer infrastructure topology
- Credentials or tokens (partial or full)
- Security incident traces

## Security Measures in the Codebase

- **Archive extraction** uses path traversal protection (rejects members that escape the target directory)
- **No external dependencies** — reduces supply chain attack surface
- **No network calls** — all processing is local-only
- **Data minimization** — Copilot instructions enforce summary over raw output
- **Redaction rules** — customer-facing outputs replace sensitive values with placeholders

## Data Handling

- Never commit real customer data to this repository
- Log files are analyzed in their original location — never copied into the repo
- The `cases/` directory contains only generated markdown outputs
- The `.gitignore` excludes common data file patterns

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest `main` | Yes |
| Older commits | Best effort |
