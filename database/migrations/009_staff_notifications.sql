ALTER TABLE users
    ADD COLUMN telegram_chat_id TEXT,
    ADD COLUMN telegram_channel_id UUID REFERENCES channels(id) ON DELETE SET NULL,
    ADD COLUMN telegram_link_code TEXT,
    ADD COLUMN telegram_link_expires_at TIMESTAMPTZ,
    ADD COLUMN notify_language TEXT NOT NULL DEFAULT 'en';

CREATE UNIQUE INDEX uq_users_telegram_link_code ON users (telegram_link_code) WHERE telegram_link_code IS NOT NULL;

CREATE TABLE ticket_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ticket_notification UNIQUE (ticket_id, user_id, kind)
);
CREATE INDEX ix_ticket_notifications_user ON ticket_notifications(user_id);
