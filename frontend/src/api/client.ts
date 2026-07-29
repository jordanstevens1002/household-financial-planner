export type ApiErrorKind =
  | 'forbidden'
  | 'network'
  | 'server'
  | 'unauthorised'
  | 'unexpected'
  | 'validation';

export interface ValidationProblem {
  field: string;
  message: string;
  type?: string;
}

interface FastApiValidationProblem {
  loc?: unknown[];
  msg?: unknown;
  type?: unknown;
}

export interface ApiRequestOptions extends RequestInit {
  csrfToken?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: ApiErrorKind,
    readonly status: number,
    readonly requestId?: string,
    readonly validation: ValidationProblem[] = [],
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function isMutation(method: string): boolean {
  return !['GET', 'HEAD', 'OPTIONS'].includes(method);
}

function validationProblems(detail: unknown): ValidationProblem[] {
  if (!Array.isArray(detail)) {
    return [];
  }

  return detail.flatMap((problem: unknown) => {
    if (typeof problem !== 'object' || problem === null) {
      return [];
    }

    const candidate = problem as FastApiValidationProblem;
    const message = typeof candidate.msg === 'string' ? candidate.msg : null;
    if (message === null) {
      return [];
    }

    const location = Array.isArray(candidate.loc)
      ? candidate.loc.filter(
          (part): part is string | number =>
            typeof part === 'string' || typeof part === 'number',
        )
      : [];
    const field = location
      .filter((part) => !['body', 'path', 'query'].includes(String(part)))
      .join('.');

    return [
      {
        field: field || 'request',
        message,
        type: typeof candidate.type === 'string' ? candidate.type : undefined,
      },
    ];
  });
}

function errorKind(status: number): ApiErrorKind {
  if (status === 401) return 'unauthorised';
  if (status === 403) return 'forbidden';
  if (status === 422) return 'validation';
  if (status >= 500) return 'server';
  return 'unexpected';
}

async function responseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (typeof body !== 'object' || body === null || !('detail' in body)) {
    return fallback;
  }
  return typeof body.detail === 'string' ? body.detail : fallback;
}

export async function apiRequest<T>(
  path: `/api/${string}`,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { csrfToken, headers: suppliedHeaders, ...requestOptions } = options;
  const method = (requestOptions.method ?? 'GET').toUpperCase();
  const headers = new Headers(suppliedHeaders);
  headers.set('Accept', 'application/json');

  if (requestOptions.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (csrfToken !== undefined && isMutation(method)) {
    headers.set('X-CSRF-Token', csrfToken);
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...requestOptions,
      credentials: 'include',
      headers,
      method,
    });
  } catch (cause) {
    throw new ApiError(
      cause instanceof Error ? cause.message : 'Unable to reach the API',
      'network',
      0,
    );
  }

  if (response.ok) {
    if (response.status === 204) {
      return undefined as T;
    }
    return (await responseBody(response)) as T;
  }

  const body = await responseBody(response);
  const requestId = response.headers.get('X-Request-ID') ?? undefined;
  const validation =
    typeof body === 'object' && body !== null && 'detail' in body
      ? validationProblems(body.detail)
      : [];

  throw new ApiError(
    detailMessage(body, `API request failed with status ${response.status}`),
    errorKind(response.status),
    response.status,
    requestId,
    validation,
  );
}
