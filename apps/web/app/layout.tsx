import type { Metadata } from 'next';
import { AuthProvider } from './lib/auth';

export const metadata: Metadata = {
  title: 'OpsPilot',
  description: 'AI Operations Hub for Property Management',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: '#f9fafb', fontFamily: 'Arial, sans-serif', color: '#111827' }}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
