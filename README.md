# Gmail Migrator

[![CI](https://github.com/TheHenrick/gmail-migrator/actions/workflows/ci.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/ci.yml)
[![Pre-commit](https://github.com/TheHenrick/gmail-migrator/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/pre-commit.yml)
[![Docker Compose Test](https://github.com/TheHenrick/gmail-migrator/actions/workflows/docker-compose-test.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/docker-compose-test.yml)
[![Signed Commits](https://github.com/TheHenrick/gmail-migrator/actions/workflows/verify-commit-signature.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/verify-commit-signature.yml)

A tool to help users migrate their Gmail emails to other email service providers like Outlook, Yahoo Mail, and others.

> **Note:** This repository requires GPG signed commits for all contributions.

## Features (Planned)

- Connect to Gmail using OAuth2
- Fetch emails from Gmail with filtering options
- Connect to destination email services
- Migrate emails with attachments
- Preserve folder structure and labels
- Migration progress tracking and reporting
- Error handling and retry mechanisms

## Getting Started

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- Docker (optional, for containerized deployment)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/gmail-migrator.git
   cd gmail-migrator
   ```

2. Install dependencies with Poetry:
   ```
   poetry install
   ```

3. Configure your environment variables:
   ```
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Running the application

#### Using Poetry

```bash
# Activate the Poetry virtual environment
poetry shell

# Run the application
python wsgi.py
```

#### Using Docker Compose

```bash
docker compose up -d
```

## Development

### Running tests

```bash
# Using Poetry
poetry run pytest

# Or within the Poetry shell
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Signed Commits

This repository requires signed commits to enhance security and verify the authenticity of contributions. **This requirement applies to all commits made after March 2025.**

To set up signed commits:

1. Generate a GPG key if you don't have one:
   ```bash
   gpg --full-generate-key
   ```

2. Get your GPG key ID:
   ```bash
   gpg --list-secret-keys --keyid-format=long
   ```

3. Configure Git to use your key:
   ```bash
   git config --global user.signingkey YOUR_KEY_ID
   git config --global commit.gpgsign true
   ```

4. Add your GPG key to your GitHub account: [GitHub GPG Keys](https://github.com/settings/keys)

5. Sign your commits automatically or use the `-S` flag:
   ```bash
   git commit -S -m "Your commit message"
   ```
