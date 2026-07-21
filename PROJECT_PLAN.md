# Open Household Property & Financial Planner
## Codex-Ready Project Specification — General-Purpose Edition

## 1. Project purpose

Build an open-source, self-hosted household financial planning application with a visual, time-aware interface.

The application must be suitable for different users, households and property situations. It must not assume:

- exactly two people;
- a particular property;
- a fixed number of properties;
- that every property is an investment;
- that every user is in the same tax jurisdiction;
- that financial history begins when the application is installed;
- that all assets and loans are currently active.

The application should help a household understand:

- income and take-home pay;
- household spending and cash flow;
- property values, debt and equity;
- mortgage and loan progress;
- owner-occupied, rented, vacant and other property states;
- rental income and property expenses;
- superannuation or retirement accounts;
- future purchase feasibility;
- the effect of dated financial changes and life events;
- financial position at any historical or projected date;
- scenario comparisons.

The application should prioritise clarity, resilience, flexibility and informed decision-making rather than aggressive wealth maximisation.

The product is a personal and household planning tool, primarily for people considering or
maintaining a small number of homes (typically two or three). Its language should be casual,
clear and centred on owners, renters and household decisions. Avoid positioning features for
large property businesses, professional property management or industry workflows.

---

## 2. Product scope

### Intended users

The initial release should support:

- an individual;
- a couple;
- a family household;
- a group of co-owners;
- a household with no property;
- a first-home buyer;
- a current homeowner;
- a homeowner who rents out some or all of a property;
- someone with both owner-occupied and rented properties;
- someone entering years of historical data;
- someone planning future purchases or sales.

### Configurability requirements

Users must be able to configure:

- any number of household members;
- any number of properties within reasonable deployment limits;
- multiple owners per property;
- ownership percentages;
- different property types;
- multiple loans per property;
- historical and future events;
- household-specific terminology and display names;
- local tax and superannuation assumptions.

Do not hard-code named people, property names, locations or loan values in application logic.

Do not hard-code a deployment-wide currency or silently persist a jurisdictional currency
default. Household currency must be selected explicitly. Child financial records may inherit
that household currency while still allowing an explicit override for cross-currency assets.

Do not convert unknown financial values into zero or unknown provenance into an estimate/fact.
Inputs such as debt balances and observed-versus-estimated status must be explicit whenever
omission would change the financial meaning of a record.

### Practical limits

The schema should not impose an artificial property limit.

For user experience and performance:

- normal screens may display the first 10–20 active properties;
- pagination and filtering must be used for larger sets;
- projections should remain efficient for at least:
  - 10 household members;
  - 50 properties;
  - 100 loans;
  - 50 years of monthly projections.

These are design-performance targets, not product recommendations.

---

## 3. Recommended architecture

### Core stack

- **Frontend / application UI:** Appsmith Community Edition
- **Database:** PostgreSQL
- **Calculation service:** Python FastAPI
- **ORM:** SQLAlchemy
- **Database migrations:** Alembic
- **Charts:** Appsmith chart widgets initially; Apache ECharts for custom visualisations
- **Deployment:** Docker Compose
- **Authentication:** Appsmith authentication for the first release
- **Reverse proxy:** Nginx Proxy Manager, Caddy or another user-selected proxy
- **Optional automation:** n8n
- **Optional budgeting integration:** Actual Budget or Firefly III
- **Optional observability:** Grafana and Prometheus

### Separation of responsibilities

#### Appsmith

Responsible for:

- forms;
- dashboards;
- navigation;
- tables;
- charts;
- validation feedback;
- user interaction.

#### FastAPI

Responsible for:

- business rules;
- calculation orchestration;
- timeline resolution;
- tax calculations;
- loan amortisation;
- rental calculations;
- retirement-account projections;
- scenario generation;
- validation;
- audit events.

#### PostgreSQL

Responsible for:

- durable source-of-truth records;
- dated events;
- versioned assumptions;
- scenarios;
- snapshots;
- user preferences.

Do not make Appsmith formulas the source of truth for financial calculations.

---

## 4. Application tenancy and sharing model

The application should be designed so it can be shared with other people without sharing financial data between households.

### Core entities

```text
Application User
    ↓ membership
Household
    ↓
People, Properties, Loans, Accounts, Expenses, Goals and Scenarios
```

### Household isolation

Every financial record must belong directly or indirectly to a `household_id`.

API requests must verify that the authenticated user is a member of the requested household.

### Household roles

Use configurable roles:

```text
OWNER
ADMIN
EDITOR
VIEWER
```

Suggested permissions:

- `OWNER`: manage household, membership and deletion;
- `ADMIN`: manage all financial records;
- `EDITOR`: create and edit financial records;
- `VIEWER`: read-only.

### Multiple households

A user may belong to more than one household.

Examples:

- their own household;
- a household shared with a partner;
- a household they help administer for a parent.

---

## 5. First-run onboarding

Do not seed real or assumed financial data into a normal production household.

The first-run wizard should:

