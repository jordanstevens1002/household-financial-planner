import { act, render, screen, waitFor } from '@testing-library/react';

import { HouseholdProvider, useHousehold } from './HouseholdContext';

const first = {
  currency: 'AUD',
  display_name: 'First private household',
  id: 'dccc2857-cf74-4863-9f00-c99a9f815495',
  jurisdiction: 'AU',
};
const second = {
  currency: 'NZD',
  display_name: 'Second private household',
  id: '5d5b7d5c-f8c0-4599-bebf-3ed219d9209e',
  jurisdiction: 'NZ',
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    status,
  });
}

function Probe() {
  const context = useHousehold();
  return (
    <div>
      <span>{context.loading ? 'Loading households' : 'Finished loading'}</span>
      <span>{context.error?.message}</span>
      {context.households.map((household) => (
        <button key={household.id} onClick={() => context.select(household)}>
          {household.display_name}
        </button>
      ))}
      <span>{context.selected?.display_name}</span>
    </div>
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

describe('account-scoped household state', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('removes the previous account data while the new account loads', async () => {
    const nextRequest = deferred<Response>();
    let request = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(() => {
        request += 1;
        return request === 1
          ? Promise.resolve(response([first]))
          : nextRequest.promise;
      }),
    );
    const view = render(
      <HouseholdProvider key="first-account" sessionAccountId="first-account">
        <Probe />
      </HouseholdProvider>,
    );
    await screen.findByRole('button', { name: first.display_name });

    view.rerender(
      <HouseholdProvider key="second-account" sessionAccountId="second-account">
        <Probe />
      </HouseholdProvider>,
    );
    expect(screen.queryByText(first.display_name)).not.toBeInTheDocument();
    expect(screen.getByText('Loading households')).toBeVisible();

    act(() => nextRequest.resolve(response([second])));
    expect(
      await screen.findByRole('button', { name: second.display_name }),
    ).toBeVisible();
  });

  it('does not restore the previous account data when the new request fails', async () => {
    const nextRequest = deferred<Response>();
    let request = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(() => {
        request += 1;
        return request === 1
          ? Promise.resolve(response([first]))
          : nextRequest.promise;
      }),
    );
    const view = render(
      <HouseholdProvider key="first-account" sessionAccountId="first-account">
        <Probe />
      </HouseholdProvider>,
    );
    await screen.findByRole('button', { name: first.display_name });

    view.rerender(
      <HouseholdProvider key="second-account" sessionAccountId="second-account">
        <Probe />
      </HouseholdProvider>,
    );
    act(() => nextRequest.reject(new Error('Account load failed')));

    await waitFor(() =>
      expect(screen.getByText('Account load failed')).toBeVisible(),
    );
    expect(screen.queryByText(first.display_name)).not.toBeInTheDocument();
    expect(screen.getByText('Finished loading')).toBeVisible();
  });
});
