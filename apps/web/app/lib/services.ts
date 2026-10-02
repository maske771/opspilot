'use client';

import { useCallback, useEffect, useState } from 'react';
import { apiFetch, type ServiceRead } from './api';
import { useAuth } from './auth';
import { useLocale } from './locale';

// One fetch per page load, shared by every component that needs service names.
let cache: Promise<ServiceRead[]> | null = null;
let cacheToken: string | null = null;

export function invalidateServices() {
  cache = null;
}

export function serviceName(service: ServiceRead | undefined, locale: string, fallback: string): string {
  if (!service) return fallback;
  return service.names[locale] || service.names.en || Object.values(service.names)[0] || fallback;
}

/** All of the organization's services, archived included, so old tickets keep their labels. */
export function useServices() {
  const { token } = useAuth();
  const { locale, tOr } = useLocale();
  const [services, setServices] = useState<ServiceRead[]>([]);

  useEffect(() => {
    if (!token) return;
    if (!cache || cacheToken !== token) {
      cacheToken = token;
      cache = apiFetch<ServiceRead[]>('/services?include_archived=true', { token }).catch(() => {
        cache = null;
        return [];
      });
    }
    let cancelled = false;
    cache.then((list) => {
      if (!cancelled) setServices(list);
    });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const label = useCallback(
    (code: string) => serviceName(services.find((s) => s.code === code), locale, tOr(`category.${code}`, code)),
    [services, locale, tOr],
  );

  return { services, active: services.filter((s) => !s.archived), label };
}