1. Create a household.
2. Ask for household display name.
3. Add one or more people.
4. Ask for jurisdiction and preferred currency.
5. Ask whether to add:
   - income;
   - household expenses;
   - properties;
   - loans;
   - retirement accounts;
   - other assets or liabilities.
6. Allow records to be entered with historical effective dates.
7. Ask for a projection horizon.
8. Present a review screen.
9. Create the household baseline.

### Demo mode

Provide an optional demo household containing fictional data.

The demo must:

- be clearly labelled;
- contain no user-specific names;
- be removable;
- never be created automatically in production mode.

---

## 6. People and household members

### People are configurable records

The application must support zero or more people in each household.

A person may have:

- a display name;
- date of birth;
- tax residency;
- income records;
- tax profile;
- retirement accounts;
- ownership shares;
- liabilities;
- goals.

A person does not need an application login.

This allows records for:

- a spouse or partner;
- a child or dependant where needed;
- a co-owner;
- an elderly family member;
- a trust beneficiary;
- a non-login household member.

### Person schema

```text
people
------
id
household_id
display_name
legal_name nullable
date_of_birth nullable
tax_residency_country nullable
tax_jurisdiction nullable
is_active
effective_from
effective_to nullable
notes
created_at
updated_at
```

### Household membership is separate

Application access must use `household_memberships`, not the `people` table.

```text
household_memberships
---------------------
id
household_id
application_user_id
role
created_at
updated_at
```

An application user may optionally be linked to a person record.

---

## 7. Property model

### Supported property types

Use a configurable property-type lookup table with initial values:

```text
APARTMENT
UNIT
TOWNHOUSE
SEMI_DETACHED
TERRACE
FREESTANDING_HOUSE
DUPLEX
VILLA
RURAL_RESIDENTIAL
FARM
VACANT_LAND
COMMERCIAL
INDUSTRIAL
RETAIL
MIXED_USE
HOLIDAY_PROPERTY
OTHER
```

Property types must be extendable without a database migration.

### Property lifecycle statuses

Use configurable status definitions with initial values:

```text
PLANNED
UNDER_CONTRACT
OWNER_OCCUPIED
RENTED
FAMILY_OCCUPIED
PARTIALLY_RENTED
SHORT_TERM_RENTAL
VACANT
RENOVATING
CONSTRUCTION
SOLD
TRANSFERRED
ARCHIVED
```

### Status behaviour

Each status definition should contain behavioural flags:

```text
generates_rental_income
applies_vacancy
applies_management_fee
applies_rental_expenses
is_occupied_by_household
is_active_asset
```

This is preferable to hard-coding logic against status names.

For example:

| Status | Rental income | Vacancy | Management fee | Household occupied |
|---|---:|---:|---:|---:|
| OWNER_OCCUPIED | No | No | No | Yes |
| RENTED | Yes | Yes | Yes | No |
| FAMILY_OCCUPIED | Configurable | No by default | Configurable | No |
| VACANT | No | No | No | No |
| PARTIALLY_RENTED | Configurable share | Configurable | Configurable | Yes |

### Properties schema

```text
properties
----------
id
household_id
display_name
property_type_id
address_line_1 nullable
address_line_2 nullable
suburb_or_locality nullable
state_or_region nullable
postal_code nullable
country_code
purchase_date nullable
sale_date nullable
purchase_price nullable
current_status_id
default_currency
notes
created_at
updated_at
```

### Property values

Do not store only one current value.

Use dated valuations:

```text
property_valuations
-------------------
id
property_id
valuation_date
value
valuation_type
source
is_estimate
notes
```

Valuation types:

```text
PURCHASE_PRICE
USER_ESTIMATE
FORMAL_VALUATION
AGENT_APPRAISAL
AUTOMATED_ESTIMATE
SALE_PRICE
SCENARIO_VALUE
```

### Ownership

Support multiple owners and dated changes.

```text
property_ownership_interests
----------------------------
id
property_id
owner_type
person_id nullable
external_owner_name nullable
ownership_percentage
effective_from
effective_to nullable
notes
```

Owner types may initially include:

```text
PERSON
HOUSEHOLD
COMPANY
TRUST
RETIREMENT_FUND
EXTERNAL_PARTY
OTHER
```

Total ownership for a given date should normally equal 100%, but the application should allow incomplete historical records with a warning.

---

## 8. Backdated property setup

Creating a property must support historical entry.

### Property creation modes

#### Current snapshot mode

For users who only know:

- current value;
- current loan balance;
- current status;
- approximate purchase date.

#### Full historical mode

For users who know:

- purchase contract and settlement dates;
- purchase price;
- original deposit;
- purchase costs;
- original loans;
- valuations;
- status changes;
- rental history;
- refinance history;
- capital improvements;
- sale details.

### Backdating requirements

Users must be able to:

- create a property with a purchase date before application installation;
- create a loan with a historical settlement date;
- add historical status events;
- add historical rent changes;
- add historical valuations;
- add historical loan rate and repayment changes;
- add historical expenses;
- add historical ownership changes.

### Baseline snapshots

Where complete transaction history is unavailable, support a dated baseline snapshot:

```text
property_baselines
------------------
id
property_id
baseline_date
property_value
loan_balance_total
status_id
accumulated_cost_base nullable
notes
```

