# React v2 API parity matrix

This is the FastAPI route inventory at the start of the React migration. A route is
complete when its owner provides an ordinary React workflow or, for infrastructure,
a tested shared-client integration. A test compares this table with the application
decorators, so route changes require an intentional matrix update.

| Method | API route | React responsibility | Owner |
| --- | --- | --- | --- |
| GET | `/health/live` | API liveness | #39 |
| GET | `/api/v1/system/status` | Authenticated API and database readiness | #39 |
| GET | `/api/v1/me` | Current migration identity | #55 |
| GET | `/api/v1/auth/status` | Local-auth bootstrap status | #31 |
| POST | `/api/v1/auth/bootstrap` | First local administrator | #31 |
| POST | `/api/v1/auth/login` | Local session creation | #31 |
| POST | `/api/v1/auth/logout` | Local session revocation | #31 |
| GET | `/api/v1/auth/session` | Current local session | #31 |
| POST | `/api/v1/auth/password/change` | Authenticated password change | #31 |
| POST | `/api/v1/auth/password/reset` | One-time local password reset | #33 |
| GET | `/api/v1/admin/users` | Local account administration list | #33 |
| POST | `/api/v1/admin/users` | Local account creation | #33 |
| PATCH | `/api/v1/admin/users/{user_id}` | Local account and role update | #33 |
| POST | `/api/v1/admin/users/{user_id}/password-reset` | Reset-link issuance | #33 |
| GET | `/api/v1/admin/legacy-identities` | Legacy identity list and unresolved count | #35 |
| POST | `/api/v1/admin/legacy-identities/review` | Persist an administrator's cutover review and exact unresolved identities | #36 |
| GET | `/api/v1/admin/legacy-identities/reviews` | Audited migration review history | #36 |
| POST | `/api/v1/admin/legacy-identities/reconcile` | Final legacy membership reconciliation | #35 |
| POST | `/api/v1/admin/legacy-identities/{legacy_identity_id}/mapping` | Legacy identity mapping | #35 |
| DELETE | `/api/v1/admin/legacy-identities/{legacy_identity_id}/mapping` | Audited mapping revocation | #35 |
| GET | `/api/v1/admin/legacy-identities/{legacy_identity_id}/mapping-history` | Mapping audit history | #35 |
| GET | `/api/v1/households` | Household list and restoration | #38 |
| POST | `/api/v1/households` | Household creation | #38 |
| GET | `/api/v1/households/{household_id}` | Selected household | #38 |
| GET | `/api/v1/households/{household_id}/access` | Current member role and capabilities | #40 |
| GET | `/api/v1/households/{household_id}/memberships` | Membership list | #37, #38 |
| POST | `/api/v1/households/{household_id}/memberships` | Membership creation | #37, #38 |
| PATCH | `/api/v1/households/{household_id}/memberships/{membership_id}` | Membership role update | #37, #38 |
| DELETE | `/api/v1/households/{household_id}/memberships/{membership_id}` | Membership removal | #37, #38 |
| GET | `/api/v1/households/{household_id}/people` | People list | #40 |
| POST | `/api/v1/households/{household_id}/people` | Person creation | #40 |
| GET | `/api/v1/lookups/{category}` | Shared reference controls | #39 |
| GET | `/api/v1/reference/countries` | Country controls | #39 |
| GET | `/api/v1/reference/currencies` | Currency controls | #39 |
| GET | `/api/v1/people/{person_id}/income-sources` | Income-source list | #41 |
| POST | `/api/v1/people/{person_id}/income-sources` | Dated income creation | #41 |
| GET | `/api/v1/people/{person_id}/tax-profiles` | Tax-profile list | #41 |
| POST | `/api/v1/people/{person_id}/tax-profiles` | Tax-profile creation | #41 |
| GET | `/api/v1/tax-providers` | Provider and year discovery | #41 |
| POST | `/api/v1/calculations/tax` | Standalone tax calculation | #41 |
| GET | `/api/v1/households/{household_id}/expenses` | Household-expense list | #42 |
| POST | `/api/v1/households/{household_id}/expenses` | Dated household expense | #42 |
| PATCH | `/api/v1/households/{household_id}/expenses/{expense_id}` | Correct household expense | #42 |
| DELETE | `/api/v1/households/{household_id}/expenses/{expense_id}` | Remove household expense | #42 |
| GET | `/api/v1/households/{household_id}/income-projection` | Compatibility cash-flow alias | #42 |
| GET | `/api/v1/households/{household_id}/cashflow` | Household cash flow | #42 |
| GET | `/api/v1/households/{household_id}/properties` | Property list | #43 |
| GET | `/api/v1/households/{household_id}/property-summaries` | Value and debt summaries | #43 |
| POST | `/api/v1/households/{household_id}/properties` | Property creation | #43 |
| POST | `/api/v1/households/{household_id}/properties/wizard` | Current or historical setup | #43 |
| GET | `/api/v1/properties/{property_id}` | Property detail | #43 |
| POST | `/api/v1/properties/{property_id}/valuations` | Dated valuation | #43 |
| POST | `/api/v1/properties/{property_id}/baselines` | Dated property baseline | #43 |
| GET | `/api/v1/properties/{property_id}/state` | Resolved state at a date | #43 |
| GET | `/api/v1/properties/{property_id}/ownership` | Ownership history | #44 |
| GET | `/api/v1/properties/{property_id}/ownership-position` | Ownership resolved at a date | #44 |
| POST | `/api/v1/properties/{property_id}/ownership` | Dated ownership interests | #44 |
| PATCH | `/api/v1/properties/{property_id}/ownership/{ownership_id}` | Correct or close ownership | #44 |
| GET | `/api/v1/properties/{property_id}/rental-profiles` | Rental-profile list | #44 |
| POST | `/api/v1/properties/{property_id}/rental-profiles` | Whole or partial rental profile | #44 |
| PATCH | `/api/v1/properties/{property_id}/rental-profiles/{profile_id}` | Correct or end a rental profile | #44 |
| GET | `/api/v1/properties/{property_id}/expenses` | Property-expense list | #44 |
| POST | `/api/v1/properties/{property_id}/expenses` | Dated property expense | #44 |
| PATCH | `/api/v1/properties/{property_id}/expenses/{expense_id}` | Correct or end a property expense | #44 |
| DELETE | `/api/v1/properties/{property_id}/expenses/{expense_id}` | Remove a property expense | #44 |
| GET | `/api/v1/properties/{property_id}/cashflow` | Rental cash flow | #44 |
| GET | `/api/v1/households/{household_id}/loans` | Household loan list | #45 (React property workflow) |
| GET | `/api/v1/households/{household_id}/loan-groups` | Split-loan group catalogue | #99, #100 |
| POST | `/api/v1/households/{household_id}/loan-groups` | Split-loan group creation | #99, #100 |
| POST | `/api/v1/households/{household_id}/loans` | Loan creation | #45 (React property workflow) |
| GET | `/api/v1/loans/{loan_id}` | Loan detail | #45 |
| PATCH | `/api/v1/loans/{loan_id}` | Audited loan correction | #45 (React property workflow) |
| POST | `/api/v1/loans/{loan_id}/close` | Dated, audited loan closure | #45 (React property workflow) |
| GET | `/api/v1/properties/{property_id}/loan-debt-reconciliation` | Dated linked-loan and recorded-debt comparison | #94 |
| GET | `/api/v1/loans/{loan_id}/repayment-responsibilities` | Responsibility history | #45 |
| POST | `/api/v1/loans/{loan_id}/repayment-responsibilities` | Advanced responsibility override | #45 |
| POST | `/api/v1/loans/{loan_id}/events` | Dated loan event | #46 |
| GET | `/api/v1/loans/{loan_id}/schedule` | Amortisation schedule | #46 |
| POST | `/api/v1/loans/{loan_id}/refinance` | Refinancing | #46 |
| GET | `/api/v1/households/{household_id}/goals` | Loan-goal list | #46 |
| POST | `/api/v1/households/{household_id}/goals` | Household loan goal | #46 |
| POST | `/api/v1/loans/{loan_id}/target-calculation` | Target calculation | #46 |
| GET | `/api/v1/households/{household_id}/purchase-plans` | Purchase-plan list | #47 |
| POST | `/api/v1/households/{household_id}/purchase-plans` | Plan and funding | #47 |
| POST | `/api/v1/purchase-plans/{plan_id}/calculate` | Purchase feasibility | #47 |
| GET | `/api/v1/purchase-providers` | Installed purchase-provider discovery | #39, #47 |
| GET | `/api/v1/retirement-providers` | Provider discovery | #48 |
| GET | `/api/v1/households/{household_id}/retirement-accounts` | Account list | #48 |
| POST | `/api/v1/households/{household_id}/retirement-accounts` | Account creation | #48 |
| PUT | `/api/v1/retirement-accounts/{account_id}` | Account update | #48 |
| GET | `/api/v1/retirement-accounts/{account_id}/contribution-profiles` | Contribution history | #49 |
| POST | `/api/v1/retirement-accounts/{account_id}/contribution-profiles` | Contribution profile | #49 |
| POST | `/api/v1/retirement-accounts/{account_id}/events` | Balance adjustment | #49 |
| GET | `/api/v1/retirement-accounts/{account_id}/projection` | Projection | #49 |
| GET | `/api/v1/event-types` | Event-type discovery | #50 |
| GET | `/api/v1/households/{household_id}/timeline` | Complete or filtered timeline | #50 |
| POST | `/api/v1/households/{household_id}/events` | Planned event creation | #50 |
| PATCH | `/api/v1/events/{event_id}` | Planned event update | #50 |
| PATCH | `/api/v1/events/{event_id}/enabled` | Enable or disable event | #50 |
| GET | `/api/v1/scenario-templates` | Scenario templates | #51 |
| GET | `/api/v1/households/{household_id}/scenarios` | Saved scenario list | #51 |
| POST | `/api/v1/households/{household_id}/scenarios` | Custom scenario creation | #51 |
| POST | `/api/v1/households/{household_id}/scenarios/from-template` | Template inheritance | #51 |
| GET | `/api/v1/scenarios/{scenario_id}` | Scenario detail | #51 |
| PUT | `/api/v1/scenarios/{scenario_id}` | Scenario update | #51 |
| DELETE | `/api/v1/scenarios/{scenario_id}` | Scenario deletion | #51 |
| POST | `/api/v1/scenarios/{scenario_id}/overrides` | Dated override | #51 |
| POST | `/api/v1/scenarios/{scenario_id}/calculate` | Scenario calculation | #52 |
| POST | `/api/v1/scenarios/compare` | Side-by-side comparison | #52 |

Authentication and membership mutations do not exist in this v1 inventory. Issues
#31, #33, #35 and #37 add them and must extend the matrix in the same pull requests.
