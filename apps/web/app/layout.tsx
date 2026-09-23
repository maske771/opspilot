import type { Metadata } from 'next';
import { Inter, Noto_Sans_Thai } from 'next/font/google';
import { AuthProvider } from './lib/auth';
import { LocaleProvider } from './lib/locale';
import { ThemeProvider } from './lib/theme';
import { THEME_INIT_SCRIPT } from './lib/theme-init';
import './globals.css';

const inter = Inter({ subsets: ['latin', 'cyrillic'], display: 'swap', variable: '--font-inter' });
const notoSansThai = Noto_Sans_Thai({ subsets: ['thai'], display: 'swap', variable: '--font-thai' });

export const metadata: Metadata = {
  title: 'OpsPilot',
  description: 'AI Operations Hub for Property Management',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${notoSansThai.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <LocaleProvider>
            <AuthProvider>{children}</AuthProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
