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
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Controller, useForm, useWatch } from 'react-hook-form';
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
type PropertySummary = components['schemas']['PropertySummaryRead'];
type PropertyWizard = components['schemas']['PropertyWizardRead'];

const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const moneyPattern = /^\d+(?:\.\d{1,2})?$/;

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

type PropertyFields = z.infer<typeof propertySchema>;

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
  const form = useForm<PropertyFields>({
    defaultValues: defaults(jurisdiction),
    resolver: zodResolver(propertySchema),
  });
  const mode = useWatch({ control: form.control, name: 'mode' });
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
  const createProperty = useMutation({
    mutationFn: async (fields: PropertyFields) => {
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
                ? 'Record a dated property value and its total debt. Individual loans can be added separately.'
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
            disabled={createProperty.isPending}
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
