import { createContext, useContext } from 'react';

export type NotificationSeverity = 'error' | 'info' | 'success' | 'warning';

export interface NotificationContextValue {
  notify: (message: string, severity?: NotificationSeverity) => void;
}

export const NotificationContext =
  createContext<NotificationContextValue | null>(null);

export function useNotification(): NotificationContextValue {
  const context = useContext(NotificationContext);
  if (context === null) {
    throw new Error('useNotification must be used within NotificationProvider');
  }
  return context;
}
