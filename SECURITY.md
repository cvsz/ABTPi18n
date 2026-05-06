# Security Policy

ABTPro i18n is an automated cryptocurrency trading platform that handles exchange API credentials, trading configuration, OAuth sessions, payment callbacks, and operational telemetry. Security reports are treated as high priority and are coordinated privately until a fix or mitigation is available.

## Supported Versions

The project follows [Semantic Versioning](https://semver.org/) for release numbering. Security fixes are provided for the latest stable minor release and may be backported to older lines only when a maintainer explicitly announces extended support.

| Version | Status | Security Support |
| --- | --- | --- |
| 1.0.1 | Current stable release | ✅ Supported |
| 1.0.0 | Initial stable release | ⚠️ Critical fixes only until users can upgrade to 1.0.1 |
| < 1.0.0 | Pre-release / development snapshots | ❌ Not supported |

Users should deploy the newest stable release as soon as practical, especially when release notes mention dependency, cryptography, authentication, or trading-safety fixes.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately. Do **not** open a public GitHub issue, discussion, pull request, or social-media post containing exploit details.

### Preferred private channels

1. Use GitHub's private vulnerability reporting feature for this repository, if available.
2. If private reporting is unavailable, email the project security contact listed in the enterprise troubleshooting documentation: `security@abtpro.com`.
3. If neither channel is available, contact a maintainer through the repository owner profile and request a private security-reporting channel before sharing technical details.

### What to include

Please include as much of the following as possible:

- Affected version, commit SHA, deployment mode, and relevant configuration flags.
- Component or surface area involved, such as backend API, frontend session handling, worker loop, encryption service, exchange adapter, payment callback, Telegram webhook, CI/CD workflow, Docker image, or documentation.
- Clear reproduction steps, proof-of-concept code, screenshots, logs, or HTTP requests.
- Impact assessment, including whether the issue could expose secrets, enable unauthorized trading, bypass authentication or authorization, manipulate balances or orders, compromise payment flows, corrupt audit logs, or cause denial of service.
- Any known mitigations or temporary workarounds.
- Your preferred name, organization, and disclosure-credit preference.

Please do not include real exchange API keys, OAuth refresh tokens, production database dumps, private keys, payment secrets, or customer personal data in the report. Redact secrets and use test accounts whenever possible.

## Response Targets

The following targets are goals, not contractual service-level agreements:

| Severity | Examples | Initial Response | Status Updates | Target Fix / Mitigation |
| --- | --- | --- | --- | --- |
| Critical | Remote code execution, credential disclosure, unauthorized live trading, authentication bypass, private-key exposure | 24 hours | Every 24-48 hours | 7 days |
| High | Privilege escalation, payment callback forgery, severe SSRF, sensitive data exposure, exploitable dependency with reachable impact | 48 hours | Every 3-5 days | 14 days |
| Medium | Limited information disclosure, CSRF with constrained impact, rate-limit bypass, non-critical dependency issue | 5 business days | Weekly | 30 days |
| Low | Hardening gaps, missing headers, low-impact denial of service, documentation security issue | 10 business days | As needed | Next scheduled release |

If a report is declined, maintainers will explain the reason when it is safe to do so.

## Coordinated Disclosure

- Maintainers will acknowledge valid reports, investigate privately, and coordinate a release or mitigation before public disclosure.
- Reporters are asked to allow a reasonable remediation period and to avoid active exploitation, data exfiltration, persistence, lateral movement, or service disruption.
- Once a fix is released, maintainers may publish a security advisory, changelog entry, CVE reference, or release note with appropriate credit, unless the reporter requests otherwise.
- If active exploitation is detected, maintainers may accelerate disclosure and mitigation steps to protect users.

## Security Scope

### In scope

- Source code and configuration committed to this repository.
- Authentication, authorization, OAuth state validation, session cookies, JWT handling, and webhook verification.
- Encryption, key management, secret rotation, credential storage, and decryption paths for exchange API keys.
- Trading safety controls, including permission checks, risk limits, circuit breakers, strategy execution boundaries, and order-routing safeguards.
- Payment and rental-contract flows where they affect authorization, account balances, subscription state, or callback integrity.
- Build, packaging, release, Docker, CI/CD, and dependency-management workflows.
- Documentation that could cause insecure production deployment when followed.

### Out of scope

- Vulnerabilities in third-party exchanges, OAuth providers, Telegram, payment providers, hosting providers, or user-managed infrastructure unless ABTPro i18n integration code is directly responsible.
- Findings that require physical access to a user's device or compromised administrator credentials.
- Social engineering, phishing, spam, or attacks against project maintainers or users.
- Denial-of-service testing that degrades public services or third-party APIs.
- Automated scanner output without a plausible exploit path or practical impact.
- Reports about missing security headers or cookie flags in non-production development settings unless the issue is also present in production configuration.

## Production Security Baseline

Operators should treat ABTPro i18n as high-risk financial automation software and apply the following baseline before connecting live exchange accounts:

- Use HTTPS everywhere and terminate TLS with modern ciphers.
- Store `ENCRYPTION_KEY`, OAuth secrets, JWT signing keys, exchange credentials, payment secrets, and database passwords in a dedicated secret manager.
- Use 256-bit encryption keys for AES-GCM and rotate application secrets on a regular schedule.
- Disable exchange withdrawals on API keys and use exchange-side IP allowlists when supported.
- Grant least-privilege permissions to databases, workers, CI/CD tokens, container registries, and cloud identities.
- Enable httpOnly, Secure, and SameSite cookie attributes for browser sessions.
- Validate OAuth `state`, registered redirect URIs, Telegram webhook signatures, payment callback authenticity, and all inbound webhook payloads.
- Enable rate limiting on authentication, exchange-key management, payment, webhook, and trading-control endpoints.
- Keep PostgreSQL, Redis, Python, Node.js, Docker images, and all project dependencies patched.
- Run static analysis, dependency audits, secret scanning, and container scanning before release.
- Maintain immutable audit logs for authentication events, API-key changes, strategy changes, order submissions, payment callbacks, and administrative actions.
- Test disaster recovery, backup restoration, secret rotation, and emergency trading shutdown procedures before production use.

## Dependency and Supply-Chain Security

- Review dependency updates for security advisories before each release.
- Prefer pinned, reproducible dependency sets and lockfiles for deployable artifacts.
- Do not commit generated secrets, private keys, `.env` files containing real credentials, database dumps, or production logs.
- Treat build scripts, GitHub Actions, Dockerfiles, and package-manager configuration as security-sensitive code.
- Validate release artifacts and container images before promoting them to production.

## Incident Handling

If you believe your deployment has been compromised:

1. Stop affected bots and disable automated trading.
2. Revoke exchange API keys, OAuth tokens, JWT/session signing keys, payment secrets, and webhook secrets that may have been exposed.
3. Preserve logs and evidence before rebuilding systems.
4. Rotate `ENCRYPTION_KEY` through a controlled re-encryption process rather than replacing it without a migration plan.
5. Rebuild from a trusted release artifact and verify dependency integrity.
6. Review audit logs for unauthorized login, credential, strategy, payment, or order activity.
7. Notify affected users, exchanges, payment providers, and regulators when required by law or contract.

## Safe Harbor

The project intends to work constructively with security researchers who:

- Make a good-faith effort to avoid privacy violations, data destruction, financial harm, and service disruption.
- Access only accounts, data, and systems they own or are explicitly authorized to test.
- Report findings promptly and keep vulnerability details confidential until coordinated disclosure.
- Do not use discovered vulnerabilities to trade, withdraw funds, manipulate markets, or access unrelated user data.

Good-faith research conducted within this policy will not be pursued by project maintainers as a legal claim. This statement does not bind third parties or waive obligations under applicable law.

## Security-Related Documentation

Additional operational security details are available in:

- `docs/guides/SECURITY.md` for the platform security model and encryption lifecycle.
- `docs/guides/RELEASE.md` for release workflow expectations.
- `CHANGELOG.md` for version-specific security updates.
