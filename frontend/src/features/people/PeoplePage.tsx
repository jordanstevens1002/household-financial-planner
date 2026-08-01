import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { loadSelection, saveSelection } from '../../app/selectionStorage';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { useHousehold } from '../households/HouseholdContext';

type Country = components['schemas']['CountryRead'];
type Person = components['schemas']['PersonRead'];

const optionalDate = z
  .string()
  .refine((value) => value === '' || /^\d{4}-\d{2}-\d{2}$/.test(value), {
    message: 'Enter a date as YYYY-MM-DD',
  });
const personSchema = z
  .object({
    dateOfBirth: optionalDate,
    displayName: z.string().trim().min(1, 'Enter a display name').max(200),
    effectiveFrom: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a date as YYYY-MM-DD'),
    effectiveTo: optionalDate,
    legalName: z.string().trim().max(200),
    notes: z.string().trim().max(2000),
    taxJurisdiction: z.string(),
    taxResidencyCountry: z.string(),
  })
  .refine(
    ({ effectiveFrom, effectiveTo }) =>
      effectiveTo === '' || effectiveTo >= effectiveFrom,
    {
      message: 'End date must not be before the start date',
      path: ['effectiveTo'],
    },
  );

type PersonFields = z.infer<typeof personSchema>;

function today() {
  return new Date().toISOString().slice(0, 10);
}

