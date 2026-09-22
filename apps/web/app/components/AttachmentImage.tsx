'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '../lib/auth';
import { API_BASE } from '../lib/api';

export function AttachmentImage({ id }: { id: string }) {
  const { token } = useAuth();
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let objectUrl: string | null = null;
    let cancelled = false;

    fetch(`${API_BASE}/attachments/${id}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error('failed'))))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        /* leave placeholder */
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [token, id]);

  if (!src) {
    return (
      <div
        style={{
          width: 200,
          height: 150,
          background: 'var(--color-bg)',
          borderRadius: 10,
          border: '1px solid var(--color-border)',
        }}
      />
    );
  }

  return (
    <img
      src={src}
      alt="Вложение"
      style={{ maxWidth: 240, maxHeight: 320, borderRadius: 10, display: 'block', objectFit: 'cover' }}
    />
  );
}
