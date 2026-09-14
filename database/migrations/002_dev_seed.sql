-- Local development seed data for the first end-to-end API flow.
-- These fixed UUIDs make Swagger testing repeatable.
INSERT INTO organizations (id, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'OpsPilot Demo')
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, organization_id, email, password_hash, role)
VALUES (
    '00000000-0000-0000-0000-000000000010',
    '00000000-0000-0000-0000-000000000001',
    'admin@opspilot.local',
    'dev-only-no-login',
    'admin'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO properties (id, organization_id, name, address)
VALUES (
    '00000000-0000-0000-0000-000000000100',
    '00000000-0000-0000-0000-000000000001',
    'Demo Villa Resort',
    'Pattaya, Thailand'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO units (id, organization_id, property_id, name, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000200',
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000100',
    '304',
    '{"type":"villa"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO sla_policies (organization_id, priority, response_minutes, resolution_minutes)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'critical', 15, 60),
    ('00000000-0000-0000-0000-000000000001', 'high', 30, 240),
    ('00000000-0000-0000-0000-000000000001', 'medium', 120, 1440),
    ('00000000-0000-0000-0000-000000000001', 'low', 480, 4320)
ON CONFLICT (organization_id, priority) DO NOTHING;
