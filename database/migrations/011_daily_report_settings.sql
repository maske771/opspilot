ALTER TABLE organizations
    ADD COLUMN daily_report_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN daily_report_time TEXT NOT NULL DEFAULT '08:00',
    ADD COLUMN daily_report_timezone TEXT NOT NULL DEFAULT 'Asia/Bangkok',
    ADD COLUMN daily_report_last_sent_date DATE;
