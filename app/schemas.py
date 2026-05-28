from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ImportCreateResponse(BaseModel):
    import_id: int
    status: str
    message: str


class ImportRead(BaseModel):
    id: int
    status: str
    total_rows: int
    valid_emails: int
    invalid_emails: int
    duplicates: int
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RecipientRead(BaseModel):
    id: int
    name: str | None = None
    email: EmailStr
    group: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MailingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    recipients: list[EmailStr] | None = None
    group: str | None = None

    @model_validator(mode="after")
    def require_recipients_or_group(self) -> "MailingCreate":
        if not self.recipients and not self.group:
            raise ValueError("Укажите recipients или group")
        return self


class MailingListItem(BaseModel):
    id: int
    title: str
    subject: str
    total_recipients: int
    sent_count: int
    failed_count: int
    status: str


class MailingRead(MailingListItem):
    body: str
    queued_count: int
    sending_count: int


class EmailTaskRead(BaseModel):
    id: int
    recipient: str
    status: str
    error: str | None = None


class MailingCreateResponse(BaseModel):
    mailing_id: int
    status: str
    total_recipients: int
    message: str


class EventRead(BaseModel):
    id: str
    event: str
    created_at: datetime | None = None
    data: dict[str, str]
