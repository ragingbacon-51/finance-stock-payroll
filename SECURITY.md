# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately. Do not open a public issue for a security vulnerability.

Use the repository's GitHub **Security > Report a vulnerability** page for a private report. Include:

- Affected component and steps to reproduce
- Potential impact
- Relevant logs or screenshots with secrets removed
- Suggested remediation, if known

## Response expectations

The maintainer aims to acknowledge reports within 5 business days and will coordinate a fix and disclosure timeline with the reporter.

## Production status

This project is not production-ready. Before deployment:

- Set `DEBUG=False` and a unique random `SECRET_KEY` of at least 50 characters.
- Configure explicit `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- Use PostgreSQL or another appropriately managed database and take verified backups.
- Serve only over HTTPS, with secure cookies and security headers.
- Store receipts outside public web storage and enforce authenticated private access.
- Never commit `.env`, credentials, employee data, receipts, or database backups.
- Configure login throttling and an additional hosting-edge rate limit.
- Review statutory payroll rules and Kenyan data protection requirements.
- Run Django deployment checks and dependency/security scans before release.
