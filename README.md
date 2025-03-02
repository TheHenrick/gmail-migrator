# Gmail Migrator

A tool to help users migrate their Gmail emails to other email service providers like Outlook, Yahoo Mail, and others.

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

- Python 3.8+
- Docker (optional, for containerized deployment)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/gmail-migrator.git
   cd gmail-migrator
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure your environment variables:
   ```
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Running with Docker

```bash
docker compose up -d
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 