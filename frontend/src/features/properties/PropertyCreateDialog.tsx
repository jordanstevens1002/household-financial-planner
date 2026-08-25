import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Controller, useFieldArray, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type Country = components['schemas']['CountryRead'];
type Baseline = components['schemas']['BaselineRead'];
type Lookup = components['schemas']['LookupRead'];
type Person = components['schemas']['PersonRead'];
type PropertySummary = components['schemas']['PropertySummaryRead'];
type PropertyWizard = components['schemas']['PropertyWizardRead'];

const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const moneyPattern = /^\d+(?:\.\d{1,2})?$/;

const setupLoanSchema = z.object({
  borrowerPersonIds: z.array(z.string().uuid()).max(20),
  displayName: z.string().trim().min(1, 'Enter a loan name').max(200),
  initialInterestRate: z
    .string()
    .refine(
      (value) =>
        value.trim() !== '' &&
        Number.isFinite(Number(value)) &&
        Number(value) >= 0 &&
        Number(value) <= 100,
      'Enter a rate from 0 to 100',
    ),
  interestCalculationMethod: z
    .enum(['', 'DAILY', 'MONTHLY'])
    .refine((value) => value !== '', 'Choose how interest is calculated'),
  isInterestOnly: z
    .enum(['', 'false', 'true'])
    .refine((value) => value !== '', 'Choose a repayment type'),
  loanTypeId: z.string().min(1, 'Choose a loan type'),
  openingBalance: z
    .string()
    .refine(
      (value) => validMoney(value, true),
      'Enter a balance greater than zero',
    ),
  repaymentFrequency: z
    .enum(['', 'WEEKLY', 'FORTNIGHTLY', 'MONTHLY'])
    .refine((value) => value !== '', 'Choose a repayment frequency'),
  scheduledRepayment: z
    .string()
    .refine(
      (value) => value === '' || validMoney(value),
      'Enter a repayment of zero or more',
    ),
  termMonths: z
    .string()
    .refine(
      (value) =>
        value === '' ||
        (/^\d+$/.test(value) && Number(value) > 0 && Number(value) <= 1200),
      'Enter a term from 1 to 1200 months',
    ),
});

type SetupLoanFields = z.input<typeof setupLoanSchema>;

const setupLoanDefaults: SetupLoanFields = {
  borrowerPersonIds: [],
  displayName: '',
  initialInterestRate: '',
  interestCalculationMethod: '',
  isInterestOnly: '',
  loanTypeId: '',
  openingBalance: '',
  repaymentFrequency: '',
  scheduledRepayment: '',
  termMonths: '',
};

function moneyCents(value: string): bigint | null {
  if (!moneyPattern.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole!) * 100n + BigInt(fraction.padEnd(2, '0'));
}

function formattedCents(value: bigint, currency: string) {
  const digits = value.toString().padStart(3, '0');
  return `${currency} ${digits.slice(0, -2)}.${digits.slice(-2)}`;
}

