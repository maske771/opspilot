'use client';

import { useRef, useState } from 'react';
import { ApiError, apiUpload, type TicketNoteRead } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLocale } from '../lib/locale';
import { AttachmentImage } from './AttachmentImage';

const MAX_PHOTOS = 5;
const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

export function WorkLog({
  ticketId,
  notes,
  closed,
  onAdded,
}: {
  ticketId: string;
  notes: TicketNoteRead[];
  closed: boolean;
  onAdded: (note: TicketNoteRead) => void;
}) {
  const { token } = useAuth();
  const { t, formatDateTime } = useLocale();
  const [body, setBody] = useState('');
  const [photos, setPhotos] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function pickPhotos(list: FileList | null) {
    const picked = Array.from(list ?? []);
    if (photos.length + picked.length > MAX_PHOTOS) {
      setError(t('worklog.tooManyPhotos', { max: MAX_PHOTOS }));
      return;
    }
    if (picked.some((f) => f.size > MAX_PHOTO_BYTES)) {
      setError(t('worklog.photoTooBig'));
      return;
    }
    setError(null);
    setPhotos((prev) => [...prev, ...picked]);
    if (fileInput.current) fileInput.current.value = '';
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim() && photos.length === 0) return;
    const form = new FormData();
    form.append('body', body);
    photos.forEach((p) => form.append('photos', p));
    setBusy(true);
    setError(null);
    try {
      onAdded(await apiUpload<TicketNoteRead>(`/tickets/${ticketId}/notes`, form, token));
      setBody('');
      setPhotos([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('worklog.saveFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {notes.length === 0 ? (
        <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', marginTop: 0 }}>{t('worklog.empty')}</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 20 }}>
          {notes.map((note) => (
            <div key={note.id} style={{ borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--color-text-subtle)', marginBottom: 6 }}>
                {note.author_email?.split('@')[0] ?? t('worklog.unknownAuthor')} · {formatDateTime(note.created_at)}
              </div>
              {note.body && <div style={{ fontSize: 14, whiteSpace: 'pre-wrap', marginBottom: note.attachments.length ? 10 : 0 }}>{note.body}</div>}
              {note.attachments.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                  {note.attachments.map((a) => (
                    <AttachmentImage key={a.id} id={a.id} kind="ticket" />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {closed ? (
        <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', margin: 0 }}>{t('worklog.closed')}</p>
      ) : (
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <textarea
            className="textarea"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={t('worklog.placeholder')}
            maxLength={5000}
            rows={3}
          />
          {photos.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {photos.map((p, i) => (
                <span key={`${p.name}-${i}`} className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)', display: 'inline-flex', gap: 6 }}>
                  {p.name}
                  <button
                    type="button"
                    aria-label={t('worklog.removePhoto')}
                    onClick={() => setPhotos((prev) => prev.filter((_, j) => j !== i))}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0 }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          {error && <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              ref={fileInput}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={(e) => pickPhotos(e.target.files)}
              style={{ display: 'none' }}
              aria-label={t('worklog.addPhotos')}
            />
            <button type="button" className="btn btn-secondary" onClick={() => fileInput.current?.click()} disabled={busy || photos.length >= MAX_PHOTOS}>
              {t('worklog.addPhotos')}
            </button>
            <button type="submit" className="btn btn-accent" disabled={busy || (!body.trim() && photos.length === 0)}>
              {busy ? t('common.saving') : t('worklog.add')}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
