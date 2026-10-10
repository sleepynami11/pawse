# Security

Pawse is an early hackathon project and has no production release or promised security response schedule.

## Reporting a vulnerability

Please use this repository's GitHub **Security → Report a vulnerability** option if available. Do not post credentials or exploit details in public issues. If private reporting is unavailable, open an issue asking the maintainer for a private contact channel without including sensitive details.

## Credential handling

- Keep permanent Gemini API keys on the server, outside source control.
- Use short-lived tokens for browser Live API sessions.
- Avoid logging tokens, private page contents, or raw voice recordings by default.
- Revoke and replace a leaked key immediately; deleting it from the latest commit does not remove it from history.
- Replace temporary hackathon credentials before continuing after the event.