Projection calculations begin from the most recent valid baseline plus later events.

The UI must clearly distinguish:

- observed historical values;
- user estimates;
- projected values.

---

## 9. Event-driven timeline

Use events to represent changes over time rather than overwriting history.

### General event table

```text
financial_events
----------------
id
household_id
event_type_id
effective_at
recorded_at
property_id nullable
loan_id nullable
person_id nullable
account_id nullable
scenario_id nullable
amount nullable
percentage nullable
payload jsonb
notes
is_planned
is_enabled
created_by_user_id
created_at
updated_at
```

### Initial event types

```text
HOUSEHOLD_MEMBER_ADDED
HOUSEHOLD_MEMBER_REMOVED
INCOME_STARTED
INCOME_CHANGED
INCOME_ENDED
PROPERTY_PURCHASED
PROPERTY_STATUS_CHANGED
PROPERTY_VALUED
PROPERTY_SOLD
PROPERTY_TRANSFERRED
OWNERSHIP_CHANGED
RENT_STARTED
RENT_CHANGED
RENT_ENDED
PROPERTY_EXPENSE_CHANGED
SPECIAL_LEVY
LOAN_OPENED
LOAN_RATE_CHANGED
LOAN_REPAYMENT_CHANGED
LOAN_REFINANCED
LOAN_LUMP_SUM_PAID
LOAN_OFFSET_CHANGED
LOAN_CLOSED
RETIREMENT_BALANCE_ADJUSTED
RETIREMENT_CONTRIBUTION_CHANGED
HOUSEHOLD_EXPENSE_CHANGED
ASSET_VALUE_CHANGED
LIABILITY_CHANGED
CUSTOM_EVENT
```

### Timeline resolution

For any requested date:

1. Select a valid baseline.
2. Load enabled events after the baseline and on or before the requested date.
3. Sort by `effective_at`, then deterministic event priority.
4. Apply each event.
5. Produce resolved state.
6. Calculate period outputs.
7. Identify whether each result is historical, current or projected.

### Planned events

Planned events must:

- be visually distinct;
- be enableable or disableable;
- be editable without modifying observed history;
- work inside scenarios;
- support moving an event to another date.

---

## 10. Rental model

### Rental profile

```text
rental_profiles
---------------
id
property_id
display_name
effective_from
effective_to nullable
market_rent_amount nullable
charged_rent_amount
frequency
vacancy_rate
management_fee_rate
letting_fee nullable
rental_share_percentage
notes
```

A property may have multiple named rental portions active at once, such as a room, granny flat,
or the other half of a duplex. Each portion has its own dated rent and rental share. Concurrent
shares must not exceed 100%. This supports a household occupying one part of a home while renters
occupy another part without treating the household as a property business.

### Rental activation

Rental income is controlled by resolved property status behaviour.

```python
if not status.generates_rental_income:
    gross_rent = 0
    vacancy_cost = 0
    management_fee = 0
else:
    gross_rent = charged_rent_for_period * rental_share_percentage
    vacancy_cost = gross_rent * vacancy_rate if status.applies_vacancy else 0
    management_fee = (
        gross_rent - vacancy_cost
    ) * management_fee_rate if status.applies_management_fee else 0
```

### Partial rental

Support:

- renting one room;
- renting a granny flat;
- mixed owner-occupied and rental use;
- partial-year rental;
- rental share percentage.

### Market rent and chosen rent

Market rent is informational.

Charged rent drives financial calculations.

Display:

```text
market rent
charged rent
discount or premium
annual difference
```

Do not describe a voluntary discount as an optimisation failure.

---

## 11. Loans and finance

### Multiple loans per property

A property may have:

- one mortgage;
- split fixed and variable loans;
- an equity loan;
- a construction loan;
- a line of credit;
- no loan.

### Loan schema

```text
loans
-----
id
household_id
property_id nullable
display_name
lender nullable
account_reference_masked nullable
loan_type_id
currency
original_balance nullable
opening_balance
opening_balance_date
term_months nullable
interest_calculation_method
repayment_frequency
is_active
notes
created_at
updated_at
```

### Loan components

For split loans, use separate loan records linked through an optional group:

```text
loan_groups
-----------
id
household_id
display_name
property_id nullable
```

### Loan event data

Support:

- interest-rate changes;
- repayment changes;
- lump sums;
- offsets;
- redraw;
- refinancing;
- term changes;
- interest-only periods;
- closure.

### Historical setup

Users may enter either:

1. every historical loan event; or
2. an opening balance at a chosen date, followed by later events.

### Mortgage calculations

Support:

- daily or monthly interest calculation configuration;
- weekly, fortnightly and monthly repayments;
- principal and interest;
- interest only;
- offset accounts;
- redraw balances;
- lump sums;
- rate changes;
- refinancing;
- re-amortised minimum repayment;
- payoff date;
- interest paid;
- interest saved against a selected baseline.

Do not assume a `$500/week` target globally.

Targets must be configurable per household or per loan.

---

## 12. Configurable goals and targets

### Goal types

Initial types:

```text
MAXIMUM_WEEKLY_REPAYMENT
TARGET_LOAN_BALANCE
TARGET_PAYOFF_DATE
TARGET_PURCHASE_DATE
TARGET_PURCHASE_PRICE
EMERGENCY_FUND_MONTHS
MAXIMUM_HOUSING_RATIO
COMFORTABLE_HOUSING_RATIO
TARGET_RETIREMENT_BALANCE
TARGET_MONTHLY_SURPLUS
CUSTOM_NUMERIC
CUSTOM_DATE
CUSTOM_BOOLEAN
```

### Goal schema

```text
goals
-----
id
household_id
person_id nullable
property_id nullable
loan_id nullable
goal_type_id
display_name
target_amount nullable
target_percentage nullable
target_date nullable
target_boolean nullable
priority
is_active
notes
```

A user may define a loan target such as:

```text
Re-amortised repayment <= $500/week
```

This should be configured rather than hard-coded.

---

## 13. Income and tax

### Income sources

A person may have multiple dated income sources.

```text
income_sources
--------------
id
person_id
income_type_id
display_name
gross_amount
frequency
salary_sacrifice_amount nullable
annual_growth_rate nullable
effective_from
effective_to nullable
taxable
notes
```

Initial income types:

```text
SALARY
WAGES
BONUS
OVERTIME
CONTRACTING
BUSINESS
RENTAL_DISTRIBUTION
PENSION
GOVERNMENT_PAYMENT
INVESTMENT_INCOME
OTHER_TAXABLE
OTHER_NON_TAXABLE
```

### Jurisdiction-aware tax engine

Tax calculations must be modular.

```text
tax/
  base.py
  australia.py
  registry.py
```

The shared income and cash-flow services must depend only on jurisdiction-neutral tax contracts.
Country-specific parameters belong in the tax profile's `settings.parameters` JSON object. Tax
providers map dates to their own tax years, validate their own parameters, and return generic named
calculation components. The Australian implementation is the bundled working example and is
versioned by financial year.

Additional tax providers may be supplied by installed Python packages through the
`household_financial_planner.tax_providers` entry-point group. Adding a jurisdiction must not
require changes to the income service, shared response schemas, or database schema.

Tax outputs are planning estimates, not tax advice. Each implementation must identify its source
financial year, reject unsupported years rather than silently reuse old rules, expose material
limitations, and allow a person to replace automatic tax with an explicit manual net-income
amount.

A household must be able to disable automatic tax calculation and enter net income manually.

### Tax profile

```text
person_tax_profiles
-------------------
id
person_id
jurisdiction
tax_year
settings jsonb
effective_from
effective_to nullable
```

For Australia, settings may include:

- resident status;
- HELP debt settings;
- Medicare levy settings;
- Medicare levy surcharge;
- salary sacrifice;
- deductions estimate;
- manual override.

---

## 14. Retirement and superannuation accounts

Use generic retirement accounts with jurisdiction-specific account types.

### Account types

Initial values:

```text
AUSTRALIAN_SUP
DEFINED_BENEFIT
PENSION_ACCOUNT
RETIREMENT_SAVINGS
EMPLOYER_PLAN
SELF_MANAGED_SUP_FUND
OTHER
```

### Schema

```text
retirement_accounts
-------------------
id
household_id
person_id nullable
display_name
account_type_id
currency
opening_balance
opening_balance_date
expected_return_rate
annual_fees
is_active
notes
```

### Contribution profiles

```text
retirement_contribution_profiles
--------------------------------
id
retirement_account_id
effective_from
effective_to nullable
employer_rate nullable
employer_amount nullable
voluntary_pre_tax_amount nullable
voluntary_post_tax_amount nullable
contribution_tax_rate nullable
annual_pre_tax_cap nullable
```

### Projection requirements

Support:

- opening balance;
- dated balance adjustments;
- employer contributions;
- voluntary contributions;
- contribution tax;
- fees;
- earnings;
- retirement age;
- drawdown in a future phase.

---

## 15. Other financial records

### Household expenses

```text
household_expenses
------------------
id
household_id
person_id nullable
category_id
display_name
amount
frequency
annual_growth_rate nullable
effective_from
effective_to nullable
is_essential
notes
```

### Assets

```text
assets
------
id
household_id
owner_person_id nullable
asset_type_id
display_name
currency
opening_value
opening_value_date
notes
```

### Liabilities

```text
liabilities
-----------
id
household_id
owner_person_id nullable
liability_type_id
display_name
currency
opening_balance
opening_balance_date
interest_rate nullable
notes
```

---

## 16. Calculation services

Create isolated calculation modules:

```text
calculations/
  dates.py
  money.py
  tax/
  loans/
  property_values.py
  rental.py
  retirement.py
  household_cashflow.py
  purchase_feasibility.py
  ownership.py
  scenarios.py
  timeline.py
```

### General calculation contract

Every projection response should include:

```json
{
  "calculation_date": "2035-01-01",
  "currency": "AUD",
  "scenario_id": null,
  "values": {},
  "assumptions_used": [],
  "warnings": [],
  "data_quality": {
    "historical": true,
    "contains_estimates": true,
    "contains_projections": false
  }
}
```

