from typing import Any

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr, NameEmail

from app.core import settings

FM = FastMail(
    ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USERNAME,
        MAIL_PASSWORD=settings.SMTP_PASSWORD,
        MAIL_FROM=settings.SMTP_FROM,
        MAIL_PORT=settings.SMTP_PORT,
        MAIL_SERVER=settings.SMTP_SERVER,
        MAIL_STARTTLS=settings.SMTP_START_TLS,
        MAIL_SSL_TLS=settings.SMTP_SSL_TLS,
        USE_CREDENTIALS=True,
        TEMPLATE_FOLDER=settings.TEMPLATE_DIR / "email",
    )
)


class MailService:
    def __init__(self, mail_client: FastMail) -> None:
        self._mail_client = mail_client

    async def send(
        self,
        *,
        to: EmailStr,
        subject: str,
        html: str,
    ) -> None:
        message = MessageSchema(
            subject=subject,
            recipients=[NameEmail(email=to, name="")],
            body=html,
            subtype=MessageType.html,
        )
        await self._mail_client.send_message(message)

    async def send_with_template(
        self,
        *,
        to: EmailStr,
        subject: str,
        template_name: str,
        context: dict[str, Any],
    ) -> None:
        message = MessageSchema(
            subject=subject,
            recipients=[NameEmail(email=to, name="")],
            template_body=context,
            subtype=MessageType.html,
        )
        await self._mail_client.send_message(message, template_name=template_name)


def get_mail_service() -> MailService:
    return MailService(FM)
