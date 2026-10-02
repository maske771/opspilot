CREATE TABLE property_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    sla JSONB,
    CONSTRAINT uq_property_services UNIQUE (property_id, service_id)
);
CREATE INDEX ix_property_services_property_id ON property_services(property_id);