### Data quality flags

Track whether a value is:

```text
OBSERVED
USER_ENTERED
ESTIMATED
CALCULATED
PROJECTED
SCENARIO_OVERRIDE
```

---

## 17. Scenario engine

### Scenarios are household-specific

A scenario should contain overrides and planned-event changes.

Examples should be generated from a template library rather than hard-coded household assumptions.

Template scenarios:

```text
Higher interest rates
Lower income
Higher household expenses
Delayed property purchase
Earlier property purchase
Property vacant for a period
Major maintenance cost
Lower property growth
Higher property growth
Retirement contribution change
Custom
```

### Scenario schema

```text
scenarios
---------
id
household_id
display_name
description
base_scenario_id nullable
is_active
created_at
updated_at
```

```text
scenario_overrides
------------------
id
scenario_id
target_entity_type
target_entity_id nullable
effective_from
effective_to nullable
override_key
value_json
```

### Comparison

Allow:

- current plan versus scenario;
- scenario A versus scenario B;
- selected metrics;
- selected date range.

---

## 18. API structure

### Authentication and households

```text
GET    /me
GET    /households
POST   /households
GET    /households/{household_id}
PUT    /households/{household_id}
GET    /households/{household_id}/memberships
POST   /households/{household_id}/memberships
```

### People

```text
GET    /households/{household_id}/people
POST   /households/{household_id}/people
GET    /people/{person_id}
PUT    /people/{person_id}
DELETE /people/{person_id}
```

### Properties

```text
GET    /households/{household_id}/properties
POST   /households/{household_id}/properties
GET    /properties/{property_id}
PUT    /properties/{property_id}
POST   /properties/{property_id}/valuations
POST   /properties/{property_id}/status-events
POST   /properties/{property_id}/ownership
GET    /properties/{property_id}/timeline
GET    /properties/{property_id}/cashflow
GET    /properties/{property_id}/rental-profiles
POST   /properties/{property_id}/rental-profiles
GET    /properties/{property_id}/expenses
POST   /properties/{property_id}/expenses
```

### Loans

```text
GET    /households/{household_id}/loans
POST   /households/{household_id}/loans
GET    /loans/{loan_id}
PUT    /loans/{loan_id}
POST   /loans/{loan_id}/events
GET    /loans/{loan_id}/schedule
POST   /loans/{loan_id}/target-calculation
```

### Income, expenses and tax

```text
GET    /people/{person_id}/income-sources
POST   /people/{person_id}/income-sources
GET    /people/{person_id}/tax-profiles
POST   /people/{person_id}/tax-profiles
GET    /households/{household_id}/expenses
POST   /households/{household_id}/expenses
POST   /calculations/tax
GET    /households/{household_id}/income-projection
GET    /households/{household_id}/cashflow
```

### Retirement accounts

```text
GET    /households/{household_id}/retirement-accounts
POST   /households/{household_id}/retirement-accounts
PUT    /retirement-accounts/{account_id}
POST   /retirement-accounts/{account_id}/events
GET    /retirement-accounts/{account_id}/projection
```

### Dashboard and timeline

```text
GET /households/{household_id}/dashboard
GET /households/{household_id}/projection
GET /households/{household_id}/timeline
```

### Scenarios

```text
GET    /households/{household_id}/scenarios
POST   /households/{household_id}/scenarios
GET    /scenarios/{scenario_id}
PUT    /scenarios/{scenario_id}
DELETE /scenarios/{scenario_id}
POST   /scenarios/{scenario_id}/calculate
POST   /scenarios/compare
```

---

## 19. Appsmith page structure

### 19.1 Household selector

For users belonging to multiple households.

### 19.2 Onboarding wizard

Dynamic steps based on what the household owns or wants to track.

### 19.3 Dashboard

Configurable cards:

- take-home income;
- monthly surplus;
- emergency-fund coverage;
- property value;
- property debt;
- property equity;
- retirement balances;
- active goals;
- upcoming events.

Users should be able to hide irrelevant cards.

### 19.4 People

Display configurable person cards.

No fixed two-column assumption.

Use responsive cards and an “Add person” action.

### 19.5 Properties

Display:

- property cards;
- table view;
- filters by status, type and ownership;
- “Add property” action;
- historical import option.

### 19.6 New property wizard

Steps:

1. Identity and property type.
2. Address or general location.
3. Ownership.
4. Purchase or baseline date.
5. Value history.
6. Status history.
7. Loans.
8. Rental profile.
9. Expenses.
10. Review and create.

Allow users to skip unknown sections.

### 19.7 Property detail

Tabs:

```text
Overview
Timeline
Ownership
Values
Loans
Rental
Expenses
Documents later
Scenarios
```

### 19.8 Loans

Loan list and loan detail pages.

Allow configurable financial targets.

### 19.9 Purchase planner

Do not assume the next purchase is a home or in a particular location.

Inputs:

- purchase type;
- target location;
- target price range;
- intended use;
- ownership;
- target date;
- deposit;
- costs;
- funding sources;
- desired buffer.

