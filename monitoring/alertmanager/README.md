# Alertmanager notifications

Set these variables in `.env` before starting the monitoring stack:

```env
ALERTMANAGER_SMTP_SMARTHOST=smtp.example.com:587
ALERTMANAGER_SMTP_FROM=opspilot@example.com
ALERTMANAGER_SMTP_USERNAME=opspilot@example.com
ALERTMANAGER_SMTP_PASSWORD=change-me
ALERTMANAGER_EMAIL_TO=ops@example.com
ALERTMANAGER_TELEGRAM_BOT_TOKEN=123456:replace-me
ALERTMANAGER_TELEGRAM_CHAT_ID=-1001234567890
```

The repository intentionally contains no real credentials.
