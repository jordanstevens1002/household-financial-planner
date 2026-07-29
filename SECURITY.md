# Security policy

## Supported versions

Security fixes are applied to the latest released version. Older versions are not supported.

## Reporting a vulnerability

Use GitHub's private vulnerability-reporting feature for this repository. If private reporting is
not available, contact the repository owner privately through their GitHub profile. Do not include
tokens, passwords, production database dumps or real household financial data in a report.

Please include the affected version, configuration, reproduction steps, impact and any suggested
mitigation. GitHub sends an automatic notification that a private report was submitted, but it does
not provide the maintainer acknowledgement described here. The maintainer aims to acknowledge a
report manually within seven days, but this volunteer project does not guarantee a response or
remediation timeline.

## Deployment responsibilities

- Replace every example secret.
- Use a trusted OpenID Connect provider and HTTPS reverse proxy.
- Keep `ALLOW_DEVELOPMENT_AUTH=false` outside isolated local evaluation.
- Do not expose PostgreSQL or Appsmith administration directly to the internet.
- Restrict backup access and test restoration.
- Apply host, Docker and dependency security updates.
- Review logs without recording bearer tokens or personal financial payloads.

This project has not received a professional security audit and provides no compliance guarantee.
