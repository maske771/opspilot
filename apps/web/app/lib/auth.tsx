'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch, type UserRead } from './api';

const TOKEN_KEY = 'opspilot_token';

type AuthState = {
  token: string | null;
  user: UserRead | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserRead | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const stored = window.localStorage.getItem(TOKEN_KEY);
    if (stored) {
      setToken(stored);
    } else {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    apiFetch<UserRead>('/auth/me', { token })
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (cancelled) return;
        window.localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: { email, password },
    });
    window.localStorage.setItem(TOKEN_KEY, res.access_token);
    setToken(res.access_token);
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    router.push('/login');
  }, [router]);

  return (
    <AuthContext.Provider value={{ token, user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !token) router.replace('/login');
  }, [loading, token, router]);

  if (loading || !token) {
    return <main style={{ padding: 40, color: '#6b7280' }}>Загрузка...</main>;
  }
  return <>{children}</>;
}
