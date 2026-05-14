"""Tests for email provider selection."""

from app.services.email_service import EmailService, MockEmailProvider


def test_email_service_forces_mock_under_pytest(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "mailtrap")
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "tests/test_email_service.py::test_email_service_forces_mock_under_pytest (call)",
    )

    EmailService._provider = None

    provider = EmailService._build_provider()

    assert isinstance(provider, MockEmailProvider)
