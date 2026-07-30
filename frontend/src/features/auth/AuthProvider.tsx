import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError, apiRequest, setUnauthorisedHandler } from '../../api/client';
import type { components } from '../../api/schema';
import { AuthContext, type Account } from './AuthContext';

type SessionResponse = components['schemas']['SessionResponse'];

function csrfCookie(): string | undefined {
  const prefix = 'hfp_csrf=';
  const value = document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : undefined;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [expired, setExpired] = useState(false);
  const [loading, setLoading] = useState(true);
  const csrfToken = useRef<string | undefined>(csrfCookie());
  const hadSession = useRef(false);

  const markUnauthorised = useCallback(() => {
    if (hadSession.current) {
      setExpired(true);
    }
    hadSession.current = false;
    setAccount(null);
  }, []);

  const refreshSession = useCallback(async () => {
    try {
      const response = await apiRequest<SessionResponse>(
        '/api/v1/auth/session',
        { suppressUnauthorisedEvent: true },
      );
      hadSession.current = true;
      setAccount(response.account);
      setExpired(false);
      csrfToken.current = csrfCookie();
    } catch (error) {
      if (!(error instanceof ApiError && error.kind === 'unauthorised')) {
        throw error;
      }
      markUnauthorised();
    } finally {
      setLoading(false);
    }
  }, [markUnauthorised]);

  useEffect(() => {
    setUnauthorisedHandler(markUnauthorised);
    const initial = window.setTimeout(() => {
      void refreshSession();
    }, 0);
    const timer = window.setInterval(() => {
      void refreshSession();
    }, 60_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
      setUnauthorisedHandler();
    };
  }, [markUnauthorised, refreshSession]);

  const acceptSession = useCallback((response: SessionResponse) => {
    setAccount(response.account);
    setExpired(false);
    hadSession.current = true;
    csrfToken.current = response.csrf_token ?? csrfCookie();
  }, []);

  const value = useMemo(
    () => ({
      account,
      expired,
      loading,
      async bootstrap(input: {
        bootstrapToken: string;
        displayName?: string;
        password: string;
        username: string;
      }) {
        const response = await apiRequest<SessionResponse>(
          '/api/v1/auth/bootstrap',
          {
            body: JSON.stringify({
              display_name: input.displayName || null,
              password: input.password,
              username: input.username,
            }),
            headers: { 'X-Bootstrap-Token': input.bootstrapToken },
            method: 'POST',
          },
        );
        acceptSession(response);
      },
      async changePassword(currentPassword: string, newPassword: string) {
        const response = await apiRequest<SessionResponse>(
          '/api/v1/auth/password/change',
          {
            body: JSON.stringify({
              current_password: currentPassword,
              new_password: newPassword,
            }),
            csrfToken: csrfToken.current,
            method: 'POST',
            suppressUnauthorisedEvent: true,
          },
        );
        acceptSession(response);
      },
      csrfToken() {
        return csrfToken.current;
      },
      async login(username: string, password: string) {
        const response = await apiRequest<SessionResponse>(
          '/api/v1/auth/login',
          {
            body: JSON.stringify({ password, username }),
            method: 'POST',
          },
        );
        acceptSession(response);
      },
      async logout() {
        await apiRequest<void>('/api/v1/auth/logout', {
          csrfToken: csrfToken.current,
          method: 'POST',
        });
        csrfToken.current = undefined;
        hadSession.current = false;
        setAccount(null);
        setExpired(false);
      },
    }),
    [acceptSession, account, expired, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
