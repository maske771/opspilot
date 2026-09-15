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
    telegram_configs:
      - bot_token: '${ALERTMANAGER_TELEGRAM_BOT_TOKEN}'
        chat_id: ${ALERTMANAGER_TELEGRAM_CHAT_ID:-0}
        send_resolved: true

  - name: opspilot-critical
    email_configs:
      - to: '${ALERTMANAGER_EMAIL_TO}'
        send_resolved: true
        headers:
          Subject: '[OpsPilot][CRITICAL] {{ .CommonLabels.alertname }}'
    telegram_configs:
      - bot_token: '${ALERTMANAGER_TELEGRAM_BOT_TOKEN}'
        chat_id: ${ALERTMANAGER_TELEGRAM_CHAT_ID:-0}
        send_resolved: true
