# Phase 7 retirement projection assumptions

Retirement projections are planning estimates, not financial advice.

- Returns use the account's user-entered annual rate, compounded monthly.
- Annual fees are spread evenly across months.
- Employer amounts and voluntary/non-concessional amounts are annual values spread across months.
- Employer rates apply to linked taxable income effective at the projection date. This simplified
  Phase 7 basis is disclosed in every projection response; contribution-income timing can be made
  more granular in a later phase.
- Contribution tax applies to employer and voluntary concessional contributions, not
  non-concessional contributions.
- Configured caps produce warnings and do not silently discard contributions.
- Dated balance adjustments are applied in their containing monthly period and the balance cannot
  fall below zero.
- Retirement and preservation ages are milestones only. Drawdown is deliberately deferred to a
  later phase.
- Projections are limited to 80 years and preserve the account's currency; currency conversion is
  not performed.

The Australian super profile is optional jurisdiction-specific metadata on the generic account
model. Generic calculation logic does not assume Australian caps, tax rates or retirement ages.
