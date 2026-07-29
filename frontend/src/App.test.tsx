import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { App } from './App';

describe('App', () => {
  it('explains the parallel migration without presenting an unfinished workflow', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(
      screen.getByRole('heading', { name: 'Household Financial Planner' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /connect/i }),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: 'About this preview' }),
    );

    expect(
      screen.getByText(/Appsmith remains available during the migration/i),
    ).toBeInTheDocument();
  });
});
