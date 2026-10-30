# ruff: noqa: RUF001 -- reply headers are written in Chinese.
"""E-mail files: .eml (any mail program) and Outlook .msg read, with their attachments; drafts
written as .eml that Outlook opens as an unsent message (X-Unsent); calendar invitations as
.ics. Nothing is sent from here."""

from __future__ import annotations

import html
import re
import struct
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

from agent_workspace.office.ooxml import OfficeError

MAX_BODY = 60_000


@dataclass
class Attachment:
    name: str
    content_type: str
    data: bytes


@dataclass
class Mail:
    subject: str = ""
    sender: str = ""
    to: str = ""
    cc: str = ""
    date: str = ""
    message_id: str = ""
    references: str = ""
    body: str = ""
    attachments: list[Attachment] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "from": self.sender,
            "to": self.to,
            "cc": self.cc,
            "date": self.date,
            "message_id": self.message_id,
            "body": self.body[:MAX_BODY],
            "body_truncated": len(self.body) > MAX_BODY,
            "attachments": [
                {"name": item.name, "type": item.content_type, "bytes": len(item.data)}
                for item in self.attachments
            ],
        }


def html_text(source: str) -> str:
    text = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", "", source)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</h\d>", "\n", text)
    text = re.sub(r"(?i)<li\b[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def read_eml(data: bytes) -> Mail:
    message = BytesParser(policy=policy.default).parsebytes(data)
    mail = Mail(
        subject=str(message.get("Subject", "")),
        sender=str(message.get("From", "")),
        to=str(message.get("To", "")),
        cc=str(message.get("Cc", "")),
        message_id=str(message.get("Message-ID", "")),
        references=str(message.get("References", "")),
    )
    if message.get("Date"):
        try:
            mail.date = (
                parsedate_to_datetime(str(message["Date"])).astimezone().strftime("%Y-%m-%d %H:%M")
            )
        except (TypeError, ValueError):
            mail.date = str(message["Date"])
    body = (
        message.get_body(preferencelist=("plain", "html"))
        if isinstance(message, EmailMessage)
        else None
    )
    if body is not None:
        content = body.get_content()
        mail.body = (
            html_text(content) if body.get_content_type() == "text/html" else str(content).strip()
        )
    if isinstance(message, EmailMessage):
        for part in message.iter_attachments():
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                mail.attachments.append(
                    Attachment(
                        part.get_filename() or "attachment", part.get_content_type(), payload
                    )
                )
    return mail


# ---- Outlook .msg (a Compound File) --------------------------------------------------------------

_FREE, _END = 0xFFFFFFFF, 0xFFFFFFFE


class _Compound:
    def __init__(self, data: bytes) -> None:
        if data[:8] != bytes.fromhex("D0CF11E0A1B11AE1"):
            raise OfficeError("not an Outlook message (.msg)")
        self.data = data
        self.sector_size = 1 << struct.unpack_from("<H", data, 30)[0]
        self.mini_size = 1 << struct.unpack_from("<H", data, 32)[0]
        fat_count, directory_start = struct.unpack_from("<II", data, 44)
        self.cutoff = struct.unpack_from("<I", data, 56)[0]
        mini_fat_start, mini_fat_count, difat_start, difat_count = struct.unpack_from(
            "<IIII", data, 60
        )
        difat = list(struct.unpack_from("<109I", data, 76))
        sector = difat_start
        for _ in range(difat_count):
            if sector in (_FREE, _END):
                break
            values = struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(sector))
            difat.extend(values[:-1])
            sector = values[-1]
        self.fat: list[int] = []
        for sector in difat[:fat_count]:
            if sector in (_FREE, _END):
                continue
            self.fat.extend(struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(sector)))
        self.mini_fat: list[int] = []
        if mini_fat_count:
            chain = self._chain(mini_fat_start)
            self.mini_fat = list(struct.unpack(f"<{len(chain) // 4}I", chain))
        directory = self._chain(directory_start)
        self.entries = []
        for offset in range(0, len(directory), 128):
            entry = directory[offset : offset + 128]
            length = struct.unpack_from("<H", entry, 64)[0]
            name = entry[: max(0, length - 2)].decode("utf-16-le", errors="replace")
            kind = entry[66]
            left, right, child = struct.unpack_from("<III", entry, 68)
            start, size = struct.unpack_from("<II", entry, 116)
            self.entries.append(
                {
                    "name": name,
                    "type": kind,
                    "left": left,
                    "right": right,
                    "child": child,
                    "start": start,
                    "size": size,
                }
            )
        root = self.entries[0]
        self.mini_stream = self._chain(root["start"])[: root["size"]]

    def _sector(self, number: int) -> bytes:
        offset = (number + 1) * self.sector_size
        return self.data[offset : offset + self.sector_size]

    def _chain(self, start: int) -> bytes:
        out = bytearray()
        sector, seen = start, 0
        while sector not in (_FREE, _END) and sector < len(self.fat) and seen <= len(self.fat):
            out += self._sector(sector)
            sector = self.fat[sector]
            seen += 1
        return bytes(out)

    def read(self, index: int) -> bytes:
        entry = self.entries[index]
        if entry["size"] < self.cutoff:
            out = bytearray()
            sector, seen = entry["start"], 0
            while (
                sector not in (_FREE, _END)
                and sector < len(self.mini_fat)
                and seen <= len(self.mini_fat)
            ):
                out += self.mini_stream[sector * self.mini_size : (sector + 1) * self.mini_size]
                sector = self.mini_fat[sector]
                seen += 1
            return bytes(out[: entry["size"]])
        return self._chain(entry["start"])[: entry["size"]]

    def children(self, index: int) -> dict[str, int]:
        """Names of a storage's direct children and their entry numbers."""
        out: dict[str, int] = {}
        stack = [self.entries[index]["child"]]
        while stack:
            current = stack.pop()
            if current in (_FREE, _END) or current >= len(self.entries):
                continue
            entry = self.entries[current]
            out[entry["name"]] = current
            stack.extend([entry["left"], entry["right"]])
        return out


