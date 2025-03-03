# Security Policy

## Supported Versions

Currently, this project is in early development. Security updates will be applied to the latest version.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Gmail Migrator, please follow these steps:

1. **Do not disclose the vulnerability publicly** until it has been addressed.
2. Email the details to [your-email@example.com](mailto:your-email@example.com) with "SECURITY VULNERABILITY" in the subject line.
3. Include detailed steps to reproduce the issue, and any proof-of-concept code if possible.
4. Allow time for the vulnerability to be addressed before public disclosure.

## Security Practices

### Signed Commits

All commits to this repository must be signed with a GPG key. This ensures that commits are verified and authenticated by their authors.

To sign your commits:

1. Set up a GPG key following [GitHub's instructions](https://docs.github.com/en/authentication/managing-commit-signature-verification/generating-a-new-gpg-key)
2. Configure Git to use your signing key:
   ```bash
   git config --global user.signingkey YOUR_KEY_ID
   git config --global commit.gpgsign true
   ```
3. Add your GPG key to your GitHub account

Pull requests with unsigned commits will be rejected by the CI/CD pipeline.

### Dependency Management

We regularly scan dependencies for vulnerabilities using:
- GitHub's Dependabot alerts
- `poetry` dependency management with version pinning
- Periodic review of dependency trees

### Code Review Process

All code changes undergo review before merging to ensure:
- No security vulnerabilities are introduced
- Authentication and authorization mechanisms are properly implemented
- Sensitive data is handled securely
- Input validation is comprehensive
