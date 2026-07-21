# Phase 6 Australian tax assumptions

The Phase 6 Australian engine provides a transparent planning estimate for the 2025–26 financial
year. It is not tax advice and is not intended to reproduce every field of an Australian tax
return.

Implemented rules:

- 2025–26 resident and foreign-resident individual income-tax brackets;
- the low income tax offset (LITO);
- an optional 2% Medicare levy;
- an explicitly supplied Medicare levy surcharge percentage;
- 2025–26 marginal study and training loan repayments;
- estimated deductions and reportable super contributions;
- manual annual net income as an alternative to automatic calculation.

Not yet modelled:

- Medicare levy low-income and family reductions or exemptions;
- automatic Medicare levy surcharge thresholds and private-health-cover rules;
- SAPTO and other individual offsets;
- capital gains, business concessions, foreign income, or detailed rental deductions;
- PAYG withholding and tax-return reconciliation.

The engine refuses unsupported years. A future financial year requires a separate implementation
and boundary tests before it becomes selectable.

Australia is the bundled example for the generic provider interface. Australian-only inputs are
validated from `settings.parameters`; the shared income service does not know their names. See
[Adding a tax provider](custom-tax-provider.md) for the external package scaffold.

Official sources consulted:

- [ATO resident tax rates and legislated brackets](https://www.ato.gov.au/law/view/document?DocNum=0000081364&FullDocument=true)
- [ATO foreign-resident rates](https://www.ato.gov.au/api/public/content/0-e7019e89-9b44-4034-ba9c-59ed0cf906ca)
- [ATO low income tax offset](https://www.ato.gov.au/api/public/content/0-2319183b-9958-4848-88f9-ea9dc64b121e)
- [ATO study and training loan repayment thresholds](https://www.ato.gov.au/tax-rates-and-codes/study-and-training-support-loans-rates-and-repayment-thresholds?page=1)
