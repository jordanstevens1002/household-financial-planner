import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AdvancedSection } from './AdvancedSection';
import { ConfirmDialog } from './ConfirmDialog';
import { DataTable } from './DataTable';
import { EmptyState } from './EmptyState';
import { NotificationProvider } from './NotificationProvider';
import { useNotification } from './notificationContext';

describe('shared design components', () => {
  it('renders typed table rows and an accessible caption', () => {
    render(
      <DataTable
        caption="Example balances"
        columns={[
          { key: 'name', label: 'Account', render: (row) => row.name },
          { key: 'balance', label: 'Balance', render: (row) => row.balance },
        ]}
        getRowKey={(row) => row.name}
        rows={[{ balance: '$120.00', name: 'Everyday account' }]}
      />,
    );

    expect(
      screen.getByRole('table', { name: 'Example balances' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Everyday account')).toBeInTheDocument();
  });

  it('supports empty-state and confirmation actions', async () => {
    const user = userEvent.setup();
    const action = vi.fn();
    const cancel = vi.fn();

    const { rerender } = render(
      <EmptyState
        actionLabel="Add one"
        description="Nothing here yet."
        onAction={action}
        title="No records"
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Add one' }));
    expect(action).toHaveBeenCalledOnce();

    rerender(
      <ConfirmDialog
        description="This cannot be undone."
        onCancel={cancel}
        onConfirm={action}
        open
        title="Delete record?"
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(cancel).toHaveBeenCalledOnce();
  });

  it('hides specialist controls behind one advanced pattern', async () => {
    const user = userEvent.setup();
    render(
      <AdvancedSection>
        <label>
          Provider JSON
          <textarea />
        </label>
      </AdvancedSection>,
    );

    expect(screen.queryByLabelText('Provider JSON')).not.toBeVisible();
    await user.click(screen.getByText('Advanced'));
    expect(screen.getByLabelText('Provider JSON')).toBeVisible();
  });

  it('requires notification consumers to use the provider', () => {
    function Consumer() {
      const { notify } = useNotification();
      return <button onClick={() => notify('Saved', 'success')}>Save</button>;
    }

    expect(() => render(<Consumer />)).toThrow(
      'useNotification must be used within NotificationProvider',
    );
  });

  it('shows a notification through the provider', async () => {
    const user = userEvent.setup();

    function Consumer() {
      const { notify } = useNotification();
      return <button onClick={() => notify('Saved', 'success')}>Save</button>;
    }

    render(
      <NotificationProvider>
        <Consumer />
      </NotificationProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Saved')).toBeInTheDocument();
  });
});
