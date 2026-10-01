ALTER TABLE organizations
    ADD COLUMN daily_report_skip_weekends BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN daily_report_excluded_dates DATE[] NOT NULL DEFAULT '{}',
    ADD COLUMN daily_report_template JSONB;
