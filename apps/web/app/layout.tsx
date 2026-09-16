import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'OpsPilot',
  description: 'AI Operations Hub for Property Management',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body style={{ margin: 0, background: '#f9fafb' }}>{children}</body>
    </html>
  );
}
