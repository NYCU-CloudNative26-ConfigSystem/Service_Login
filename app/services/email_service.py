"""Email service with switchable providers (Mailtrap, Brevo, Amazon SES)."""
from __future__ import annotations

from abc import ABC, abstractmethod
import os
from typing import Optional

from app.core.config import settings
from app.core.logging import logger


class BaseEmailProvider(ABC):
    """Provider abstraction for sending email messages."""

    @abstractmethod
    def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        raise NotImplementedError


class MockEmailProvider(BaseEmailProvider):
    """No-op email sender for tests/local development."""

    def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        logger.info(
            "Mock email sent",
        )
        logger.debug(
            "mock_email to=%s subject=%s text=%s",
            to_email,
            subject,
            text_body,
        )
        return True


class MailtrapEmailProvider(BaseEmailProvider):
    """Mailtrap transactional email sender using the official SDK."""

    def __init__(self):
        try:
            import mailtrap as mt
        except ImportError as exc:
            raise RuntimeError(
                "mailtrap package is required when EMAIL_PROVIDER=mailtrap"
            ) from exc

        if not settings.mailtrap_api_token:
            raise RuntimeError("MAILTRAP_API_TOKEN is required when EMAIL_PROVIDER=mailtrap")

        self._mt = mt
        self._client = mt.MailtrapClient(token=settings.mailtrap_api_token)

    def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        try:
            mail = self._mt.Mail(
                sender=self._mt.Address(
                    email=settings.email_from,
                    name=settings.mailtrap_sender_name,
                ),
                to=[self._mt.Address(email=to_email)],
                subject=subject,
                text=text_body,
                html=html_body,
                category=settings.mailtrap_category,
            )
            response = self._client.send(mail)
            success = response.get("success") if isinstance(response, dict) else getattr(response, "success", False)
            if not success:
                logger.error("Mailtrap email send failed: %s", response)
            return bool(success)
        except Exception as exc:
            logger.error(f"Mailtrap email send failed: {exc}")
            return False


class BrevoEmailProvider(BaseEmailProvider):
    """Brevo transactional email provider."""

    def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        if not settings.brevo_api_key:
            logger.error("Brevo API key is missing")
            return False

        try:
            import httpx
        except ImportError as exc:
            logger.error("httpx is required when EMAIL_PROVIDER=brevo: %s", exc)
            return False

        payload = {
            "sender": {"email": settings.email_from},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body,
        }
        headers = {
            "accept": "application/json",
            "api-key": settings.brevo_api_key,
            "content-type": "application/json",
        }

        try:
            response = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.error(f"Brevo email send failed: {exc}")
            return False


class AmazonSESEmailProvider(BaseEmailProvider):
    """Amazon SES sender using boto3."""

    def __init__(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required when EMAIL_PROVIDER=ses") from exc

        kwargs = {
            "region_name": settings.ses_region,
        }
        if settings.ses_access_key_id and settings.ses_secret_access_key:
            kwargs["aws_access_key_id"] = settings.ses_access_key_id
            kwargs["aws_secret_access_key"] = settings.ses_secret_access_key
        self._client = boto3.client("ses", **kwargs)

    def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        try:
            self._client.send_email(
                Source=settings.email_from,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {
                        "Html": {"Data": html_body},
                        "Text": {"Data": text_body},
                    },
                },
            )
            return True
        except Exception as exc:
            logger.error(f"Amazon SES email send failed: {exc}")
            return False


class EmailService:
    """Facade service for application email operations."""

    _provider: Optional[BaseEmailProvider] = None

    @staticmethod
    def _should_force_mock_provider() -> bool:
        return bool(os.getenv("PYTEST_CURRENT_TEST"))

    @classmethod
    def _build_provider(cls) -> BaseEmailProvider:
        if cls._should_force_mock_provider():
            return MockEmailProvider()

        provider = settings.email_provider.strip().lower()

        if provider == "mailtrap":
            return MailtrapEmailProvider()
        if provider == "brevo":
            return BrevoEmailProvider()
        if provider == "ses":
            return AmazonSESEmailProvider()
        return MockEmailProvider()

    @classmethod
    def _get_provider(cls) -> BaseEmailProvider:
        if cls._provider is None:
            cls._provider = cls._build_provider()
        return cls._provider

    @classmethod
    def _send_email(cls, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        try:
            return cls._get_provider().send(to_email, subject, html_body, text_body)
        except Exception as exc:
            logger.error(f"Email send failed: {exc}")
            return False

    @classmethod
    def send_verification_code(cls, to_email: str, code: str) -> bool:
        subject = "Your email verification code"
        text_body = (
            f"Your verification code is {code}. "
            f"It will expire in {settings.email_verification_code_ttl_seconds // 60} minutes."
        )
        html_body = (
            f"<p>Your verification code is <strong>{code}</strong>.</p>"
            f"<p>It will expire in {settings.email_verification_code_ttl_seconds // 60} minutes.</p>"
        )
        return cls._send_email(to_email, subject, html_body, text_body)

    @classmethod
    def send_password_reset_code(cls, to_email: str, code: str) -> bool:
        subject = "Your password reset code"
        text_body = (
            f"Your password reset code is {code}. "
            f"It will expire in {settings.password_reset_code_ttl_seconds // 60} minutes."
        )
        html_body = (
            f"<p>Your password reset code is <strong>{code}</strong>.</p>"
            f"<p>It will expire in {settings.password_reset_code_ttl_seconds // 60} minutes.</p>"
        )
        return cls._send_email(to_email, subject, html_body, text_body)
