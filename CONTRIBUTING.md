# Contributing

Start with the [README](README.md) and [repository verification](REPOSITORY-VERIFICATION.md). Follow the existing architecture and keep changes focused on a reproduced problem or an explicit product requirement.

## Before submitting

1. Record the affected workflow, expected result, reproduction and actual result.
2. Run the documented checks before and after changes. Add regression coverage when behaviour changes; avoid tests that only repeat the implementation.
3. For UI changes, exercise phone, tablet and desktop widths, keyboard access, loading/error states and refresh recovery. Label browser emulation accurately.
4. Preserve existing user data and configuration. Never commit credentials, personal documents, recordings, financial records or exported capability keys.
5. Explain the change, its validation and remaining limits in the pull request. Separate local tests, CI and live-production evidence.

## Reporting issues

For an ordinary defect, include browser/runtime versions, viewport, steps and a sanitised example. Do not attach real customer or financial data. Report security problems privately using [SECURITY.md](SECURITY.md).

Do not report a release as certified solely because its build passes. Tie production evidence to the intended source and complete the relevant acceptance journey.
