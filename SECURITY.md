# Security Policy

This policy applies to the `signnow/sn-mcp-server` repository and any packages published from it (e.g., the PyPI package, if applicable).

## Supported versions

We provide security fixes for the latest minor release line (N) and the previous one (N-1). Older versions may receive fixes at our discretion.

| Version line | Supported |
|--------------|-----------|
| 0.1.x (latest) | ✅ |
| < 0.1          | ❌ |

## Reporting a vulnerability (preferred channel)

Please **do not** open public issues for security problems.

Use GitHub’s **Private vulnerability reporting**:
1) Go to this repository → **Security** tab → **Report a vulnerability**.  
2) Fill out the advisory form with:
- Affected version(s) and environment
- Impact and clear reproduction steps (PoC if possible)
- Any suggested mitigation/fix
- (Optional) CVSS v3.1 vector and your severity assessment
- Your GitHub handle and preferred credit name

If you cannot use GitHub, you may email the maintainers at **[add your security email/contact here]**. Consider sharing encrypted details or a link to a secure channel.  

We will acknowledge within **3 business days**, triage within **7 business days**, and keep you updated throughout remediation.

## Remediation & disclosure

For confirmed issues we will:
- Assign a severity, create a private advisory, and work in a private fix branch/fork.
- Target timelines (guidelines, not guarantees):
  - **Critical:** fix or mitigation target ≤ 14 days  
  - **High:** ≤ 30 days  
  - **Medium:** ≤ 90 days  
  - **Low:** best effort / next release
- Publish a security advisory with release notes once a fix is available, and **credit the reporter** unless you request otherwise.

Please give us reasonable time to remediate before any public disclosure.

## Scope

**In scope:** vulnerabilities in this repository and its released artifacts (server binaries/containers/packages).  
**Out of scope:** issues in SignNow production services, APIs, web apps, infrastructure, or third-party platforms. For those, use the official SignNow channels.

## Acceptable testing / Out-of-scope findings

Good-faith, non-destructive research is welcome. Please **do not**:
- Perform denial-of-service, spam, or load testing against SignNow or third-party systems
- Exfiltrate or access data that is not yours
- Use social engineering, phishing, or physical intrusion
- Report issues that only affect third-party dependencies **without** showing exploitability in this project
- Disclose secrets or tokens belonging to real users

## Safe Harbor

We will not initiate legal action for good-faith research that:
- Stays within scope and avoids privacy violations or service disruption
- Uses your own accounts/test data
- Reports findings privately and allows reasonable remediation time

## Hardening guidance (recommended)

- **Never commit secrets**; use environment variables or a secret manager
- In **HTTP mode**, run behind **HTTPS** (reverse proxy/ingress) and use short-lived tokens
- In production, **provide a persistent RSA private key** for OAuth via `OAUTH_RSA_PRIVATE_PEM` (rotate and back up securely)
- Restrict `ALLOWED_REDIRECTS` to known URIs; use least-privilege SignNow credentials and rotate regularly

See the project README for setup and configuration details.
