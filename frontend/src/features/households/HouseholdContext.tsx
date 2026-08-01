import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { loadSelection, saveSelection } from '../../app/selectionStorage';

export type Household = components['schemas']['HouseholdRead'];

interface HouseholdContextValue {
  add: (household: Household) => void;
  households: Household[];
  loading: boolean;
  selected: Household | null;
  select: (household: Household | null) => void;
}

const HouseholdContext = createContext<HouseholdContextValue | null>(null);

export function HouseholdProvider({
  children,
  sessionAccountId,
}: {
  children: React.ReactNode;
  sessionAccountId: string;
}) {
  const [selectedId, setSelectedId] = useState(() =>
    loadSelection('household'),
  );
  const [households, setHouseholds] = useState<Household[]>([]);
  const [loading, setLoading] = useState(true);
  const selected =
    households.find((household) => household.id === selectedId) ?? null;

  useEffect(() => {
    let active = true;
    void apiRequest<Household[]>('/api/v1/households', {
      // The session endpoint owns global expiry handling. A secondary request
      // must not tear down a newly restored shell during transient failures.
      suppressUnauthorisedEvent: true,
    })
      .then((accessible) => {
        if (!active) return;
        if (!Array.isArray(accessible)) return;
        setHouseholds(accessible);
        if (
          selectedId !== null &&
          !accessible.some((item) => item.id === selectedId)
        ) {
          saveSelection('household', null);
          saveSelection('person', null);
          saveSelection('property', null);
          setSelectedId(null);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId, sessionAccountId]);

  const value = useMemo<HouseholdContextValue>(
    () => ({
      add: (newHousehold) => {
        setHouseholds((current) => [...current, newHousehold]);
      },
      households,
      loading,
      selected,
      select: (household) => {
        setSelectedId(household?.id ?? null);
        saveSelection('household', household?.id ?? null);
        saveSelection('person', null);
        saveSelection('property', null);
      },
    }),
    [households, loading, selected],
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