def _property(compound: _Compound, items: dict[str, int], property_id: str) -> str:
    for suffix, encoding in (("001F", "utf-16-le"), ("001E", "gb18030")):
        key = f"__substg1.0_{property_id}{suffix}"
        if key in items:
            return compound.read(items[key]).decode(encoding, errors="replace").rstrip("\x00")
    return ""


def _filetime(compound: _Compound, items: dict[str, int], wanted: int) -> str:
    name = "__properties_version1.0"
    if name not in items:
        return ""
    data = compound.read(items[name])
    for offset in range(32, len(data) - 15, 16):
        tag = struct.unpack_from("<I", data, offset)[0]
        if tag >> 16 == wanted and tag & 0xFFFF == 0x0040:
            value = struct.unpack_from("<Q", data, offset + 8)[0]
            moment = datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=value // 10)
            return moment.astimezone().strftime("%Y-%m-%d %H:%M")
    return ""


def read_msg(data: bytes) -> Mail:
    compound = _Compound(data)
    items = compound.children(0)
    mail = Mail(
        subject=_property(compound, items, "0037"),
        sender=" ".join(
            part
            for part in (
                _property(compound, items, "0C1A"),
                f"<{_property(compound, items, '0C1F')}>",
            )
            if part and part != "<>"
        ),
        to=_property(compound, items, "0E04"),
        cc=_property(compound, items, "0E03"),
        message_id=_property(compound, items, "1035"),
    )
    mail.date = _filetime(compound, items, 0x0039) or _filetime(compound, items, 0x0E06)
    body = _property(compound, items, "1000")
    if not body and "__substg1.0_10130102" in items:
        body = html_text(
            compound.read(items["__substg1.0_10130102"]).decode("utf-8", errors="replace")
        )
    mail.body = body.strip()
    for name, index in items.items():
        if not name.startswith("__attach_version1.0_"):
            continue
        attachment = compound.children(index)
        filename = (
            _property(compound, attachment, "3707")
            or _property(compound, attachment, "3704")
            or "attachment"
        )
        content = (
            compound.read(attachment["__substg1.0_37010102"])
            if "__substg1.0_37010102" in attachment
            else b""
        )
        mail.attachments.append(
            Attachment(
                filename,
                _property(compound, attachment, "370E") or "application/octet-stream",
                content,
            )
        )
    return mail


