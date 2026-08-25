# Post-2.0 Stake CGT working-paper utility

This experimental command-line utility is staged for redesign and integration after version 2.0.0.
It is intentionally not exposed through the API or frontend. It converts a directory of historical
Stake **Investment Activity** XLSX exports into a Markdown capital-gains working paper.

It is a record-checking aid, not tax or accounting advice. Review its output against contract notes,
issuer tax statements, corporate-action documents and advice appropriate to the taxpayer.

## Run it

Download the Investment Activity XLSX for every financial year from the first acquisition of any
security later sold. Put only those activity workbooks in one directory, then run from `api/`:

```bash
python -m scripts.stake_cgt /path/to/stake-activity \
  --financial-year 2025-26 \
  --output stake-cgt-2025-26.md
```

The report includes disposal proceeds, matched cost base, gain or loss, potentially discount-eligible
gross gains, trade identifiers, source rows and parcel-level working. A sale without sufficient prior
acquisitions is marked incomplete and excluded from totals instead of being reported as a zero-cost
gain.

## Current assumptions and boundaries

- Input is Stake's sectioned Investment Activity `.xlsx` format; PDFs are not accepted.
- Australian activity uses Stake's AUD total. Wall St activity is converted using the AUD/USD rate
  included in Stake's XLSX; because Stake displays this rate to three decimals, independently verify
  material foreign-currency results against contract notes or an accepted exchange-rate source.
- Tax parcels are matched FIFO. This is an explicit convenience assumption, not a claim that FIFO is
  required or optimal under Australian tax law.
- The tool does not infer demergers, splits, transfers, returns of capital, AMIT cost-base adjustments,
  dividend reinvestment or other corporate actions. Importing activity files alone cannot establish
  those facts.
- The output separates complete gross gains, capital losses and discount-eligible gross gains. It does
  not apply current or carried-forward losses or claim to calculate the tax return's net capital gain.
- Securities are tracked separately by Stake account and ticker.

## Expected post-2.0 redesign

Before integration into the broader application, model immutable tax lots and corporate actions,
support explicit parcel selection, preserve imported source documents and checksums, add structured
XLSX/CSV output, and place jurisdiction-specific CGT rules behind the existing provider architecture.
The eventual UI should present incomplete history and assumptions prominently and require review
before an output can be treated as final.
