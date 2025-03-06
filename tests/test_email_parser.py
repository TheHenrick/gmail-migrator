"""Tests for the email parser utility functions."""

from app.utils.email_parser import (
    create_mime_message,
    decode_body,
    extract_email_address,
    extract_recipients,
    format_email_address,
    parse_date,
)


class TestEmailParser:
    """Test cases for email parser utility functions."""

    def test_extract_email_address_with_name(self):
        """Test extracting email address with a name."""
        email_string = '"John Doe" <john.doe@example.com>'
        name, address = extract_email_address(email_string)
        assert name == "John Doe"
        assert address == "john.doe@example.com"

    def test_extract_email_address_without_quotes(self):
        """Test extracting email address with a name but without quotes."""
        email_string = "John Doe <john.doe@example.com>"
        name, address = extract_email_address(email_string)
        assert name == "John Doe"
        assert address == "john.doe@example.com"

    def test_extract_email_address_only(self):
        """Test extracting just an email address without a name."""
        email_string = "john.doe@example.com"
        name, address = extract_email_address(email_string)
        assert name == ""
        assert address == "john.doe@example.com"

    def test_extract_email_address_empty(self):
        """Test extracting from an empty string."""
        email_string = ""
        name, address = extract_email_address(email_string)
        assert name == ""
        assert address == ""

    def test_format_email_address_with_name(self):
        """Test formatting an email address with a name."""
        name = "John Doe"
        email_address = "john.doe@example.com"
        formatted = format_email_address(name, email_address)
        assert formatted == '"John Doe" <john.doe@example.com>'

    def test_format_email_address_without_name(self):
        """Test formatting an email address without a name."""
        name = ""
        email_address = "john.doe@example.com"
        formatted = format_email_address(name, email_address)
        assert formatted == "john.doe@example.com"

    def test_parse_date_valid(self):
        """Test parsing a valid date string."""
        date_string = "Mon, 15 Jan 2024 14:30:45 +0000"
        parsed = parse_date(date_string)
        assert "2024-01-15" in parsed
        assert "14:30:45" in parsed

    def test_parse_date_invalid(self):
        """Test parsing an invalid date string."""
        date_string = "Invalid Date"
        parsed = parse_date(date_string)
        assert parsed == "Invalid Date"

    def test_parse_date_empty(self):
        """Test parsing an empty date string."""
        date_string = ""
        parsed = parse_date(date_string)
        assert parsed == ""

    def test_decode_body_valid(self):
        """Test decoding a valid base64 encoded body."""
        # "Hello World" in base64
        test_data = "SGVsbG8gV29ybGQ="
        part = {"body": {"data": test_data}}
        decoded = decode_body(part)
        assert decoded == "Hello World"

    def test_decode_body_with_padding(self):
        """Test decoding base64 that needs padding."""
        # "Test" in base64 without padding
        test_data = "VGVzdA"  # Should be "VGVzdA=="
        part = {"body": {"data": test_data}}
        decoded = decode_body(part)
        assert decoded == "Test"

    def test_decode_body_empty(self):
        """Test decoding with empty data."""
        part = {"body": {"data": ""}}
        decoded = decode_body(part)
        assert decoded == ""

    def test_decode_body_missing_data(self):
        """Test decoding with missing data structure."""
        part = {}
        decoded = decode_body(part)
        assert decoded == ""

        part = {"body": {}}
        decoded = decode_body(part)
        assert decoded == ""

    def test_create_mime_message_basic(self):
        """Test creating a basic MIME message."""
        email_data = {
            "subject": "Test Subject",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "body": {
                "plain": "Plain text content",
                "html": "<p>HTML content</p>",
            },
        }

        message = create_mime_message(email_data)
        assert message["Subject"] == "Test Subject"
        assert message["From"] == "sender@example.com"
        assert message["To"] == "recipient@example.com"

        # Check that both plain and HTML parts are included
        parts = [
            part
            for part in message.walk()
            if part.get_content_type() in ["text/plain", "text/html"]
        ]
        assert len(parts) == 2

        plain_parts = [
            part for part in parts if part.get_content_type() == "text/plain"
        ]
        html_parts = [part for part in parts if part.get_content_type() == "text/html"]

        assert len(plain_parts) == 1
        assert len(html_parts) == 1
        assert plain_parts[0].get_payload() == "Plain text content"
        assert html_parts[0].get_payload() == "<p>HTML content</p>"

    def test_create_mime_message_with_cc(self):
        """Test creating a MIME message with CC recipients."""
        email_data = {
            "subject": "Test Subject",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "cc": "cc@example.com",
            "body": {"plain": "Plain text content"},
        }

        message = create_mime_message(email_data)
        assert message["Cc"] == "cc@example.com"

    def test_create_mime_message_with_attachments(self):
        """Test creating a MIME message with attachments."""
        email_data = {
            "subject": "Test Subject",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "body": {"plain": "Plain text content"},
            "attachments": [
                {"filename": "test.txt"},
                {"filename": "test2.txt"},
            ],
        }

        attachments = [b"attachment content 1", b"attachment content 2"]
        message = create_mime_message(email_data, attachments)

        # Count attachments
        attachment_parts = [
            part
            for part in message.walk()
            if part.get_content_type() == "application/octet-stream"
        ]
        assert len(attachment_parts) == 2

        # Check filenames
        filenames = [part.get_filename() for part in attachment_parts]
        assert "test.txt" in filenames
        assert "test2.txt" in filenames

    def test_extract_recipients_all_types(self):
        """Test extracting all types of recipients."""
        email_data = {
            "to": "recipient1@example.com, recipient2@example.com",
            "cc": "cc1@example.com, cc2@example.com",
            "bcc": "bcc1@example.com, bcc2@example.com",
        }

        recipients = extract_recipients(email_data)
        assert recipients["to"] == ["recipient1@example.com", "recipient2@example.com"]
        assert recipients["cc"] == ["cc1@example.com", "cc2@example.com"]
        assert recipients["bcc"] == ["bcc1@example.com", "bcc2@example.com"]

    def test_extract_recipients_partial(self):
        """Test extracting recipients with some fields missing."""
        email_data = {
            "to": "recipient@example.com",
            # No CC or BCC
        }

        recipients = extract_recipients(email_data)
        assert recipients["to"] == ["recipient@example.com"]
        assert recipients["cc"] == []
        assert recipients["bcc"] == []

    def test_extract_recipients_empty(self):
        """Test extracting recipients from empty data."""
        email_data = {}
        recipients = extract_recipients(email_data)
        assert recipients["to"] == []
        assert recipients["cc"] == []
        assert recipients["bcc"] == []