### 19.10 Retirement

Support any number of retirement accounts and people.

### 19.11 Timeline

Unified historical and planned timeline.

Allow:

- filtering;
- editing planned dates;
- enabling and disabling planned events;
- identifying observed versus projected entries.

### 19.12 Scenarios

Template-based and custom scenarios.

### 19.13 Settings

Configure:

- currency;
- locale;
- tax jurisdiction;
- date format;
- financial year;
- calculation defaults;
- status behaviours;
- property types;
- household roles.

---

## 20. Visual design requirements

The interface should be:

- welcoming;
- non-technical;
- visually calm;
- responsive;
- accessible;
- suitable for users who dislike spreadsheets.

Use:

- large summary cards;
- charts;
- plain-language labels;
- progressive disclosure;
- helpful empty states;
- tooltips;
- onboarding prompts;
- clear historical/projected styling.

Suggested visual states:

```text
Observed history: solid neutral
User estimate: dotted neutral
Current: strong blue
Planned: purple or blue outline
Projected: lighter blue
Comfortable: green
Caution: amber
Warning: red
Inactive: grey
```

Do not use language that assumes wealth maximisation is the user's goal.

---

## 21. Repository structure

```text
open-household-finance/
├── README.md
├── PROJECT_PLAN.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── architecture.md
│   ├── calculation-engine.md
│   ├── data-model.md
│   ├── event-model.md
│   ├── backdated-setup.md
│   ├── deployment-truenas.md
│   ├── security.md
│   └── user-guide.md
├── database/
│   ├── migrations/
│   ├── seed/
│   │   ├── lookup_data.py
│   │   └── optional_demo_household.py
│   └── schema-reference.sql
├── api/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── auth/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── calculations/
│   │   └── tests/
│   └── alembic/
├── appsmith/
│   ├── export/
│   └── setup-guide.md
├── scripts/
│   ├── backup.sh
│   ├── restore.sh
│   ├── create_demo_household.py
│   └── import_template.py
└── tests/
    ├── fixtures/
    └── integration/
```

---

## 22. Open-source project requirements

### Licensing

Choose an OSI-approved licence before public release.

Suggested options:

- AGPL-3.0 for ensuring hosted modifications remain open;
- GPL-3.0 for strong copyleft;
- Apache-2.0 for permissive commercial reuse with patent protection.

Document the choice.

### Contribution readiness

Include:

- contribution guide;
- code of conduct;
- issue templates;
- pull-request template;
- architecture decision records;
- migration policy;
- calculation test requirements;
- security reporting process.

### Privacy

The application must:

- default to local storage;
- avoid telemetry unless explicitly enabled;
- avoid storing bank credentials;
- avoid sending financial data to third parties;
- clearly document any optional external integrations.

---

## 23. Testing requirements

### Household isolation

Test that:

- users cannot access households without membership;
- viewers cannot edit;
- records cannot be moved across households accidentally.

### Configurable people

Test:

- zero-person onboarding;
- one-person household;
- two-person household;
- more than two people;
- inactive people;
- person without an application login.

### Property tests

Test:

- every initial property type;
- custom property type;
- multiple owners;
- ownership changes;
- historical purchase;
- current snapshot baseline;
- full history;
- status changes;
- property with no loan;
- multiple loans;
- sold property;
- planned property.

### Rental tests

Test:

- no rent before rental status starts;
- backdated rental period;
- future rental period;
- partial rental;
- family occupancy with configurable rent;
- vacant status;
- management fees only when configured;
- chosen rent versus market rent.

### Loan tests

Test:

- historical opening balance;
- full amortisation history;
- multiple repayment frequencies;
- offsets;
- refinancing;
- target calculations;
- property-independent personal loan.

### Timeline tests

Test:

- event ordering;
- same-day event priority;
- disabled events;
- planned events;
- scenario overrides;
- baseline selection;
- historical versus projected flags.

### Import and backdating tests

Test:

- incomplete historical data;
- baseline-only entry;
- later addition of older events;
- recalculation after backdated correction;
- duplicate event prevention.

---

## 24. Implementation phases

### Phase 0 — Repository bootstrap

Deliver directly to `main` as the initial commit:

- initialise the Git repository and public GitHub repository;
- retain this project plan as the governing specification;
- add a short README describing the purpose, planned stack and project status;
- establish the GPL-3.0 licensing decision;
- document that tests and evaluation metrics are mandatory for every implementation phase.

Phase 0 does not require its own branch or pull request because it creates the repository and the baseline from which reviewed work begins.

### Completion standard for every implementation phase

Every phase from Phase 1 onward must define and satisfy:

- Python 3.14 for the API runtime, tests and static-analysis tooling;
- `pydantic-settings` as the single typed boundary for environment configuration;
- `structlog` for structured application and request logging, including request correlation;
- automated unit tests for new business logic;
- integration tests for new database, migration and API behaviour;
- regression tests for defects discovered during the phase;
- access-control and household-isolation tests for every affected resource;
- explicit acceptance criteria mapped to the phase deliverables;
- measurable evaluation metrics covering correctness, test coverage, performance, reliability or usability as appropriate;
- recorded test and evaluation results in the pull request;
- CI quality gates appropriate to the changed components.