def read_mail(path: Path) -> Mail:
    data = path.read_bytes()
    if path.suffix.lower() == ".msg":
        return read_msg(data)
    if path.suffix.lower() == ".eml":
        return read_eml(data)
    raise OfficeError("e-mail is read from .eml and .msg files")


# ---- writing -----------------------------------------------------------------------------------


def draft(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    reply_to: Mail | None = None,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """An unsent message: double-clicked, Outlook opens it ready to edit and send."""
    message = EmailMessage(policy=policy.SMTP)
    message["X-Unsent"] = "1"
    if to:
        message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    subject_text = subject
    if reply_to is not None:
        if not subject_text:
            subject_text = (
                reply_to.subject
                if reply_to.subject.lower().startswith(("re:", "回复"))
                else f"Re: {reply_to.subject}"
            )
        if reply_to.message_id:
            message["In-Reply-To"] = reply_to.message_id
            message["References"] = f"{reply_to.references} {reply_to.message_id}".strip()
    message["Subject"] = subject_text
    quoted = ""
    if reply_to is not None and reply_to.body:
        lines = "\n".join("> " + line for line in reply_to.body[:20_000].splitlines())
        quoted = f"\n\n{reply_to.date} {reply_to.sender} 写道：\n{lines}"
    message.set_content(body + quoted)
    for name, data in attachments or []:
        message.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return message.as_bytes()


def addresses(values: list[str] | str | None) -> list[str]:
    if not values:
        return []
    items = values if isinstance(values, list) else [values]
    out = []
    for name, address in getaddresses([str(item) for item in items]):
        if address and "@" in address:
            out.append(f"{name} <{address}>" if name else address)
        elif name or address:
            raise OfficeError(f"{name or address} is not an e-mail address")
    return out


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    out: list[str] = []
    current = b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > (75 if not out else 74):
            out.append(current.decode("utf-8"))
            current = b""
        current += encoded
    out.append(current.decode("utf-8"))
    return "\r\n ".join(out)


def parse_time(text: str) -> datetime:
    """A local time written "2026-11-05 14:30" (or with T, seconds, /)."""
    cleaned = text.strip().replace("/", "-").replace("T", " ")
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, pattern)
        except ValueError:
            continue
    raise OfficeError(f"cannot read the time {text!r}; write it like 2026-11-05 14:30")


def invitation(
    title: str,
    start: str,
    end: str | None = None,
    minutes: int = 60,
    location: str = "",
    description: str = "",
    attendees: list[str] | None = None,
    organizer: str = "",
    reminder: int = 15,
) -> bytes:
    """A calendar invitation (.ics); the times are this computer's local time."""
    begin = parse_time(start).astimezone()
    finish = parse_time(end).astimezone() if end else begin + timedelta(minutes=minutes)
    if finish <= begin:
        raise OfficeError("the meeting ends before it starts")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    def utc(moment: datetime) -> str:
        return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Agent Workspace//Office//ZH",
        "CALSCALE:GREGORIAN",
        f"METHOD:{'REQUEST' if attendees else 'PUBLISH'}",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@agent-workspace",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{utc(begin)}",
        f"DTEND:{utc(finish)}",
        f"SUMMARY:{_ics_text(title)}",
    ]
    if location:
        lines.append(f"LOCATION:{_ics_text(location)}")
    if description:
        lines.append(f"DESCRIPTION:{_ics_text(description)}")
    if organizer:
        for _name, address in getaddresses([organizer]):
            if address:
                lines.append(f"ORGANIZER:mailto:{address}")
    for item in addresses(attendees or []):
        address = getaddresses([item])[0][1]
        lines.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{address}")
    if reminder > 0:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_ics_text(title)}",
            f"TRIGGER:-PT{int(reminder)}M",
            "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")


__all__ = [
    "Attachment",
    "Mail",
    "addresses",
    "draft",
    "html_text",
    "invitation",
    "parse_time",
    "read_eml",
    "read_mail",
    "read_msg",
]
