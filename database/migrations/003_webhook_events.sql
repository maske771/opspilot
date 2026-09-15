CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    external_event_id VARCHAR(255),
    payload JSONB NOT NULL,
    signature_valid BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_webhook_external_event UNIQUE (organization_id, provider, account_id, external_event_id)
);
CREATE INDEX ix_webhook_events_org_created ON webhook_events(organization_id, created_at);
CREATE INDEX ix_webhook_events_channel ON webhook_events(channel_id);
