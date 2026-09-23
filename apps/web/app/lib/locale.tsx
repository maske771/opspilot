'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { en, type MessageKey, type Messages } from './i18n/en';
import { ru } from './i18n/ru';
import { th } from './i18n/th';

export type Locale = 'en' | 'ru' | 'th';

export const LOCALES: { code: Locale; label: string; name: string }[] = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'ru', label: 'RU', name: 'Русский' },
  { code: 'th', label: 'TH', name: 'ไทย' },
];

const MESSAGES: Record<Locale, Messages> = { en, ru, th };
const INTL_LOCALE: Record<Locale, string> = { en: 'en-GB', ru: 'ru-RU', th: 'th-TH-u-ca-gregory' };
const LOCALE_KEY = 'opspilot_locale';

type Params = Record<string, string | number>;

type LocaleState = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, params?: Params) => string;
  tOr: (key: string, fallback: string) => string;
  formatDateTime: (value: string | Date) => string;
  formatDate: (value: string | Date) => string;
  timeAgo: (iso: string) => string;
};

const LocaleContext = createContext<LocaleState | null>(null);

function detectLocale(): Locale {
  try {
    const stored = window.localStorage.getItem(LOCALE_KEY);
    if (stored === 'en' || stored === 'ru' || stored === 'th') return stored;
  } catch {
    /* storage unavailable — fall back to the browser language */
  }
  const lang = (navigator.language ?? '').toLowerCase();
  if (lang.startsWith('ru')) return 'ru';
  if (lang.startsWith('th')) return 'th';
  return 'en';
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('en');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setLocaleState(detectLocale());
    setReady(true);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_KEY, next);
    } catch {
      /* the choice just won't persist */
    }
  }, []);

  const value = useMemo<LocaleState>(() => {
    const messages = MESSAGES[locale];
    const intl = INTL_LOCALE[locale];
    const dateTime = new Intl.DateTimeFormat(intl, { dateStyle: 'medium', timeStyle: 'short' });
    const date = new Intl.DateTimeFormat(intl, { dateStyle: 'medium' });
    const relative = new Intl.RelativeTimeFormat(intl, { numeric: 'always', style: 'short' });

    const t = (key: MessageKey, params?: Params) => {
      let text: string = messages[key];
      if (params) {
        for (const [name, replacement] of Object.entries(params)) {
          text = text.replaceAll(`{${name}}`, String(replacement));
        }
      }
      return text;
    };

    return {
      locale,
      setLocale,
      t,
      tOr: (key, fallback) => (messages as Record<string, string>)[key] ?? fallback,
      formatDateTime: (v) => dateTime.format(new Date(v)),
      formatDate: (v) => date.format(new Date(v)),
      timeAgo: (iso) => {
        const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
        if (minutes < 1) return t('time.justNow');
        if (minutes < 60) return relative.format(-minutes, 'minute');
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return relative.format(-hours, 'hour');
        return relative.format(-Math.floor(hours / 24), 'day');
      },
    };
  }, [locale, setLocale]);

  if (!ready) return null;

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleState {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error('useLocale must be used within LocaleProvider');
  return ctx;
}
