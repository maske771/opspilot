CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('owner', 'admin', 'manager', 'staff', 'technician');
CREATE TYPE ticket_priority AS ENUM ('critical', 'high', 'medium', 'low');
CREATE TYPE ticket_status AS ENUM ('new', 'assigned', 'accepted', 'in_progress', 'completed', 'waiting_approval', 'closed');

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'staff',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_org_email UNIQUE (organization_id, email)
);
CREATE INDEX ix_users_organization_id ON users(organization_id);

CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_properties_organization_id ON properties(organization_id);

CREATE TABLE units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    unit_number VARCHAR(100) NOT NULL
);
CREATE INDEX ix_units_organization_id ON units(organization_id);
CREATE INDEX ix_units_property_id ON units(property_id);

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(320),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_customers_organization_id ON customers(organization_id);

CREATE TABLE customer_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel_type VARCHAR(50) NOT NULL,
    external_user_id VARCHAR(255) NOT NULL,
    CONSTRAINT uq_customer_identity UNIQUE (organization_id, channel_type, external_user_id)
);
CREATE INDEX ix_customer_identities_organization_id ON customer_identities(organization_id);
CREATE INDEX ix_customer_identities_customer_id ON customer_identities(customer_id);

CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    property_id UUID REFERENCES properties(id) ON DELETE SET NULL,
    unit_id UUID REFERENCES units(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'other',
    priority ticket_priority NOT NULL DEFAULT 'medium',
    status ticket_status NOT NULL DEFAULT 'new',
    assignee_id UUID REFERENCES users(id) ON DELETE SET NULL,
    response_deadline TIMESTAMPTZ,
    resolution_deadline TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_tickets_organization_id ON tickets(organization_id);
CREATE INDEX ix_tickets_customer_id ON tickets(customer_id);
CREATE INDEX ix_tickets_property_id ON tickets(property_id);
CREATE INDEX ix_tickets_unit_id ON tickets(unit_id);
CREATE INDEX ix_tickets_status ON tickets(organization_id, status);
CREATE INDEX ix_tickets_sla ON tickets(organization_id, resolution_deadline);