function validDate(value: string) {
  if (!datePattern.test(value)) return false;
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

function validMoney(value: string, mustBePositive = false) {
  if (!moneyPattern.test(value) || value.replace('.', '').length > 18) {
    return false;
  }
  const amount = Number(value);
  return Number.isFinite(amount) && (mustBePositive ? amount > 0 : amount >= 0);
}

const propertySchema = z
  .object({
    addressLine1: z.string().trim().max(200),
    countryCode: z.string(),
    currentStatusId: z.string().min(1, 'Choose the current use'),
    currentValue: z.string(),
    displayName: z.string().trim().max(200),
    existingPropertyId: z.string(),
    mode: z.enum(['CURRENT_SNAPSHOT', 'HISTORICAL_PURCHASE']),
    notes: z.string().trim().max(2000),
    loans: z.array(setupLoanSchema).max(100),
    positionDate: z.string(),
    postalCode: z.string().trim().max(20),
    propertyTypeId: z.string(),
    purchaseDate: z.string(),
    purchasePrice: z.string(),
    stateOrRegion: z.string().trim().max(120),
    suburbOrLocality: z.string().trim().max(120),
    totalDebt: z.string(),
  })
  .superRefine((fields, context) => {
    const createsProperty =
      fields.mode === 'HISTORICAL_PURCHASE' || !fields.existingPropertyId;
    if (createsProperty && !fields.displayName) {
      context.addIssue({
        code: 'custom',
        message: 'Enter a property name',
        path: ['displayName'],
      });
    }
    if (createsProperty && !fields.propertyTypeId) {
      context.addIssue({
        code: 'custom',
        message: 'Choose a property type',
        path: ['propertyTypeId'],
      });
    }
    if (fields.mode === 'CURRENT_SNAPSHOT') {
      if (!validDate(fields.positionDate)) {
        context.addIssue({
          code: 'custom',
          message: 'Enter a position date',
          path: ['positionDate'],
        });
      }
      if (!validMoney(fields.currentValue, true)) {
        context.addIssue({
          code: 'custom',
          message: 'Enter a current value greater than zero',
          path: ['currentValue'],
        });
      }
      if (!validMoney(fields.totalDebt)) {
        context.addIssue({
          code: 'custom',
          message: 'Enter total debt, using 0 when there is none',
          path: ['totalDebt'],
        });
      }
      if (!fields.existingPropertyId) {
        const debt = moneyCents(fields.totalDebt);
        const linked = fields.loans.reduce(
          (total, loan) => total + (moneyCents(loan.openingBalance) ?? 0n),
          0n,
        );
        if (debt !== null && debt > 0n && fields.loans.length === 0) {
          context.addIssue({
            code: 'custom',
            message: 'Add the loan details that make up this property debt',
            path: ['loans'],
          });
        } else if (debt !== null && linked !== debt) {
          context.addIssue({
            code: 'custom',
            message: 'Linked loan balances must equal total property debt',
            path: ['loans'],
          });
        }
      }
    } else {
      if (!validDate(fields.purchaseDate)) {
        context.addIssue({
          code: 'custom',
          message: 'Enter the purchase date',
          path: ['purchaseDate'],
        });
      }
      if (!validMoney(fields.purchasePrice)) {
        context.addIssue({
          code: 'custom',
          message: 'Enter the purchase price',
          path: ['purchasePrice'],
        });
      }
    }
  });

type PropertyFields = z.input<typeof propertySchema>;
type ValidPropertyFields = z.output<typeof propertySchema>;

function defaults(jurisdiction: string | null): PropertyFields {
  return {
    addressLine1: '',
    countryCode: jurisdiction ?? '',
    currentStatusId: '',
    currentValue: '',
    displayName: '',
    existingPropertyId: '',
    mode: 'CURRENT_SNAPSHOT',
    notes: '',
    loans: [],
    positionDate: localCalendarDate(),
    postalCode: '',
    propertyTypeId: '',
    purchaseDate: '',
    purchasePrice: '',
    stateOrRegion: '',
    suburbOrLocality: '',
    totalDebt: '',
  };
}

function optional(value: string) {
  return value || null;
}

function personLabel(person: Person) {
  return `${person.display_name}${person.is_active ? '' : ' (inactive)'}`;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function PropertyCreateDialog({
  currency,
  householdId,
  jurisdiction,
  onClose,
  onCreated,
  open,
  properties,
  propertyTypes,
  statuses,
}: {
  currency: string;
  householdId: string;
  jurisdiction: string | null;
  onClose: () => void;
  onCreated: (propertyId: string) => void;
  open: boolean;
  properties: PropertySummary[];
  propertyTypes: Lookup[];
  statuses: Lookup[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const form = useForm<PropertyFields, unknown, ValidPropertyFields>({
    defaultValues: defaults(jurisdiction),
    resolver: zodResolver(propertySchema),
  });
  const setupLoans = useFieldArray({ control: form.control, name: 'loans' });
  const mode = useWatch({ control: form.control, name: 'mode' });
  const loans = useWatch({ control: form.control, name: 'loans' });
  const totalDebt = useWatch({ control: form.control, name: 'totalDebt' });
  const existingPropertyId = useWatch({
    control: form.control,
    name: 'existingPropertyId',
  });
  const countries = useQuery({
    enabled:
      open &&
      (mode === 'HISTORICAL_PURCHASE' || existingPropertyId.length === 0),
    queryFn: () => apiRequest<Country[]>('/api/v1/reference/countries'),
    queryKey: ['reference', 'countries'],
  });
  const loanTypes = useQuery({
    enabled: open && mode === 'CURRENT_SNAPSHOT',
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/loan_type'),
    queryKey: ['lookups', 'loan_type'],
  });
  const people = useQuery({
    enabled:
      open &&
      mode === 'CURRENT_SNAPSHOT' &&
      existingPropertyId.length === 0 &&
      (loans?.length ?? 0) > 0,
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const linkedLoanCents = (loans ?? []).reduce(
    (total, loan) => total + (moneyCents(loan.openingBalance) ?? 0n),
    0n,
  );
  const setupLoanError =
    form.formState.errors.loans?.root?.message ??
    form.formState.errors.loans?.message;
  const createProperty = useMutation({
    mutationFn: async (fields: ValidPropertyFields) => {
      if (fields.mode === 'CURRENT_SNAPSHOT' && fields.existingPropertyId) {
        const property = properties.find(
          (item) => item.id === fields.existingPropertyId,
        );
        if (!property) throw new Error('Choose an accessible property');
        const baseline = await apiRequest<Baseline>(
          `/api/v1/properties/${property.id}/baselines`,
          {
            body: JSON.stringify({
              baseline_date: fields.positionDate,
              loan_balance_total: fields.totalDebt,
              property_value: fields.currentValue,
              status_id: fields.currentStatusId,
            }),
            csrfToken: auth.csrfToken(),
            method: 'POST',
          },
        );
        return {
          notification: 'Current position recorded',
          propertyId: property.id,
          summary: {
            ...property,
            current_status_id: baseline.status_id,
            current_value: baseline.property_value,
            position_date: baseline.baseline_date,
            setup_mode: 'CURRENT_SNAPSHOT' as const,
            total_property_debt: baseline.loan_balance_total,
          },
        };
      }
      const created = await apiRequest<PropertyWizard>(
        `/api/v1/households/${householdId}/properties/wizard`,
        {
          body: JSON.stringify({
            baseline:
              fields.mode === 'CURRENT_SNAPSHOT'
                ? {
                    baseline_date: fields.positionDate,
                    loan_balance_total: fields.totalDebt,
                    property_value: fields.currentValue,
                    status_id: fields.currentStatusId,
                  }
                : null,
            mode: fields.mode,
            loans:
              fields.mode === 'CURRENT_SNAPSHOT'
                ? fields.loans.map((loan) => ({
                    borrower_person_ids: loan.borrowerPersonIds,
                    display_name: loan.displayName,
                    initial_interest_rate: loan.initialInterestRate,
                    interest_calculation_method: loan.interestCalculationMethod,
                    is_active: true,
                    is_interest_only: loan.isInterestOnly === 'true',
                    loan_type_id: loan.loanTypeId,
                    opening_balance: loan.openingBalance,
                    opening_balance_date: fields.positionDate,
                    repayment_frequency: loan.repaymentFrequency,
                    scheduled_repayment: loan.scheduledRepayment || null,
                    term_months: loan.termMonths
                      ? Number(loan.termMonths)
                      : null,
                  }))
                : [],
            property: {
              address_line_1: optional(fields.addressLine1),
              country_code: optional(fields.countryCode),
              current_status_id: fields.currentStatusId,
              display_name: fields.displayName,
              notes: optional(fields.notes),
              postal_code: optional(fields.postalCode),
              property_type_id: fields.propertyTypeId,
              purchase_date:
                fields.mode === 'HISTORICAL_PURCHASE'
                  ? fields.purchaseDate
                  : null,
              purchase_price:
                fields.mode === 'HISTORICAL_PURCHASE'
                  ? fields.purchasePrice
                  : null,
              state_or_region: optional(fields.stateOrRegion),
              suburb_or_locality: optional(fields.suburbOrLocality),
            },
          }),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      );
      const summary: PropertySummary = {
        currency: created.property.default_currency,
        current_status_id: created.property.current_status_id,
        current_value: created.baseline?.property_value ?? null,
        display_name: created.property.display_name,
        id: created.property.id,
        position_date: created.baseline?.baseline_date ?? null,
        property_type_id: created.property.property_type_id,
        purchase_date: created.property.purchase_date ?? null,
        purchase_price: created.property.purchase_price ?? null,
        setup_mode: created.baseline
          ? 'CURRENT_SNAPSHOT'
          : 'HISTORICAL_PURCHASE',
        total_property_debt: created.baseline?.loan_balance_total ?? null,
      };
      return {
        notification: 'Property added',
        propertyId: created.property.id,
        summary,
      };
    },
    onSuccess: async ({ notification, propertyId, summary }) => {
      queryClient.setQueryData<PropertySummary[]>(
        ['property-summaries', householdId],
        (current = []) => [
          ...current.filter((property) => property.id !== summary.id),
          summary,
        ],
      );
      onCreated(propertyId);
      form.reset(defaults(jurisdiction));
      onClose();
      notify(notification, 'success');
      await queryClient.invalidateQueries({
        queryKey: ['property-summaries', householdId],
      });
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-loans', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
      ]);
    },
  });
  const close = () => {
    if (createProperty.isPending) return;
    form.reset(defaults(jurisdiction));
    onClose();
  };

  return (
    <Dialog fullWidth maxWidth="md" onClose={close} open={open}>
      <Box
        component="form"
        noValidate
        onSubmit={(event) => {
          void form.handleSubmit((fields) => createProperty.mutate(fields))(
            event,
          );
        }}
      >
        <DialogTitle>
          {existingPropertyId ? 'Record current position' : 'Add a property'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Controller
              control={form.control}
              name="mode"
              render={({ field }) => (
                <TextField
                  {...field}
                  label="How would you like to start?"
                  select
                >
                  <MenuItem value="CURRENT_SNAPSHOT">Current position</MenuItem>
                  <MenuItem value="HISTORICAL_PURCHASE">
                    Historical purchase
                  </MenuItem>
                </TextField>
              )}
            />
            <Alert severity="info">
              {mode === 'CURRENT_SNAPSHOT'
                ? 'Record a dated property value and add the loans that make up its total debt.'
                : 'Record what was paid and when. Purchase history does not mean the property is debt-free.'}
            </Alert>
            {mode === 'CURRENT_SNAPSHOT' && properties.length ? (
              <TextField
                label="Property to update"
                select
                {...form.register('existingPropertyId')}
              >
                <MenuItem value="">Create a new property</MenuItem>
                {properties.map((property) => (
                  <MenuItem key={property.id} value={property.id}>
                    {property.display_name}
                  </MenuItem>
                ))}
              </TextField>
            ) : null}
            {!existingPropertyId || mode === 'HISTORICAL_PURCHASE' ? (
              <>
                <TextField
                  autoFocus
                  error={Boolean(form.formState.errors.displayName)}
                  helperText={form.formState.errors.displayName?.message}
                  label="Property name"
                  {...form.register('displayName')}
                />
                <TextField
                  error={Boolean(form.formState.errors.propertyTypeId)}
                  helperText={form.formState.errors.propertyTypeId?.message}
                  label="Property type"
                  select
                  {...form.register('propertyTypeId')}
                >
                  {propertyTypes.map((item) => (
                    <MenuItem key={item.id} value={item.id}>
                      {item.display_name}
                    </MenuItem>
                  ))}
                </TextField>
              </>
            ) : null}
            <Stack>
              <TextField
                error={Boolean(form.formState.errors.currentStatusId)}
                fullWidth
                helperText={form.formState.errors.currentStatusId?.message}
                label="Current use"
                select
                {...form.register('currentStatusId')}
              >
                {statuses.map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.display_name}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            {mode === 'CURRENT_SNAPSHOT' ? (
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Position date"
                  type="date"
                  {...form.register('positionDate')}
                  error={Boolean(form.formState.errors.positionDate)}
                  helperText={form.formState.errors.positionDate?.message}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  label={`Property value (${currency})`}
                  {...form.register('currentValue')}
                  error={Boolean(form.formState.errors.currentValue)}
                  helperText={form.formState.errors.currentValue?.message}
                />
                <TextField
                  label={`Total property debt (${currency})`}
                  {...form.register('totalDebt')}
                  error={Boolean(form.formState.errors.totalDebt)}
                  helperText={
                    form.formState.errors.totalDebt?.message ??
                    'Enter 0 when there is no debt'
                  }
                />
              </Stack>
            ) : (
              <Stack direction="row" spacing={2}>
                <TextField
                  fullWidth
                  label="Purchase date"
                  type="date"
                  {...form.register('purchaseDate')}
                  error={Boolean(form.formState.errors.purchaseDate)}
                  helperText={form.formState.errors.purchaseDate?.message}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  fullWidth
                  label={`Purchase price (${currency})`}
                  {...form.register('purchasePrice')}
                  error={Boolean(form.formState.errors.purchasePrice)}
                  helperText={form.formState.errors.purchasePrice?.message}
                />
              </Stack>
            )}
            {mode === 'CURRENT_SNAPSHOT' && !existingPropertyId ? (
              <Stack spacing={2}>
                <Divider />
                <Stack
                  direction="row"
                  sx={{ alignItems: 'center', justifyContent: 'space-between' }}
                >
                  <Box>
                    <Typography variant="h6">Linked loans</Typography>
                    <Typography color="text.secondary" variant="body2">
                      Add each loan that makes up the debt recorded above.
                    </Typography>
                  </Box>
                  <Button
                    disabled={loanTypes.isPending || Boolean(loanTypes.error)}
                    onClick={() => setupLoans.append({ ...setupLoanDefaults })}
                    variant="outlined"
                  >
                    Add loan
                  </Button>
                </Stack>
                {loanTypes.isPending ? (
                  <Alert severity="info">Loading loan types…</Alert>
                ) : null}
                {loanTypes.error ? (
                  <Alert
                    action={
                      <Button
                        color="inherit"
                        onClick={() => void loanTypes.refetch()}
                      >
                        Retry
                      </Button>
                    }
                    severity="error"
                  >
                    Loan types could not be loaded. Property setup with debt is
                    unavailable until the catalogue is restored.
                  </Alert>
                ) : null}
                {people.error ? (
                  <Alert
                    action={
                      <Button
                        color="inherit"
                        onClick={() => void people.refetch()}
                      >
                        Retry people
                      </Button>
                    }
                    severity="warning"
                  >
                    Household people could not be loaded. Loans may still be
                    saved without named borrowers.
                  </Alert>
                ) : null}
                {setupLoans.fields.map((loan, index) => {
                  const errors = form.formState.errors.loans?.[index];
                  return (
                    <Stack
                      key={loan.id}
                      spacing={2}
                      sx={{
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: 1,
                        p: 2,
                      }}
                    >
                      <Stack
                        direction="row"
                        sx={{
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <Typography variant="subtitle1">
                          Loan {index + 1}
                        </Typography>
                        <Button
                          color="error"
                          onClick={() => setupLoans.remove(index)}
                        >
                          Remove
                        </Button>
                      </Stack>
                      <Stack direction="row" spacing={2}>
                        <TextField
                          error={Boolean(errors?.displayName)}
                          fullWidth
                          helperText={errors?.displayName?.message}
                          label="Loan name"
                          {...form.register(`loans.${index}.displayName`)}
                        />
                        <Controller
                          control={form.control}
                          name={`loans.${index}.loanTypeId`}
                          render={({ field }) => (
                            <TextField
                              {...field}
                              error={Boolean(errors?.loanTypeId)}
                              fullWidth
                              helperText={errors?.loanTypeId?.message}
                              label="Loan type"
                              select
                            >
                              {(loanTypes.data ?? []).map((item) => (
                                <MenuItem key={item.id} value={item.id}>
                                  {item.display_name}
                                </MenuItem>
                              ))}
                            </TextField>
                          )}
                        />
                      </Stack>
                      <Controller
                        control={form.control}
                        name={`loans.${index}.borrowerPersonIds`}
                        render={({ field }) => (
                          <Autocomplete
                            disableCloseOnSelect
                            disabled={people.isPending || Boolean(people.error)}
                            getOptionLabel={personLabel}
                            isOptionEqualToValue={(option, value) =>
                              option.id === value.id
                            }
                            multiple
                            onChange={(_, selected) =>
                              field.onChange(
                                selected.map((person) => person.id),
                              )
                            }
                            options={people.data ?? []}
                            renderInput={(params) => (
                              <TextField
                                {...params}
                                helperText="Scheduled repayments are shared equally unless an Advanced dated override applies."
                                label={`Borrowers for loan ${index + 1} (optional)`}
                              />
                            )}
                            value={(people.data ?? []).filter((person) =>
                              field.value.includes(person.id),
                            )}
                          />
                        )}
                      />
                      <Stack direction="row" spacing={2}>
                        <TextField
                          error={Boolean(errors?.openingBalance)}
                          fullWidth
                          helperText={errors?.openingBalance?.message}
                          label={`Opening balance (${currency})`}
                          {...form.register(`loans.${index}.openingBalance`)}
                        />
                        <TextField
                          error={Boolean(errors?.initialInterestRate)}
                          fullWidth
                          helperText={errors?.initialInterestRate?.message}
                          label="Annual interest rate %"
                          {...form.register(
                            `loans.${index}.initialInterestRate`,
                          )}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2}>
                        <TextField
                          error={Boolean(errors?.scheduledRepayment)}
                          fullWidth
                          helperText={
                            errors?.scheduledRepayment?.message ?? 'Optional'
                          }
                          label={`Scheduled repayment (${currency})`}
                          {...form.register(
                            `loans.${index}.scheduledRepayment`,
                          )}
                        />
                        <Controller
                          control={form.control}
                          name={`loans.${index}.repaymentFrequency`}
                          render={({ field }) => (
                            <TextField
                              {...field}
                              error={Boolean(errors?.repaymentFrequency)}
                              fullWidth
                              helperText={errors?.repaymentFrequency?.message}
                              label="Repayment frequency"
                              select
                            >
                              <MenuItem value="WEEKLY">Weekly</MenuItem>
                              <MenuItem value="FORTNIGHTLY">
                                Fortnightly
                              </MenuItem>
                              <MenuItem value="MONTHLY">Monthly</MenuItem>
                            </TextField>
                          )}
                        />
                        <TextField
                          error={Boolean(errors?.termMonths)}
                          fullWidth
                          helperText={errors?.termMonths?.message ?? 'Optional'}
                          label="Term in months"
                          {...form.register(`loans.${index}.termMonths`)}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2}>
                        <Controller
                          control={form.control}
                          name={`loans.${index}.isInterestOnly`}
                          render={({ field }) => (
                            <TextField
                              {...field}
                              error={Boolean(errors?.isInterestOnly)}
                              fullWidth
                              helperText={errors?.isInterestOnly?.message}
                              label="Repayment type"
                              select
                            >
                              <MenuItem value="false">
                                Principal and interest
                              </MenuItem>
                              <MenuItem value="true">Interest only</MenuItem>
                            </TextField>
                          )}
                        />
                        <Controller
                          control={form.control}
                          name={`loans.${index}.interestCalculationMethod`}
                          render={({ field }) => (
                            <TextField
                              {...field}
                              error={Boolean(errors?.interestCalculationMethod)}
                              fullWidth
                              helperText={
                                errors?.interestCalculationMethod?.message
                              }
                              label="Interest calculation"
                              select
                            >
                              <MenuItem value="DAILY">Daily</MenuItem>
                              <MenuItem value="MONTHLY">Monthly</MenuItem>
                            </TextField>
                          )}
                        />
                      </Stack>
                    </Stack>
                  );
                })}
                <Alert
                  severity={
                    moneyCents(totalDebt) !== null &&
                    moneyCents(totalDebt) === linkedLoanCents
                      ? 'success'
                      : 'warning'
                  }
                >
                  Linked loan balances total{' '}
                  {formattedCents(linkedLoanCents, currency)}. Recorded property
                  debt is{' '}
                  {formattedCents(moneyCents(totalDebt) ?? 0n, currency)}.
                  {setupLoanError ? ` ${setupLoanError}` : ''}
                </Alert>
              </Stack>
            ) : null}
            {existingPropertyId && mode === 'CURRENT_SNAPSHOT' ? null : (
              <AdvancedSection description="Add the property address and notes when they are useful to your household.">
                <Stack spacing={2}>
                  <TextField
                    label="Street address (optional)"
                    {...form.register('addressLine1')}
                  />
                  <Stack direction="row" spacing={2}>
                    <TextField
                      fullWidth
                      label="Suburb or locality (optional)"
                      {...form.register('suburbOrLocality')}
                    />
                    <TextField
                      fullWidth
                      label="State or region (optional)"
                      {...form.register('stateOrRegion')}
                    />
                    <TextField
                      fullWidth
                      label="Postal code (optional)"
                      {...form.register('postalCode')}
                    />
                  </Stack>
                  <Controller
                    control={form.control}
                    name="countryCode"
                    render={({ field }) => {
                      const discovered = countries.data ?? [];
                      const fallback =
                        field.value &&
                        !discovered.some(
                          (country) => country.code === field.value,
                        )
                          ? {
                              code: field.value,
                              display_name: `${field.value} (household country)`,
                              flag: '🌐',
                              recommended_currency: null,
                            }
                          : null;
                      const options = fallback
                        ? [fallback, ...discovered]
                        : discovered;
                      return (
                        <Autocomplete
                          getOptionLabel={(option) =>
                            `${option.flag} ${option.display_name}`
                          }
                          loading={countries.isPending}
                          onChange={(_, option) =>
                            field.onChange(option?.code ?? '')
                          }
                          options={options}
                          value={
                            options.find(
                              (country) => country.code === field.value,
                            ) ?? null
                          }
                          renderInput={(params) => (
                            <TextField {...params} label="Country (optional)" />
                          )}
                        />
                      );
                    }}
                  />
                  <TextField
                    label="Notes (optional)"
                    minRows={2}
                    multiline
                    {...form.register('notes')}
                  />
                </Stack>
              </AdvancedSection>
            )}
            {countries.error ? (
              <Alert severity="warning">
                Countries could not be loaded. The household country remains
                selected; clear it if this property is elsewhere.
              </Alert>
            ) : null}
            {createProperty.error ? (
              <Alert severity="error">
                Property could not be added. {message(createProperty.error)}
              </Alert>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>Cancel</Button>
          <Button
            disabled={
              createProperty.isPending ||
              (mode === 'CURRENT_SNAPSHOT' &&
                !existingPropertyId &&
                (moneyCents(totalDebt) ?? 0n) > 0n &&
                (loanTypes.isPending || Boolean(loanTypes.error)))
            }
            type="submit"
            variant="contained"
          >
            {existingPropertyId ? 'Save current position' : 'Save property'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
