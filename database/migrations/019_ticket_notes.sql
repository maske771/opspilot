-- Work log on a ticket: comments and photos from the staff doing the work.
CREATE TABLE ticket_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    body TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_ticket_notes_ticket_id ON ticket_notes(ticket_id);

CREATE TABLE ticket_note_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    note_id UUID NOT NULL REFERENCES ticket_notes(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_ticket_note_attachments_note_id ON ticket_note_attachments(note_id);