Until the first stable v1.0 release, database migrations are forward-only. Each phase must
prove that the previously supported schema upgrades to the new head and that Alembic reports
no schema drift. Downgrade functions may remain as best-effort development conveniences, but
downgrade compatibility, data preservation and downgrade tests are not release gates. The v1.0
release process must establish and test an explicit production rollback and migration-support
policy before later versions are published.

A phase is not complete, and its pull request must not be merged, when required tests are absent, failing or bypassed, or when its agreed evaluation thresholds are not met. Documentation-only changes must still pass documentation, link and repository-policy checks.

### Phase 1 — Generic foundation

Deliver:

- repository;
- Docker Compose;
- PostgreSQL;
- FastAPI;
- migrations;
- authentication boundary;
- household records;
- memberships;
- configurable people;
- configurable lookup tables;
- health checks.

Do not seed user-specific records.

### Phase 2 — Generic property and ownership model

Deliver:

- property types;
- property statuses with behavioural flags;
- properties;
- valuations;
- ownership interests;
- backdated property wizard APIs;
- baseline snapshots.

### Phase 3 — Event and timeline engine

Deliver:

- financial events;
- event resolution;
- observed/planned/projected flags;
- timeline API;
- planned event toggles.

### Phase 4 — Loans

Deliver:

- multiple loans per property;
- historical opening balances;
- loan events;
- schedules;
- offsets;
- refinancing;
- configurable loan goals.

### Phase 5 — Rental and property expenses

Deliver:

- status-driven rental activation;
- rental profiles;
- partial rental;
- expenses;
- historical and future rent changes.

### Phase 6 — People, income and tax

Deliver:

- multiple income sources;
- configurable people;
- tax engine interface;
- provider registry and external-provider scaffold;
- Australian example implementation;
- manual net-income option;
- household cash flow.

### Phase 7 — Retirement accounts

Deliver:

- generic retirement accounts;
- Australian super profile;
- contributions;
- fees;
- projection.

Acceptance requires dated contribution profiles, idempotent balance adjustments, household
isolation, explicit projection assumptions, and tested calculations for opening balance,
contributions, contribution tax, fees, earnings and caps. Australian super settings must remain in
an optional provider implementation selected through generic account settings, rather than fields,
defaults or branches in the shared engine.

### Phase 7A — Cross-cutting jurisdiction modularity audit

Before Phase 8 begins, audit completed services for country-specific branches, field names,
defaults and calculation rules. Shared services must use neutral contracts and provider registries;
Australia remains a bundled example implemented outside shared orchestration. External providers
must be registerable through Python entry points without editing shared services, schemas or
database structures. Apply this review to every later phase as part of its completion criteria.
The consolidated rules are maintained in `docs/architecture-principles.md` and apply to both new
work and cross-cutting reviews of completed phases.

### Phase 8 — Purchase planner

Deliver:

- configurable purchase type;
- funding sources;
- ownership;
- costs;
- comfort thresholds;
- feasibility projection.

Purchase costs that vary by country or scheme must use the generic purchase-provider registry.
Shared models store only provider code/settings and generic named cost components. Australia is a
bundled user-configured example and must never be inferred from currency, household jurisdiction
or location. A non-Australian provider contract test is required for completion.

### Phase 9 — Scenarios and comparison

Deliver:

- templates;
- custom scenarios;
- side-by-side comparison;
- event overrides.

Scenarios are household-owned, dated layers over caller-supplied baseline metrics and planned
events. A scenario may inherit from another scenario in the same household, with a maximum depth
and cycle protection. Overrides use neutral target, key, operation and JSON value fields; shared
scenario orchestration must not infer a country from currency, jurisdiction or location.

The bundled template library provides editable starting points for common personal-finance
questions. Templates contain no country-specific rules. Future jurisdiction-specific template
packages must use an extension boundary rather than branches in the shared scenario engine.

Acceptance requires tested custom and template creation, effective-date filtering, deterministic
base-scenario inheritance, baseline-to-scenario and scenario-to-scenario comparison, non-mutating
planned-event overrides, household isolation, role enforcement, forward migration and schema-drift
checks. A 1,000-override calculation must remain below 100 ms p95 over 100 local runs.

### Post-Phase 9 — Cross-cutting architecture alignment

Before frontend implementation, reconcile completed backend work with the priorities established
during Phases 1–9. This is a maintenance checkpoint rather than a product phase. It must:

- maintain the consolidated architecture principles;
- remove country-specific terminology from shared ownership types;
- route every bundled country example through the same neutral provider boundary as extensions;
- require financially material purchase assumptions instead of silently defaulting them;
- remove the implicit 30-year term from open-ended loan projections; and
- disclose day-count assumptions used by current loan and rental calculations.

Acceptance requires forward migration and drift checks, preservation of existing enum data through
the neutral rename, full regression tests, architecture boundary tests, and updated measured results.

### Phase 10 — Appsmith user experience

Deliver:

- onboarding;
- responsive dashboard;
- people;
- properties;
- property wizard;
- timeline;
- scenarios;
- settings.

