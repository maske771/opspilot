#!/bin/sh

sed \
  -e "s|\${ALERTMANAGER_SMTP_SMARTHOST}|${ALERTMANAGER_SMTP_SMARTHOST:-smtp.example.com:587}|g" \
  -e "s|\${ALERTMANAGER_SMTP_FROM}|${ALERTMANAGER_SMTP_FROM:-opspilot@example.com}|g" \
  -e "s|\${ALERTMANAGER_SMTP_USERNAME}|${ALERTMANAGER_SMTP_USERNAME:-opspilot@example.com}|g" \
  -e "s|\${ALERTMANAGER_SMTP_PASSWORD}|${ALERTMANAGER_SMTP_PASSWORD:-change-me}|g" \
  -e "s|\${ALERTMANAGER_EMAIL_TO}|${ALERTMANAGER_EMAIL_TO:-ops@example.com}|g" \
  -e "s|\${ALERTMANAGER_TELEGRAM_BOT_TOKEN}|${ALERTMANAGER_TELEGRAM_BOT_TOKEN:-replace-me}|g" \
  -e "s|\${ALERTMANAGER_TELEGRAM_CHAT_ID:-0}|${ALERTMANAGER_TELEGRAM_CHAT_ID:-0}|g" \
  /etc/alertmanager/alertmanager.yml.tpl > /tmp/alertmanager.yml

exec /bin/alertmanager --config.file=/tmp/alertmanager.yml --storage.path=/alertmanager
