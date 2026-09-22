import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { AuthProvider } from './lib/auth';
import './globals.css';

const inter = Inter({ subsets: ['latin', 'cyrillic'], display: 'swap' });

export const metadata: Metadata = {
  title: 'OpsPilot',
  description: 'AI Operations Hub for Property Management',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.className}>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
