import { createContext, useContext } from 'react';

import type { components } from '../../api/schema';

export type Account = components['schemas']['AccountResponse'];

export interface AuthContextValue {
  account: Account | null;
  expired: boolean;
  loading: boolean;
  bootstrap(input: {
    bootstrapToken: string;
    displayName?: string;
    password: string;
    username: string;
  }): Promise<void>;
  changePassword(currentPassword: string, newPassword: string): Promise<void>;
  login(username: string, password: string): Promise<void>;
  logout(): Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return value;
}
