-- Who changed what: ticket history and sensitive admin actions (roles, channels, codes, SLA).
-- Written in the same transaction as the change it describes.
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_events_entity ON audit_events(organization_id, entity_type, entity_id, created_at);
CREATE INDEX ix_audit_events_org_created ON audit_events(organization_id, created_at DESC);