function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function PeoplePage() {
  const auth = useAuth();
  const household = useHousehold();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(() => loadSelection('person'));
  const form = useForm<PersonFields>({
    defaultValues: {
      dateOfBirth: '',
      displayName: '',
      effectiveFrom: today(),
      effectiveTo: '',
      legalName: '',
      notes: '',
      taxJurisdiction: '',
      taxResidencyCountry: '',
    },
    resolver: zodResolver(personSchema),
  });
  const people = useQuery({
    enabled: household.selected !== null,
    queryFn: async () => {
      const accessible = await apiRequest<Person[]>(
        `/api/v1/households/${household.selected!.id}/people`,
      );
      const storedPersonId = loadSelection('person');
      if (
        storedPersonId !== null &&
        !accessible.some((person) => person.id === storedPersonId)
      ) {
        saveSelection('person', null);
      }
      return accessible;
    },
    queryKey: ['people', household.selected?.id],
    retry: false,
  });
  const countries = useQuery({
    enabled: createOpen,
    queryFn: () => apiRequest<Country[]>('/api/v1/reference/countries'),
    queryKey: ['reference', 'countries'],
  });
  const selectionCandidate = selectedId ?? loadSelection('person');
  const validSelectedId =
    people.data?.some((person) => person.id === selectionCandidate) === true
      ? selectionCandidate
      : null;

  const createPerson = useMutation({
    mutationFn: (fields: PersonFields) => {
      const residency = fields.taxResidencyCountry || null;
      return apiRequest<Person>(
        `/api/v1/households/${household.selected!.id}/people`,
        {
          body: JSON.stringify({
            date_of_birth: fields.dateOfBirth || null,
            display_name: fields.displayName,
            effective_from: fields.effectiveFrom,
            effective_to: fields.effectiveTo || null,
            is_active: true,
            legal_name: fields.legalName || null,
            notes: fields.notes || null,
            tax_jurisdiction: fields.taxJurisdiction || residency,
            tax_residency_country: residency,
          }),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      );
    },
    onSuccess: (created) => {
      setSelectedId(created.id);
      setCreateOpen(false);
      form.reset({
        dateOfBirth: '',
        displayName: '',
        effectiveFrom: today(),
        effectiveTo: '',
        legalName: '',
        notes: '',
        taxJurisdiction: '',
        taxResidencyCountry: '',
      });
      notify('Person added', 'success');
      queryClient.setQueryData<Person[]>(
        ['people', household.selected?.id],
        (current = []) => [...current, created],
      );
      saveSelection('person', created.id);
    },
  });

  const select = (person: Person) => {
    setSelectedId(person.id);
    saveSelection('person', person.id);
    saveSelection('property', null);
  };
  const columns: DataColumn<Person>[] = [
    { key: 'name', label: 'Person', render: (row) => row.display_name },
    {
      key: 'residency',
      label: 'Tax residency',
      render: (row) => row.tax_residency_country ?? 'Not recorded',
    },
    {
      key: 'effective',
      label: 'Recorded from',
      render: (row) => formatDate(row.effective_from),
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => (row.is_active ? 'Active' : 'Inactive'),
    },
    {
      key: 'selection',
      label: 'Selection',
      render: (row) => (
        <Button
          onClick={() => select(row)}
          variant={validSelectedId === row.id ? 'contained' : 'outlined'}
        >
          {validSelectedId === row.id ? 'Selected' : 'Use person'}
        </Button>
      ),
    },
  ];

  if (!household.selected) {
    return (
      <Stack spacing={3}>
        <Typography component="h1" variant="h4">
          People
        </Typography>
        <EmptyState
          description="Choose a household before adding the people whose finances it includes."
          title="No household selected"
        />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          People
        </Typography>
        <Typography color="text.secondary">
          Record the people included in {household.selected.display_name}.
          Adding someone here records their identity only; their income,
          expenses and other financial details are added separately.
        </Typography>
      </Box>
      <Box>
        <Button onClick={() => setCreateOpen(true)} variant="contained">
          Add person
        </Button>
      </Box>
      {people.isPending ? (
        <CircularProgress aria-label="Loading people" />
      ) : people.error ? (
        <Alert severity="error">
          Could not load people. {message(people.error)}
        </Alert>
      ) : people.data?.length ? (
        <DataTable
          caption={`${household.selected.display_name} people`}
          columns={columns}
          getRowKey={(row) => row.id}
          rows={people.data}
        />
      ) : (
        <EmptyState
          actionLabel="Add the first person"
          description="Add a person to start recording their part of the household plan."
          onAction={() => setCreateOpen(true)}
          title="No people recorded"
        />
      )}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth>
        <DialogTitle>Add a person</DialogTitle>
        <Box
          component="form"
          onSubmit={(event) => {
            void form.handleSubmit((fields) => createPerson.mutate(fields))(
              event,
            );
          }}
        >
          <DialogContent>
            <Stack spacing={2}>
              <TextField
                label="Display name"
                {...form.register('displayName')}
                error={Boolean(form.formState.errors.displayName)}
                helperText={form.formState.errors.displayName?.message}
              />
              <TextField
                label="Legal name (optional)"
                {...form.register('legalName')}
              />
              <TextField
                label="Date of birth (optional)"
                type="date"
                {...form.register('dateOfBirth')}
                error={Boolean(form.formState.errors.dateOfBirth)}
                helperText={form.formState.errors.dateOfBirth?.message}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <Controller
                control={form.control}
                name="taxResidencyCountry"
                render={({ field }) => (
                  <Autocomplete
                    options={countries.data ?? []}
                    getOptionLabel={(option) =>
                      `${option.flag} ${option.display_name}`
                    }
                    value={
                      (countries.data ?? []).find(
                        (country) => country.code === field.value,
                      ) ?? null
                    }
                    onChange={(_, option) => field.onChange(option?.code ?? '')}
                    renderInput={(params) => (
                      <TextField {...params} label="Tax residency (optional)" />
                    )}
                  />
                )}
              />
              <TextField
                label="Effective from"
                type="date"
                {...form.register('effectiveFrom')}
                error={Boolean(form.formState.errors.effectiveFrom)}
                helperText={form.formState.errors.effectiveFrom?.message}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <AdvancedSection description="Tax jurisdiction normally follows tax residency. Override it only when specialist advice indicates they differ.">
                <Stack spacing={2}>
                  <Controller
                    control={form.control}
                    name="taxJurisdiction"
                    render={({ field }) => (
                      <Autocomplete
                        options={countries.data ?? []}
                        getOptionLabel={(option) =>
                          `${option.flag} ${option.display_name}`
                        }
                        value={
                          (countries.data ?? []).find(
                            (country) => country.code === field.value,
                          ) ?? null
                        }
                        onChange={(_, option) =>
                          field.onChange(option?.code ?? '')
                        }
                        renderInput={(params) => (
                          <TextField
                            {...params}
                            label="Tax jurisdiction override"
                          />
                        )}
                      />
                    )}
                  />
                  <TextField
                    label="Effective to (optional)"
                    type="date"
                    {...form.register('effectiveTo')}
                    error={Boolean(form.formState.errors.effectiveTo)}
                    helperText={form.formState.errors.effectiveTo?.message}
                    slotProps={{ inputLabel: { shrink: true } }}
                  />
                  <TextField
                    label="Notes (optional)"
                    multiline
                    minRows={2}
                    {...form.register('notes')}
                  />
                </Stack>
              </AdvancedSection>
              {createPerson.error ? (
                <Alert severity="error">{message(createPerson.error)}</Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              disabled={createPerson.isPending}
              type="submit"
              variant="contained"
            >
              Add person
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Stack>
  );
}
