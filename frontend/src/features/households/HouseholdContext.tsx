import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { loadSelection, saveSelection } from '../../app/selectionStorage';

export type Household = components['schemas']['HouseholdRead'];

interface HouseholdContextValue {
  add: (household: Household) => void;
  error: Error | null;
  households: Household[];
  loading: boolean;
  reload: () => void;
  selected: Household | null;
  select: (household: Household | null) => void;
}

const HouseholdContext = createContext<HouseholdContextValue | null>(null);
let lastSessionAccountId: string | null = null;

function initialSelection(accountId: string): string | null {
  const accountChanged =
    lastSessionAccountId !== null && lastSessionAccountId !== accountId;
  lastSessionAccountId = accountId;
  if (accountChanged) {
    saveSelection('household', null);
    saveSelection('person', null);
    saveSelection('property', null);
    return null;
  }
  return loadSelection('household');
}

export function HouseholdProvider({
  children,
  sessionAccountId,
}: {
  children: React.ReactNode;
  sessionAccountId: string;
}) {
  const [selectedId, setSelectedId] = useState(() =>
    initialSelection(sessionAccountId),
  );
  const selectedIdRef = useRef(selectedId);
  const [households, setHouseholds] = useState<Household[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const selected =
    households.find((household) => household.id === selectedId) ?? null;

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    setRequestVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    let active = true;
    void apiRequest<Household[]>('/api/v1/households', {
      // The session endpoint owns global expiry handling. A secondary request
      // must not tear down a newly restored shell during transient failures.
      suppressUnauthorisedEvent: true,
    })
      .then((accessible) => {
        if (!active) return;
        if (!Array.isArray(accessible)) {
          throw new Error('The household list response was not valid');
        }
        setHouseholds(accessible);
        if (
          selectedIdRef.current !== null &&
          !accessible.some((item) => item.id === selectedIdRef.current)
        ) {
          saveSelection('household', null);
          saveSelection('person', null);
          saveSelection('property', null);
          selectedIdRef.current = null;
          setSelectedId(null);
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError
              : new Error('The household list request failed'),
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [requestVersion]);

  const value = useMemo<HouseholdContextValue>(
    () => ({
      add: (newHousehold) => {
        setHouseholds((current) => [...current, newHousehold]);
      },
      error,
      households,
      loading,
      reload,
      selected,
      select: (household) => {
        const nextId = household?.id ?? null;
        selectedIdRef.current = nextId;
        setSelectedId(nextId);
        saveSelection('household', nextId);
        saveSelection('person', null);
        saveSelection('property', null);
      },
    }),
    [error, households, loading, reload, selected],
  );

  return (
    <HouseholdContext.Provider value={value}>
      {children}
    </HouseholdContext.Provider>
  );
}

// Context hooks intentionally live with their provider to keep its contract local.
// eslint-disable-next-line react-refresh/only-export-components
export function useHousehold(): HouseholdContextValue {
  const context = useContext(HouseholdContext);
  if (context === null) {
    throw new Error('useHousehold must be used inside HouseholdProvider');
  }
  return context;
}
