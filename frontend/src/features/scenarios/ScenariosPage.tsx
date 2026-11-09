import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { useHousehold } from '../households/HouseholdContext';
import { localCalendarDate } from '../people/localDate';
import { validateTemplateValue } from './templateValueValidation';

type Access = components['schemas']['HouseholdAccessRead'];
type Scenario = components['schemas']['ScenarioRead'];
type Template = components['schemas']['TemplateRead'];

interface Draft {
  baseScenarioId: string;
  description: string;
  displayName: string;
  effectiveFrom: string;
  targetEntityId: string;
  templateCode: string;
  value: string;
}

interface LifecycleDraft {
  baseScenarioId: string;
  description: string;
  displayName: string;
}

const blankDraft = (): Draft => ({
  baseScenarioId: '',
  description: '',
  displayName: '',
  effectiveFrom: localCalendarDate(),
  targetEntityId: '',
  templateCode: 'CUSTOM',
  value: '',
});

const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed.';

const displayCode = (value: string) =>
  value
    .toLowerCase()
    .split('_')
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');

export function ScenariosPage() {
  const auth = useAuth();
  const household = useHousehold();
  const notification = useNotification();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Scenario | null>(null);
  const [deleting, setDeleting] = useState<Scenario | null>(null);
  const [draft, setDraft] = useState<Draft>(blankDraft);
  const [lifecycleDraft, setLifecycleDraft] = useState<LifecycleDraft>({
    baseScenarioId: '',
    description: '',
    displayName: '',
  });
  const [validation, setValidation] = useState('');
  const [lifecycleError, setLifecycleError] = useState('');
  const householdId = household.selected?.id ?? '';
  const scenarios = useQuery({
    enabled: Boolean(householdId),
    queryFn: () =>
      apiRequest<Scenario[]>(`/api/v1/households/${householdId}/scenarios`),
    queryKey: ['household-scenarios', householdId],
    retry: false,
  });
  const templates = useQuery({
    enabled: Boolean(householdId),
    queryFn: () => apiRequest<Template[]>('/api/v1/scenario-templates'),
    queryKey: ['scenario-templates'],
    retry: false,
  });
  const access = useQuery({
    enabled: Boolean(householdId),
    queryFn: () =>
      apiRequest<Access>(`/api/v1/households/${householdId}/access`),
    queryKey: ['household-access', householdId],
    retry: false,
  });
  const selectedTemplate = templates.data?.find(
    (item) => item.code === draft.templateCode,
  );
  const timeline = useQuery({
    enabled:
      Boolean(householdId) &&
      creating &&
      selectedTemplate?.target_entity_type === 'FINANCIAL_EVENT',
    queryFn: () =>
      apiRequest<components['schemas']['TimelineRead']>(
        `/api/v1/households/${householdId}/timeline?include_disabled=true`,
      ),
    queryKey: ['household-timeline', householdId, 'include-disabled'],
    retry: false,
  });
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: ['household-scenarios', householdId],
    });
  const closeForm = () => {
    setCreating(false);
    setValidation('');
    setDraft(blankDraft());
  };
  const beginEditing = (scenario: Scenario) => {
    setLifecycleError('');
    setLifecycleDraft({
      baseScenarioId: scenario.base_scenario_id ?? '',
      description: scenario.description ?? '',
      displayName: scenario.display_name,
    });
    setEditing(scenario);
  };
  const closeEditing = () => {
    setEditing(null);
    setLifecycleError('');
  };
  const save = useMutation({
    mutationFn: () => {
      if (draft.templateCode !== 'CUSTOM') {
        return apiRequest<Scenario>(
          `/api/v1/households/${householdId}/scenarios/from-template`,
          {
            body: JSON.stringify({
              description: draft.description.trim() || null,
              display_name: draft.displayName.trim(),
              effective_from: draft.effectiveFrom,
              target_entity_id: draft.targetEntityId || null,
              template_code: draft.templateCode,
              value: draft.value.trim() || null,
            }),
            csrfToken: auth.csrfToken(),
            method: 'POST',
          },
        );
      }
      return apiRequest<Scenario>(
        `/api/v1/households/${householdId}/scenarios`,
        {
          body: JSON.stringify({
            base_scenario_id: draft.baseScenarioId || null,
            description: draft.description.trim() || null,
            display_name: draft.displayName.trim(),
            is_active: true,
            template_code: null,
          }),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      );
    },
    onError: (error) => notification.notify(message(error), 'error'),
    onSuccess: async () => {
      await refresh();
      notification.notify('Scenario created.', 'success');
      closeForm();
    },
  });
  const recoverLifecycleFailure = async (
    error: unknown,
    selected = editing ?? deleting,
  ) => {
    const refreshed = await scenarios.refetch();
    if (
      selected &&
      refreshed.data &&
      !refreshed.data.some((item) => item.id === selected.id)
    ) {
      setEditing(null);
      setDeleting(null);
      setLifecycleError(
        'This scenario is no longer available. The catalogue has been refreshed.',
      );
      return;
    }
    setLifecycleError(message(error));
  };
  const updateScenario = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: components['schemas']['ScenarioUpdate'];
    }) =>
      apiRequest<Scenario>(`/api/v1/scenarios/${id}`, {
        body: JSON.stringify(values),
        csrfToken: auth.csrfToken(),
        method: 'PUT',
      }),
    onError: (error) => recoverLifecycleFailure(error, editing),
    onSuccess: async (_, variables) => {
      await refresh();
      notification.notify(
        'is_active' in variables.values
          ? `Scenario ${variables.values.is_active ? 'activated' : 'deactivated'}.`
          : 'Scenario updated.',
        'success',
      );
      closeEditing();
    },
  });
  const deleteScenario = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`/api/v1/scenarios/${id}`, {
        csrfToken: auth.csrfToken(),
        method: 'DELETE',
      }),
    onError: async (error) => {
      const selected = deleting;
      setDeleting(null);
      await recoverLifecycleFailure(error, selected);
    },
    onSuccess: async () => {
      setDeleting(null);
      setLifecycleError('');
      await refresh();
      notification.notify('Scenario deleted.', 'success');
    },
  });
  const submit = () => {
    setValidation('');
    if (!draft.displayName.trim()) return setValidation('Name is required.');
    if (draft.description.length > 2_000)
      return setValidation('Description cannot exceed 2,000 characters.');
    if (draft.templateCode !== 'CUSTOM') {
      if (!draft.effectiveFrom)
        return setValidation('Effective date is required for a template.');
      if (
        selectedTemplate?.target_entity_type === 'FINANCIAL_EVENT' &&
        !draft.targetEntityId
      )
        return setValidation(
          'Choose the planned event affected by this template.',
        );
      const valueError = validateTemplateValue(
        draft.templateCode,
        draft.value.trim() || selectedTemplate?.default_value || '',
      );
      if (valueError) return setValidation(valueError);
    }
    save.mutate();
  };
  const submitCorrection = () => {
    setLifecycleError('');
    if (!editing) return;
    if (!lifecycleDraft.displayName.trim())
      return setLifecycleError('Name is required.');
    if (lifecycleDraft.description.length > 2_000)
      return setLifecycleError('Description cannot exceed 2,000 characters.');
    updateScenario.mutate({
      id: editing.id,
      values: {
        base_scenario_id: lifecycleDraft.baseScenarioId || null,
        description: lifecycleDraft.description.trim() || null,
        display_name: lifecycleDraft.displayName.trim(),
      },
    });
  };
  const templateName = (scenario: Scenario) =>
    templates.data?.find((item) => item.code === scenario.template_code)
      ?.display_name ??
    (scenario.template_code ? displayCode(scenario.template_code) : 'Custom');
  const columns: DataColumn<Scenario>[] = [
    { key: 'name', label: 'Scenario', render: (item) => item.display_name },
    { key: 'template', label: 'Starting point', render: templateName },
    {
      key: 'base',
      label: 'Inherits from',
      render: (item) =>
        scenarios.data?.find((base) => base.id === item.base_scenario_id)
          ?.display_name ?? 'None',
    },
    {
      key: 'status',
      label: 'Status',
      render: (item) => (item.is_active ? 'Active' : 'Inactive'),
    },
    {
      key: 'description',
      label: 'Description',
      render: (item) => item.description ?? '—',
    },
    ...(access.data?.can_edit
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (item: Scenario) => (
              <Stack direction="row" spacing={1}>
                <Button onClick={() => beginEditing(item)} size="small">
                  Correct
                </Button>
                <Button
                  disabled={updateScenario.isPending}
                  onClick={() =>
                    updateScenario.mutate({
                      id: item.id,
                      values: { is_active: !item.is_active },
                    })
                  }
                  size="small"
                >
                  {item.is_active ? 'Deactivate' : 'Activate'}
                </Button>
                <Button
                  color="error"
                  onClick={() => {
                    setLifecycleError('');
                    setDeleting(item);
                  }}
                  size="small"
                >
                  Delete
                </Button>
              </Stack>
            ),
          },
        ]
      : []),
  ];

  if (household.loading)
    return <CircularProgress aria-label="Loading households" />;
  if (household.error)
    return <Alert severity="error">{household.error.message}</Alert>;
  if (!household.selected)
    return (
      <EmptyState
        description="Choose a household before managing planning scenarios."
        title="No household selected"
      />
    );

  return (
    <Stack spacing={3}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Box>
          <Typography component="h1" variant="h4">
            Scenarios
          </Typography>
          <Typography color="text.secondary">
            Save alternative assumptions without changing household records.
          </Typography>
        </Box>
        {access.data?.can_edit ? (
          <Button
            disabled={templates.isPending || Boolean(templates.error)}
            onClick={() => setCreating(true)}
            variant="contained"
          >
            Add scenario
          </Button>
        ) : null}
      </Box>
      <Alert severity="info">
        Saving a scenario records reusable assumptions only. It does not change
        household records or calculate a result; calculations run separately
        against explicit baseline metrics.
      </Alert>
      {templates.error ? (
        <Alert
          action={
            <Button color="inherit" onClick={() => void templates.refetch()}>
              Retry
            </Button>
          }
          severity="error"
        >
          Scenario templates could not be loaded. {message(templates.error)}
        </Alert>
      ) : null}
      {lifecycleError && !editing ? (
        <Alert severity="error">{lifecycleError}</Alert>
      ) : null}
      {scenarios.isPending ? (
        <CircularProgress aria-label="Loading scenarios" />
      ) : scenarios.error ? (
        <Alert
          action={
            <Button color="inherit" onClick={() => void scenarios.refetch()}>
              Retry
            </Button>
          }
          severity="error"
        >
          Scenarios could not be loaded. {message(scenarios.error)}
        </Alert>
      ) : scenarios.data.length === 0 ? (
        <EmptyState
          description={
            access.data?.can_edit
              ? 'Add a custom scenario or start from a planning template.'
              : 'No scenarios have been saved for this household.'
          }
          title="No saved scenarios"
        />
      ) : (
        <DataTable
          caption="Saved scenarios"
          columns={columns}
          getRowKey={(item) => item.id}
          rows={scenarios.data}
        />
      )}

      <Dialog
        fullWidth
        maxWidth="sm"
        onClose={save.isPending ? undefined : closeForm}
        open={creating}
      >
        <DialogTitle>Add scenario</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {validation ? <Alert severity="error">{validation}</Alert> : null}
            <TextField
              label="Starting point"
              onChange={(input) =>
                setDraft((current) => ({
                  ...current,
                  templateCode: input.target.value,
                  value: '',
                  targetEntityId: '',
                }))
              }
              select
              value={draft.templateCode}
            >
              {(templates.data ?? []).map((item) => (
                <MenuItem key={item.code} value={item.code}>
                  {item.display_name}
                </MenuItem>
              ))}
            </TextField>
            {selectedTemplate ? (
              <Alert severity="info">{selectedTemplate.description}</Alert>
            ) : null}
            <TextField
              label="Scenario name"
              onChange={(input) =>
                setDraft((current) => ({
                  ...current,
                  displayName: input.target.value,
                }))
              }
              value={draft.displayName}
            />
            <TextField
              label="Description (optional)"
              minRows={2}
              multiline
              onChange={(input) =>
                setDraft((current) => ({
                  ...current,
                  description: input.target.value,
                }))
              }
              value={draft.description}
            />
            {draft.templateCode === 'CUSTOM' ? (
              <TextField
                label="Inherits from (optional)"
                onChange={(input) =>
                  setDraft((current) => ({
                    ...current,
                    baseScenarioId: input.target.value,
                  }))
                }
                select
                value={draft.baseScenarioId}
              >
                <MenuItem value="">None</MenuItem>
                {(scenarios.data ?? []).map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.display_name}
                  </MenuItem>
                ))}
              </TextField>
            ) : (
              <>
                <TextField
                  label="Effective date"
                  onChange={(input) =>
                    setDraft((current) => ({
                      ...current,
                      effectiveFrom: input.target.value,
                    }))
                  }
                  slotProps={{ inputLabel: { shrink: true } }}
                  type="date"
                  value={draft.effectiveFrom}
                />
                <TextField
                  helperText={`Default: ${selectedTemplate?.default_value ?? 'None'}`}
                  label="Template value (optional)"
                  onChange={(input) =>
                    setDraft((current) => ({
                      ...current,
                      value: input.target.value,
                    }))
                  }
                  value={draft.value}
                />
                {selectedTemplate?.target_entity_type === 'FINANCIAL_EVENT' ? (
                  timeline.error ? (
                    <Alert severity="error">
                      Planned events could not be loaded.
                    </Alert>
                  ) : (
                    <TextField
                      disabled={timeline.isPending}
                      label="Planned event"
                      onChange={(input) =>
                        setDraft((current) => ({
                          ...current,
                          targetEntityId: input.target.value,
                        }))
                      }
                      select
                      value={draft.targetEntityId}
                    >
                      {(timeline.data?.events ?? [])
                        .filter(
                          (item) =>
                            item.classification === 'PLANNED' &&
                            item.is_enabled &&
                            item.event_type_code === 'PROPERTY_PURCHASED',
                        )
                        .map((item) => (
                          <MenuItem key={item.id} value={item.id}>
                            {displayCode(item.event_type_code)} ·{' '}
                            {formatDate(item.effective_at)}
                          </MenuItem>
                        ))}
                    </TextField>
                  )
                ) : null}
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={save.isPending} onClick={closeForm}>
            Cancel
          </Button>
          <Button
            disabled={save.isPending}
            onClick={submit}
            variant="contained"
          >
            Create scenario
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        fullWidth
        maxWidth="sm"
        onClose={updateScenario.isPending ? undefined : closeEditing}
        open={Boolean(editing)}
      >
        <DialogTitle>Correct scenario</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {lifecycleError ? (
              <Alert severity="error">{lifecycleError}</Alert>
            ) : null}
            <Alert severity="info">
              Corrections change this saved scenario only. Household records are
              not modified.
            </Alert>
            <TextField
              label="Scenario name"
              onChange={(input) =>
                setLifecycleDraft((current) => ({
                  ...current,
                  displayName: input.target.value,
                }))
              }
              value={lifecycleDraft.displayName}
            />
            <TextField
              label="Description (optional)"
              minRows={2}
              multiline
              onChange={(input) =>
                setLifecycleDraft((current) => ({
                  ...current,
                  description: input.target.value,
                }))
              }
              value={lifecycleDraft.description}
            />
            <TextField
              label="Inherits from (optional)"
              onChange={(input) =>
                setLifecycleDraft((current) => ({
                  ...current,
                  baseScenarioId: input.target.value,
                }))
              }
              select
              value={lifecycleDraft.baseScenarioId}
            >
              <MenuItem value="">None</MenuItem>
              {(scenarios.data ?? [])
                .filter((item) => item.id !== editing?.id)
                .map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.display_name}
                  </MenuItem>
                ))}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={updateScenario.isPending} onClick={closeEditing}>
            Cancel
          </Button>
          <Button
            disabled={updateScenario.isPending}
            onClick={submitCorrection}
            variant="contained"
          >
            Save correction
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        confirmLabel="Delete scenario"
        description={`Delete “${deleting?.display_name ?? ''}”? Its assumptions will be removed. Scenarios that inherit from it will no longer have this starting point. Household records are not changed.`}
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          if (deleting) deleteScenario.mutate(deleting.id);
        }}
        open={Boolean(deleting)}
        pending={deleteScenario.isPending}
        title={`Delete ${deleting?.display_name ?? 'scenario'}?`}
      />
    </Stack>
  );
}
