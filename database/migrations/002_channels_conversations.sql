CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'disconnected',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_channels_organization_id ON channels(organization_id);
CREATE INDEX ix_channels_type ON channels(type);
CREATE INDEX ix_channels_status ON channels(organization_id, status);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    external_conversation_id VARCHAR(255),
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_conversations_organization_id ON conversations(organization_id);
CREATE INDEX ix_conversations_customer_id ON conversations(customer_id);
CREATE INDEX ix_conversations_channel_id ON conversations(channel_id);
CREATE INDEX ix_conversations_status ON conversations(organization_id, status);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    external_message_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_messages_conversation_id ON messages(conversation_id, created_at);
