ALTER TABLE tickets ADD COLUMN closed_at TIMESTAMPTZ;
CREATE INDEX ix_tickets_closed_at ON tickets(organization_id, closed_at);
