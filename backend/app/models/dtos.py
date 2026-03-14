from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Event(BaseModel):
    id: str
    source_id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool = False
    description: str | None = None
    recurrence: str | None = None
    location: str | None = None
    url: str | None = None
    alert_minutes_before: list[int] | None = None
    cancelled: bool = False


class Todo(BaseModel):
    id: str
    source_id: str
    summary: str
    completed: bool = False
    due: datetime | None = None
    description: str | None = None
    priority: int | None = None
    recurrence: str | None = None
    categories: list[str] | None = None
    alert_minutes_before: list[int] | None = None


SourceType = Literal["ics_url", "local_folder", "caldav"]


class Source(BaseModel):
    id: str
    type: SourceType
    name: str
    enabled: bool = True
    color: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class SourceCreate(BaseModel):
    type: SourceType
    name: str
    enabled: bool = True
    color: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class SourceUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    color: str | None = None
    config: dict[str, Any] | None = None


class EventCreate(BaseModel):
    source_id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool = False
    description: str | None = None
    location: str | None = None
    recurrence: str | None = None
    url: str | None = None
    alert_minutes_before: list[int] | None = None


class EventUpdate(BaseModel):
    title: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool | None = None
    description: str | None = None
    location: str | None = None
    recurrence: str | None = None
    url: str | None = None
    alert_minutes_before: list[int] | None = None


class TodoCreate(BaseModel):
    source_id: str
    summary: str
    completed: bool = False
    due: datetime | None = None
    description: str | None = None
    priority: int | None = None
    recurrence: str | None = None
    categories: list[str] | None = None
    alert_minutes_before: list[int] | None = None


class TodoUpdate(BaseModel):
    summary: str | None = None
    completed: bool | None = None
    due: datetime | None = None
    description: str | None = None
    priority: int | None = None
    recurrence: str | None = None
    categories: list[str] | None = None
    alert_minutes_before: list[int] | None = None


NotificationTarget = Literal["notify_send", "webhook", "email"]
NotifySendTimeout = Literal["5s", "15s", "60s", "persistent"]
AutoSyncInterval = Literal["off", "30s", "1m", "5m"]
TimeDisplayFormat = Literal["24h", "12h"]


class WebhookSettings(BaseModel):
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class EmailSettings(BaseModel):
    to: str | None = None


class NotificationSettings(BaseModel):
    enabled: bool = False
    target: NotificationTarget = "notify_send"
    notify_send_timeout: NotifySendTimeout = "15s"
    webhook: WebhookSettings = Field(default_factory=WebhookSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    time_format: str = "%b %d %H:%M %Z"
    body_template: str = "{time}"


class NotificationSettingsUpdate(BaseModel):
    enabled: bool | None = None
    target: NotificationTarget | None = None
    notify_send_timeout: NotifySendTimeout | None = None
    webhook: WebhookSettings | None = None
    email: EmailSettings | None = None
    time_format: str | None = None
    body_template: str | None = None


class UiSettings(BaseModel):
    auto_sync_interval: AutoSyncInterval = "off"
    time_display_format: TimeDisplayFormat = "24h"


class UiSettingsUpdate(BaseModel):
    auto_sync_interval: AutoSyncInterval | None = None
    time_display_format: TimeDisplayFormat | None = None
