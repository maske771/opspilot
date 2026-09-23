'use client';

import { RequireAuth, useAuth } from './lib/auth';
import { isManagerRole } from './lib/roles';
import { InboxView } from './inbox/page';
import { TicketsList } from './tickets/page';

function Home() {
  const { user } = useAuth();

  if (!user) return null;

  if (isManagerRole(user.role)) {
    return <InboxView />;
  }

  return <TicketsList mine />;
}

export default function HomePage() {
  return (
    <RequireAuth>
      <Home />
    </RequireAuth>
  );
}
