ALTER TABLE channels ADD COLUMN account_id VARCHAR(255);
UPDATE channels SET account_id = name WHERE account_id IS NULL;
ALTER TABLE channels ALTER COLUMN account_id SET NOT NULL;
CREATE UNIQUE INDEX uq_channels_org_type_account_connected
    ON channels(organization_id, type, account_id)
    WHERE status = 'connected';
CREATE INDEX ix_channels_account_id ON channels(account_id);

ALTER TABLE tickets ADD COLUMN conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL;
CREATE INDEX ix_tickets_conversation_id ON tickets(conversation_id);
CREATE UNIQUE INDEX uq_messages_conversation_external_id
    ON messages(conversation_id, external_message_id)
    WHERE external_message_id IS NOT NULL;
CREATE UNIQUE INDEX uq_conversations_channel_external_id
    ON conversations(organization_id, channel_id, external_conversation_id)
    WHERE external_conversation_id IS NOT NULL;
