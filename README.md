# Gmail Migrator

[![CI](https://github.com/TheHenrick/gmail-migrator/actions/workflows/ci.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/ci.yml)
[![Pre-commit](https://github.com/TheHenrick/gmail-migrator/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/pre-commit.yml)
[![Docker Compose Test](https://github.com/TheHenrick/gmail-migrator/actions/workflows/docker-compose-test.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/docker-compose-test.yml)
[![Signed Commits](https://github.com/TheHenrick/gmail-migrator/actions/workflows/verify-commit-signature.yml/badge.svg)](https://github.com/TheHenrick/gmail-migrator/actions/workflows/verify-commit-signature.yml)

A tool to help users migrate their Gmail emails to other email service providers like Outlook, Yahoo Mail, and others.

## Features

### Implemented Features

- **Authentication & Connection**
  - Connect to Gmail using OAuth2
  - Connect to Outlook using Microsoft Graph API
  - Secure credential management with token refresh

- **Email Retrieval & Processing**
  - Fetch emails from Gmail with filtering options
  - Process email content while maintaining formatting
  - Handle email metadata

- **Email Migration**
  - Migrate individual emails from Gmail to Outlook
  - Batch migration of multiple emails
  - Transfer emails with attachments
  - Create folders in Outlook for organizing migrated emails
  - Migrate Gmail labels to Outlook folders
  - Migrate emails by label to corresponding folders
  - Full migration of all emails preserving label structure

- **User Interface**
  - Basic web interface following Apple HIG principles
  - OAuth connection workflow for Gmail and Outlook

- **API Endpoints**
  - Gmail authentication and email retrieval
  - Outlook authentication, folder management, and email migration
  - Health check endpoint
  - Migration endpoints for Gmail to Outlook transfers:
    - `/migration/gmail-to-outlook/labels`: Migrate Gmail labels to Outlook folders
    - `/migration/gmail-to-outlook/by-label`: Migrate emails from a specific Gmail label
    - `/migration/gmail-to-outlook/all`: Migrate all emails preserving label structure

### Planned Features

- **Authentication & Connection**
  - Connect to Yahoo Mail using OAuth2
  - Support for additional email providers

- **Email Retrieval & Processing**
  - Advanced filtering options (date ranges, labels, search queries)
  - Improved handling of email threads and conversations

- **Email Migration**
  - Migration to Yahoo and other providers
  - Improved preservation of email metadata (read/unread status)
  - Better maintenance of folder structures and label hierarchies

- **User Interface**
  - Enhanced, responsive web interface
  - Real-time progress reporting during migration
  - Detailed migration statistics and reporting

- **Reliability & Performance**
  - Parallel processing for faster migrations
  - Automatic retries for failed transfers
  - Resumable migrations after interruption
  - Rate limiting to prevent API throttling

- **Security**
  - End-to-end encryption for data in transit
  - No permanent storage of email content
  - Temporary caching with secure deletion

## Getting Started

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- Docker and Docker Compose (optional, for containerized deployment)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/TheHenrick/gmail-migrator.git
   cd gmail-migrator
   ```

2. Install dependencies with Poetry:
   ```
   poetry install
   ```

3. Configure environment variables:
   ```
   cp .env.example .env
   # Edit .env with your OAuth credentials
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

### Using the Application

1. Access the web interface at http://localhost:8000
2. Configure OAuth credentials:
   - Click on "OAuth Settings" in the Migration Options section
   - Enter your OAuth credentials for Gmail and Outlook
   - Save your settings

3. Start the migration:
   - Connect to your Gmail account
   - Connect to your Outlook account
   - Select emails to migrate
   - Choose destination folder (optional)
   - Click "Start Migration"

### OAuth Configuration

This application uses OAuth for secure API access. You'll need to create OAuth applications in:

- Google Cloud Platform (for Gmail access)
- Microsoft Azure Portal (for Outlook access)
- Yahoo Developer Network (for Yahoo Mail access, planned)

When creating these applications, set the redirect URIs to:
- Gmail: `http://localhost:8000/gmail/auth-callback`
- Outlook: `http://localhost:8000/outlook/auth-callback`
- Yahoo: `http://localhost:8000/yahoo/auth-callback`

Enter the client IDs and secrets in the application's OAuth Settings modal or in your `.env` file.

#### Creating Gmail OAuth Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" and select "OAuth client ID"
5. If prompted, configure the OAuth consent screen:
   - User Type: External
   - App name: Gmail Migrator
   - User support email: Your email
   - Developer contact information: Your email
   - Authorized domains: Add your domain if applicable
6. For the OAuth client ID:
   - Application type: Web application
   - Name: Gmail Migrator
   - Authorized JavaScript origins: `http://localhost:8000`
   - Authorized redirect URIs: `http://localhost:8000/gmail/auth-callback`
7. Click "Create" and note your Client ID and Client Secret
8. Enable the Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API" and enable it

#### Creating Outlook OAuth Credentials

1. Go to the [Microsoft Azure Portal](https://portal.azure.com/)
2. Navigate to "Microsoft Entra" > "Applications" > "App registrations"
3. Click "New registration"
4. Enter the following information:
   - Name: Gmail Migrator
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: Web > `http://localhost:8000/outlook/auth-callback`
5. Click "Register"
6. Note your Application (client) ID from the Overview page
7. Navigate to "Certificates & secrets" in the left menu
8. Under "Client secrets", click "New client secret"
9. Add a description and select an expiration period
10. Click "Add" and note the Value (this is your client secret)
11. Navigate to "API permissions" in the left menu
12. Click "Add a permission" > "Microsoft Graph" > "Delegated permissions"
13. Add the following permissions:
    - Mail.Read
    - Mail.ReadWrite
    - Mail.Send
    - User.Read
14. Click "Add permissions"
15. Click "Grant admin consent" if you have admin rights

## Development

### Project Structure

```
gmail-migrator/
├── app/                    # Main application code
│   ├── api/                # API endpoints
│   │   └── routers/        # API routers (Gmail, Outlook)
│   │   └── services/       # Service implementations
│   │   └── utils/          # Utility functions
│   ├── config/             # Configuration settings
│   ├── models/             # Data models
│   ├── static/             # Static assets
│   ├── templates/          # HTML templates
│   └── utils/              # Utility functions
├── scripts/                # Development scripts
├── tests/                  # Test suite
├── .github/                # GitHub workflows
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile              # Docker configuration
├── pyproject.toml          # Poetry configuration
└── README.md               # Project documentation
```

### Setting Up Development Environment

1. Install development dependencies:
   ```bash
   poetry install
   ```

2. Install pre-commit hooks:
   ```bash
   poetry run pre-commit install
   ```

3. Set up your OAuth credentials in `.env` file:
   ```
   GMAIL_CLIENT_ID=your_client_id
   GMAIL_CLIENT_SECRET=your_client_secret
   GMAIL_REDIRECT_URI=http://localhost:8000/gmail/auth-callback
   OUTLOOK_CLIENT_ID=your_client_id
   OUTLOOK_CLIENT_SECRET=your_client_secret
   OUTLOOK_REDIRECT_URI=http://localhost:8000/outlook/auth-callback
   ```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run tests with coverage report
poetry run pytest --cov=app --cov-report=term --cov-report=html

# Run specific test file
poetry run pytest tests/test_gmail_client.py
```

### Code Quality Tools

The project uses several code quality tools:

1. **Ruff** for linting and formatting:
   ```bash
   # Run linting
   poetry run ruff check .

   # Run formatting
   poetry run ruff format .
   ```

2. **MyPy** for type checking:
   ```bash
   poetry run mypy .
   ```

3. **Pre-commit** for automated checks:
   ```bash
   poetry run pre-commit run --all-files
   ```

4. **Convenience scripts**:
   ```bash
   # Format code
   poetry run format

   # Run linting
   poetry run lint

   # Run type checking
   poetry run typecheck

   # Run all checks
   poetry run checks

   # Run tests
   poetry run test
   ```

### Contribution Workflow

1. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure all tests pass:
   ```bash
   poetry run checks
   poetry run test
   ```

3. Commit your changes with a descriptive message:
   ```bash
   git add .
   git commit -S -m "Add detailed description of all changes"
   ```

4. Push your branch to GitHub:
   ```bash
   git push origin feature/your-feature-name
   ```

5. Create a pull request using GitHub CLI:
   ```bash
   gh pr create --title "Your PR title" --body "Description of your changes"
   ```

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Docker

### Building the Docker Image

You can build the Docker image using the following command:

```bash
docker compose build
```

This will create a Docker image with the tag `gmail-migrator-app:latest`.

### Running the Docker Container

You can run the Docker container using the following command:

```bash
docker compose up -d
```

This will start the container in detached mode. You can access the application at http://localhost:8000.

### Production Deployment

For production deployment, you can use the production Docker Compose file:

```bash
docker compose -f docker-compose.prod.yml up -d
```

This will use the pre-built image with the tag `gmail-migrator:v0.2.0` and set the appropriate production settings.

### Docker Image Tags

- `gmail-migrator-app:latest`: Latest development build
- `gmail-migrator:v0.2.0`: Stable release with email migration feature
