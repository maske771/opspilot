ALTER TABLE channels
    ADD COLUMN webhook_token TEXT NOT NULL
    DEFAULT replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
