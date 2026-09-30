import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Channel, Ticket, User
from .outbound import send_message
from .roles import MANAGER_ROLES

SUPPORTED_LANGUAGES = ("en", "ru", "th")

SENT = "sent"
SKIPPED = "skipped"  # the recipient has no Telegram linked, so there is nowhere to send it
FAILED = "failed"

PRIORITY_NAMES = {
    "en": {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"},
    "ru": {"critical": "Критичный", "high": "Высокий", "medium": "Средний", "low": "Низкий"},
    "th": {"critical": "วิกฤต", "high": "สูง", "medium": "ปานกลาง", "low": "ต่ำ"},
}

NOBODY = {"en": "nobody assigned", "ru": "не назначен", "th": "ยังไม่มอบหมาย"}

MESSAGES: dict[str, dict[str, str]] = {
    "assigned": {
        "en": "New ticket assigned to you: {title}\nPriority: {priority}. Please respond within {minutes} min.\n{url}",
        "ru": "Вам назначена новая заявка: {title}\nПриоритет: {priority}. Ответьте в течение {minutes} мин.\n{url}",
        "th": "มีงานใหม่มอบหมายให้คุณ: {title}\nความสำคัญ: {priority} กรุณาตอบกลับภายใน {minutes} นาที\n{url}",
    },
    "response_soon": {
        "en": "Response due soon ({minutes} min left): {title}\n{url}",
        "ru": "Скоро истекает срок ответа (осталось {minutes} мин): {title}\n{url}",
        "th": "ใกล้ครบกำหนดตอบกลับ (เหลือ {minutes} นาที): {title}\n{url}",
    },
    "response_overdue": {
        "en": "Response overdue by {minutes} min: {title}\n{url}",
        "ru": "Срок ответа просрочен на {minutes} мин: {title}\n{url}",
        "th": "เกินกำหนดตอบกลับแล้ว {minutes} นาที: {title}\n{url}",
    },
    "resolution_soon": {
        "en": "Resolution due soon ({minutes} min left): {title}\n{url}",
        "ru": "Скоро истекает срок решения (осталось {minutes} мин): {title}\n{url}",
        "th": "ใกล้ครบกำหนดแก้ไขงาน (เหลือ {minutes} นาที): {title}\n{url}",
    },
    "resolution_overdue": {
        "en": "Resolution overdue by {minutes} min: {title}\n{url}",
        "ru": "Срок решения просрочен на {minutes} мин: {title}\n{url}",
        "th": "เกินกำหนดแก้ไขงานแล้ว {minutes} นาที: {title}\n{url}",
    },
    "escalation_response": {
        "en": "Escalation: response overdue by {minutes} min. Assignee: {assignee}. {title}\n{url}",
        "ru": "Эскалация: срок ответа просрочен на {minutes} мин. Исполнитель: {assignee}. {title}\n{url}",
        "th": "แจ้งเตือนผู้จัดการ: เกินกำหนดตอบกลับ {minutes} นาที ผู้รับผิดชอบ: {assignee} {title}\n{url}",
    },
    "escalation_resolution": {
        "en": "Escalation: resolution overdue by {minutes} min. Assignee: {assignee}. {title}\n{url}",
        "ru": "Эскалация: срок решения просрочен на {minutes} мин. Исполнитель: {assignee}. {title}\n{url}",
        "th": "แจ้งเตือนผู้จัดการ: เกินกำหนดแก้ไขงาน {minutes} นาที ผู้รับผิดชอบ: {assignee} {title}\n{url}",
    },
    "approval_needed": {
        "en": "Ready to close, needs your approval ({priority}): {title}\n{url}",
        "ru": "Готово к закрытию, нужно ваше подтверждение ({priority}): {title}\n{url}",
        "th": "พร้อมปิดงาน ต้องรออนุมัติจากคุณ ({priority}): {title}\n{url}",
    },
    "daily_report": {
        "en": "📊 Daily report for {date}\nCreated: {created} | Closed: {closed}\nRight now: open {open}, overdue {overdue}, awaiting approval {waiting}\nOpen high/critical: {critical}\n{url}",
        "ru": "📊 Ежедневная сводка за {date}\nСоздано: {created} | Закрыто: {closed}\nПрямо сейчас: открыто {open}, просрочено {overdue}, ждёт подтверждения {waiting}\nОткрытых high/critical: {critical}\n{url}",
        "th": "📊 สรุปประจำวันที่ {date}\nสร้างใหม่: {created} | ปิดแล้ว: {closed}\nตอนนี้: เปิดอยู่ {open} เกินกำหนด {overdue} รออนุมัติ {waiting}\nงานความสำคัญสูง/วิกฤตที่เปิดอยู่: {critical}\n{url}",
    },
    "link_ok": {
        "en": "Telegram is now linked to {email}. You will get notifications about your tickets here. Open tickets assigned to you: {count}.",
        "ru": "Telegram привязан к {email}. Здесь вы будете получать уведомления о ваших заявках. Открытых заявок на вас: {count}.",
        "th": "เชื่อมต่อ Telegram กับ {email} แล้ว คุณจะได้รับการแจ้งเตือนเกี่ยวกับงานที่นี่ งานที่ยังเปิดอยู่ของคุณ: {count}",
    },
    "link_bad": {
        "en": "This code is invalid or has expired. Generate a new one in your OpsPilot profile.",
        "ru": "Код недействителен или истёк. Создайте новый в профиле OpsPilot.",
        "th": "รหัสไม่ถูกต้องหรือหมดอายุแล้ว กรุณาสร้างรหัสใหม่ในโปรไฟล์ OpsPilot",
    },
}


def normalize_language(code: str | None) -> str:
    prefix = (code or "").lower()[:2]
    return prefix if prefix in SUPPORTED_LANGUAGES else "en"


def render(kind: str, language: str | None, **values: object) -> str:
    return MESSAGES[kind][normalize_language(language)].format(**values).strip()


def ticket_url(ticket: Ticket) -> str:
    base = os.getenv("PUBLIC_WEB_URL", "").rstrip("/")
    return f"{base}/tickets/{ticket.id}" if base else ""


def ticket_message(kind: str, ticket: Ticket, language: str | None, minutes: int, assignee: User | None = None) -> str:
    lang = normalize_language(language)
    assignee_name = assignee.email.split("@")[0] if assignee is not None else NOBODY[lang]
    return render(
        kind,
        lang,
        title=ticket.title,
        priority=PRIORITY_NAMES[lang][ticket.priority.value],
        minutes=max(1, minutes),
        url=ticket_url(ticket),
        assignee=assignee_name,
    )


def notify_managers_approval_needed(db: Session, ticket: Ticket) -> None:
    """A high/critical ticket just reached waiting_approval: tell every manager once, right now
    (not through the polling SLA monitor — this is an event, not a deadline)."""
    managers = db.scalars(
        select(User).where(User.organization_id == ticket.organization_id, User.role.in_(MANAGER_ROLES))
    )
    for manager in managers:
        text = ticket_message("approval_needed", ticket, manager.notify_language, 0)
        send_to_user(db, manager, text)


def send_to_user(db: Session, user: User, text: str) -> str:
    """Send `text` to the user's linked Telegram chat. Returns SENT, SKIPPED (not linked) or FAILED."""
    if not user.telegram_linked:
        return SKIPPED
    channel = db.get(Channel, user.telegram_channel_id)
    if channel is None or channel.type != "telegram" or channel.status != "connected":
        return SKIPPED
    return SENT if send_message(channel, user.telegram_chat_id, text) else FAILED
