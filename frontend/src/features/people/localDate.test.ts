import { localCalendarDate } from './localDate';

describe('local calendar date', () => {
  it('uses the next local day east of UTC after local midnight', () => {
    expect(
      localCalendarDate(new Date('2026-08-01T14:30:00Z'), 'Australia/Sydney'),
    ).toBe('2026-08-02');
  });

  it('uses the previous local day west of UTC before local midnight', () => {
    expect(
      localCalendarDate(
        new Date('2026-08-02T00:30:00Z'),
        'America/Los_Angeles',
      ),
    ).toBe('2026-08-01');
  });
});
