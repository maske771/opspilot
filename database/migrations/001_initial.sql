CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner','admin','manager','staff','technician')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, email)
);
CREATE INDEX users_org_idx ON users(organization_id);

CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX properties_org_idx ON properties(organization_id);

CREATE TABLE units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    property_id UUID NOT NULL REFERENCES properties(id),
    name TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX units_property_idx ON units(property_id);

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name TEXT,
    email TEXT,
    phone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX customers_org_idx ON customers(organization_id);

CREATE TABLE customer_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    channel_type TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (organization_id, channel_type, external_user_id)
);
CREATE INDEX customer_identity_customer_idx ON customer_identities(customer_id);

CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    channel_type TEXT NOT NULL CHECK (channel_type IN ('line','whatsapp','telegram','email')),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'disconnected' CHECK (status IN ('connected','disconnected','error')),
    secret_ref TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX channels_org_idx ON channels(organization_id);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    customer_id UUID REFERENCES customers(id),
    channel_id UUID NOT NULL REFERENCES channels(id),
    external_conversation_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (channel_id, external_conversation_key)
);
CREATE INDEX conversations_org_idx ON conversations(organization_id);

CREATE TABLE inbound_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    channel_id UUID NOT NULL REFERENCES channels(id),
    external_event_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (channel_id, external_event_id)
);

CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    customer_id UUID REFERENCES customers(id),
    property_id UUID REFERENCES properties(id),
    unit_id UUID REFERENCES units(id),
    conversation_id UUID REFERENCES conversations(id),
    category TEXT NOT NULL DEFAULT 'other',
    priority TEXT NOT NULL CHECK (priority IN ('critical','high','medium','low')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','assigned','accepted','in_progress','completed','pending_approval','closed')),
    assignee_id UUID REFERENCES users(id),
    summary TEXT NOT NULL,
    response_due_at TIMESTAMPTZ,
    resolution_due_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ
);
CREATE INDEX tickets_org_status_idx ON tickets(organization_id, status);
CREATE INDEX tickets_org_priority_idx ON tickets(organization_id, priority);
CREATE INDEX tickets_assignee_idx ON tickets(assignee_id);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    direction TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
    sender_external_id TEXT,
    text TEXT,
    external_message_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messages_conversation_idx ON messages(conversation_id, created_at);

CREATE TABLE sla_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    priority TEXT NOT NULL CHECK (priority IN ('critical','high','medium','low')),
    response_minutes INTEGER NOT NULL CHECK (response_minutes > 0),
    resolution_minutes INTEGER NOT NULL CHECK (resolution_minutes > 0),
    UNIQUE (organization_id, priority)
);

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    actor_user_id UUID REFERENCES users(id),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    action TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_org_entity_idx ON audit_events(organization_id, entity_type, entity_id);

CREATE TABLE ai_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    agent_type TEXT NOT NULL,
    model_identifier TEXT,
    input_hash TEXT NOT NULL,
    output JSONB NOT NULL,
    confidence NUMERIC(5,4),
    token_count INTEGER,
    cost_minor_units NUMERIC(14,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ai_events_org_time_idx ON ai_events(organization_id, created_at);