### Phase 11 — Open-source release readiness

Deliver:

- licence;
- contribution documentation;
- demo mode;
- upgrade documentation;
- backup and restore;
- security guide;
- release workflow.

---

## 25. Initial Codex prompts

### Prompt 1 — Generic foundation

```text
Read PROJECT_PLAN.md before making changes.

Implement Phase 1 only for a reusable open-source household financial planning application.

Requirements:
1. Create the repository structure.
2. Add Docker Compose services for PostgreSQL, FastAPI and Appsmith Community Edition.
3. Add SQLAlchemy and Alembic.
4. Implement application users, households and household memberships.
5. Implement configurable people records.
6. Implement lookup tables for:
   - property types;
   - property statuses;
   - loan types;
   - income types;
   - retirement account types.
7. Property status lookup records must include behavioural flags rather than relying on status-name string comparisons.
8. Add household-level access-control checks.
9. Create .env.example.
10. Add health endpoints and basic tests.
11. Do not seed named people, real properties or financial values.
12. Add an optional fictional demo-data script, but do not run it automatically.
13. Use British English in documentation.

Do not implement financial calculations or Appsmith pages yet.
```

### Prompt 2 — Generic property and backdating model

```text
Read PROJECT_PLAN.md and complete Phase 2 only.

Implement:
- properties;
- configurable property types;
- configurable property statuses;
- dated valuations;
- ownership interests;
- multiple owners;
- baseline snapshots;
- historical purchase entry;
- current-snapshot entry;
- validation and warnings for incomplete ownership totals;
- APIs for a backdated property setup wizard.

A property must not require a loan, rental profile or complete address.
Do not hard-code any location, property name or number of properties.
Add unit and integration tests.
```

### Prompt 3 — Event engine

```text
Read PROJECT_PLAN.md and complete Phase 3 only.

Implement:
- financial event types;
- financial events;
- event ordering;
- event enable/disable;
- planned versus observed events;
- baseline resolution;
- state resolution at an arbitrary date;
- a unified household timeline API;
- data-quality flags.

Add tests for:
- backdated events;
- future events;
- disabled planned events;
- same-day event ordering;
- adding an older event after newer records exist.
```

### Prompt 4 — Status-driven rental

```text
Read PROJECT_PLAN.md and implement the rental portion of Phase 5.

Rental behaviour must be driven by status behavioural flags, not by status names.

Requirements:
- no rental income when generates_rental_income is false;
- vacancy only when applies_vacancy is true;
- management fees only when applies_management_fee is true;
- support partial rental using rental_share_percentage;
- support historical and future rental profiles;
- support market rent and charged rent separately;
- support backdated rental commencement and cessation;
- expose property rental cash flow for any requested date range.

Add comprehensive tests.
```

---

## 26. Migration from a spreadsheet

A spreadsheet importer may be added later.

Import only:

- user-entered values;
- explicit assumptions;
- dated historical records;
- named goals;
- decision-log entries.

Do not import spreadsheet formula results as permanent source-of-truth records.

The import workflow should:

1. preview records;
2. map columns;
3. identify missing dates;
4. detect duplicates;
5. allow baseline creation where history is incomplete;
6. show warnings;
7. require confirmation before saving.

---

## 27. Definition of done for first public beta

The beta is complete when a new user can:

1. Install the application with Docker Compose.
2. Create an empty household.
3. Add any number of people.
4. Add a property of any configured type.
5. Enter a property purchased in the past.
6. Enter only a current baseline when older details are unavailable.
7. Add multiple owners and ownership shares.
8. Add zero, one or multiple loans.
9. Add historical and future property statuses.
10. Confirm rent is calculated only when status behaviour permits it.
11. Add income sources for any person.
12. See household cash flow.
13. Add retirement accounts.
14. Define custom goals.
15. Create and compare scenarios.
16. View a historical and projected timeline.
17. Back up and restore the application.
18. Invite another application user with a chosen household role.
19. Use an optional fictional demo household.
20. Delete all demo data without affecting production data.

---

## 28. Non-goals for version 1

Do not build:

- automatic banking login;
- automatic tax-return preparation;
- lender approval guarantees;
- automated property-price scraping;
- unlimited accounting features;
- public multi-tenant SaaS billing;
- wealth-maximisation recommendations;
- forced rent-growth assumptions;
- automatic legal or tax advice;
- jurisdiction support beyond the initial implemented modules.

The architecture should permit later additions without pretending they are already supported.

---

## 29. Future enhancements

Possible later features:

- CSV and OFX transaction imports;
- Actual Budget integration;
- Open Banking integration;
- document storage;
- insurance and renewal reminders;
- maintenance schedules;
- property co-owner reporting;
- trusts and company ownership;
- capital-gains cost-base tracking;
- depreciation schedules;
- retirement drawdown;
- estate-planning notes;
- inflation-adjusted reports;
- Monte Carlo projections;
- localisation and additional currencies;
- additional country tax modules;
- native frontend replacing Appsmith;
- mobile application.

These should be added only after the core event and calculation model is stable.
