'use client';

import { useLocale, LOCALES } from '../lib/locale';
import { useTheme } from '../lib/theme';

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

export function Preferences() {
  const { locale, setLocale, t } = useLocale();
  const { theme, toggleTheme } = useTheme();
  const dark = theme === 'dark';

  return (
    <div className="prefs">
      <div className="seg" role="group" aria-label={t('switcher.language')}>
        {LOCALES.map((l) => (
          <button
            key={l.code}
            type="button"
            lang={l.code}
            title={l.name}
            aria-pressed={locale === l.code}
            className={`seg-btn${locale === l.code ? ' seg-btn-active' : ''}`}
            onClick={() => setLocale(l.code)}
          >
            {l.label}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="icon-btn"
        onClick={toggleTheme}
        title={dark ? t('switcher.toLight') : t('switcher.toDark')}
        aria-label={dark ? t('switcher.toLight') : t('switcher.toDark')}
      >
        {dark ? <SunIcon /> : <MoonIcon />}
      </button>
    </div>
  );
}
