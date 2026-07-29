# Retirement projection assumptions

Retirement projections are estimates, not financial advice.

- Returns use the account's user-entered annual rate, compounded monthly.
- Annual fees are spread evenly across months.
- Employer, voluntary pre-tax and voluntary post-tax amounts are annual values spread across months.
- Employer rates apply to linked taxable income effective at the projection date.
- Contribution tax applies to employer and voluntary pre-tax contributions, not post-tax
  contributions.
- Configured caps produce warnings and do not silently discard contributions.
- Dated balance adjustments are applied in their containing monthly period and the balance cannot
  fall below zero.
- Retirement and preservation ages are milestones only; drawdown is not modelled.
- Projections are limited to 80 years and preserve the account's currency; currency conversion is
  not performed.

Jurisdiction rules are supplied by optional retirement providers selected by `provider_code`.
Australia is the bundled example provider; generic calculation logic does not assume Australian
caps, tax rates, terminology or retirement ages.
