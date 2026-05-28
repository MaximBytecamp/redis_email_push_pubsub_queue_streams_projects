from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import EMAIL_STATUS_QUEUED, IMPORT_STATUS_QUEUED, MAILING_STATUS_CREATED
from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)


class RecipientImport(Base, TimestampMixin):
    __tablename__ = "recipient_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default=IMPORT_STATUS_QUEUED, index=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_emails: Mapped[int] = mapped_column(Integer, default=0)
    invalid_emails: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recipient(Base, TimestampMixin):
    __tablename__ = "recipients"
    __table_args__ = (UniqueConstraint("email", name="uq_recipients_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    group: Mapped[str | None] = mapped_column("group", String(120), nullable=True, quote=True)


class Mailing(Base, TimestampMixin):
    __tablename__ = "mailings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=MAILING_STATUS_CREATED, index=True)

    email_tasks: Mapped[list["EmailTask"]] = relationship(
        back_populates="mailing", cascade="all, delete-orphan"
    )


class EmailTask(Base, TimestampMixin):
    __tablename__ = "email_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mailing_id: Mapped[int] = mapped_column(ForeignKey("mailings.id"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(320), index=True)
    status: Mapped[str] = mapped_column(String(30), default=EMAIL_STATUS_QUEUED, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    mailing: Mapped[Mailing] = relationship(back_populates="email_tasks")
