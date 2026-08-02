import type { components } from '../../api/schema';

type Calculation = components['schemas']['StandaloneTaxCalculationRead'];
type Provider = components['schemas']['TaxProviderRead'];

export function taxCalculationProvenance(
  result: Calculation,
  providers: Provider[],
) {
  if (result.ruleset_version === 'manual') {
    return `Manual annual net income — ${result.jurisdiction}`;
  }
  return (
    providers.find((provider) => provider.jurisdiction === result.jurisdiction)
      ?.display_name ?? `${result.jurisdiction} (not currently discovered)`
  );
}
