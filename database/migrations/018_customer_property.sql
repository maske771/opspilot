-- A short code per property that managers hand out to residents; the bot asks for it on first contact.
ALTER TABLE properties ADD COLUMN code TEXT;
UPDATE properties SET code = upper(substr(md5(random()::text || id::text), 1, 6)) WHERE code IS NULL;
ALTER TABLE properties ALTER COLUMN code SET NOT NULL;
ALTER TABLE properties ADD CONSTRAINT uq_properties_org_code UNIQUE (organization_id, code);

ALTER TABLE customers
    ADD COLUMN property_id UUID REFERENCES properties(id) ON DELETE SET NULL,
    ADD COLUMN unit_id UUID REFERENCES units(id) ON DELETE SET NULL;

-- Dialog state: the conversation is waiting for the customer's property code. pending_message_id is
-- the request they sent before being linked (deliberately no FK: messages already reference conversations).
ALTER TABLE conversations
    ADD COLUMN pending_step TEXT,
    ADD COLUMN pending_message_id UUID;
