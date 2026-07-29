import { Alert, Snackbar } from '@mui/material';
import { useCallback, useMemo, useState, type ReactNode } from 'react';

import {
  NotificationContext,
  type NotificationSeverity,
} from './notificationContext';

interface Notification {
  message: string;
  severity: NotificationSeverity;
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notification, setNotification] = useState<Notification | null>(null);
  const notify = useCallback(
    (message: string, severity: NotificationSeverity = 'info') => {
      setNotification({ message, severity });
    },
    [],
  );
  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <Snackbar
        autoHideDuration={5000}
        onClose={() => {
          setNotification(null);
        }}
        open={notification !== null}
      >
        {notification ? (
          <Alert
            onClose={() => {
              setNotification(null);
            }}
            severity={notification.severity}
            variant="filled"
          >
            {notification.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </NotificationContext.Provider>
  );
}
