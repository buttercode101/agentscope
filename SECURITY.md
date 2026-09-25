# Security Policy

## Supported versions

The latest release on the default branch is the supported version.

AgentScope is designed to run locally and read existing agent state. It does not intentionally transmit source data, execution history, credentials, prompts, or tool payloads to a hosted AgentScope service.

## Reporting a vulnerability

Please report security vulnerabilities privately through GitHub's repository security advisory / private vulnerability reporting flow rather than opening a public issue.

Include:
- affected version or commit
- reproducible steps
- expected and actual behavior
- impact and any relevant logs or proof of concept

Do not include real API keys, access tokens, passwords, personal data, or private agent transcripts in a report.

## Security principles

- Read-only supervision; no operational controls are exposed by the generated dashboard.
- Local files are read directly and the dashboard is generated locally.
- HTML output escapes collected values before rendering.
- Optional integrations should be configured with the minimum filesystem/database access required.
