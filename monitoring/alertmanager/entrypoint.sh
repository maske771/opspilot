#!/bin/sh

: "${ALERTMANAGER_SMTP_SMARTHOST:=smtp.example.com:587}"
: "${ALERTMANAGER_SMTP_FROM:=opspilot@example.com}"
: "${ALERTMANAGER_SMTP_USERNAME:=opspilot@example.com}"
: "${ALERTMANAGER_SMTP_PASSWORD:=change-me}"
: "${ALERTMANAGER_EMAIL_TO:=ops@example.com}"
: "${ALERTMANAGER_TELEGRAM_BOT_TOKEN:=replace-me}"
: "${ALERTMANAGER_TELEGRAM_CHAT_ID:=0}"

cat > /tmp/alertmanager.yml <<EOF
global:
  resolve_timeout: 5m
  smtp_smarthost: '${ALERTMANAGER_SMTP_SMARTHOST}'
  smtp_from: '${ALERTMANAGER_SMTP_FROM}'
  smtp_auth_username: '${ALERTMANAGER_SMTP_USERNAME}'
  smtp_auth_password: '${ALERTMANAGER_SMTP_PASSWORD}'
  smtp_require_tls: true

route:
  receiver: opspilot-default
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - receiver: opspilot-critical
      matchers:
        - severity="critical"

receivers:
  - name: opspilot-default
    email_configs:
      - to: '${ALERTMANAGER_EMAIL_TO}'
        send_resolved: true
EOF

if [ "${ALERTMANAGER_TELEGRAM_CHAT_ID}" != "0" ] && [ -n "${ALERTMANAGER_TELEGRAM_BOT_TOKEN}" ] && [ "${ALERTMANAGER_TELEGRAM_BOT_TOKEN}" != "replace-me" ]; then
  cat >> /tmp/alertmanager.yml <<EOF
    telegram_configs:
      - bot_token: '${ALERTMANAGER_TELEGRAM_BOT_TOKEN}'
        chat_id: ${ALERTMANAGER_TELEGRAM_CHAT_ID}
        send_resolved: true
EOF
fi

cat >> /tmp/alertmanager.yml <<EOF

  - name: opspilot-critical
    email_configs:
      - to: '${ALERTMANAGER_EMAIL_TO}'
        send_resolved: true
        headers:
          Subject: '[OpsPilot][CRITICAL] {{ .CommonLabels.alertname }}'
EOF

if [ "${ALERTMANAGER_TELEGRAM_CHAT_ID}" != "0" ] && [ -n "${ALERTMANAGER_TELEGRAM_BOT_TOKEN}" ] && [ "${ALERTMANAGER_TELEGRAM_BOT_TOKEN}" != "replace-me" ]; then
  cat >> /tmp/alertmanager.yml <<EOF
    telegram_configs:
      - bot_token: '${ALERTMANAGER_TELEGRAM_BOT_TOKEN}'
        chat_id: ${ALERTMANAGER_TELEGRAM_CHAT_ID}
        send_resolved: true
EOF
fi

exec /bin/alertmanager --config.file=/tmp/alertmanager.yml --storage.path=/alertmanager
