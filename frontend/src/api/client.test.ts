import { ApiError, apiRequest } from './client';

function jsonResponse(
  body: unknown,
  status = 200,
  requestId?: string,
): Response {
  const headers = new Headers({ 'Content-Type': 'application/json' });
  if (requestId !== undefined) {
    headers.set('X-Request-ID', requestId);
  }
  return new Response(JSON.stringify(body), { headers, status });
}

describe('apiRequest', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses cookie credentials and sends CSRF only for mutations', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ id: 'household-1' }));
    vi.stubGlobal('fetch', fetchMock);

    await apiRequest('/api/v1/households', {
      body: JSON.stringify({ display_name: 'Home' }),
      csrfToken: 'csrf-value',
      method: 'POST',
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, request] = fetchMock.mock.calls[0] ?? [];
    expect(request?.credentials).toBe('include');
    expect(new Headers(request?.headers).get('X-CSRF-Token')).toBe(
      'csrf-value',
    );
    expect(new Headers(request?.headers).get('Content-Type')).toBe(
      'application/json',
    );

    await apiRequest('/api/v1/households', { csrfToken: 'not-for-get' });
    const [, getRequest] = fetchMock.mock.calls[1] ?? [];
    expect(new Headers(getRequest?.headers).has('X-CSRF-Token')).toBe(false);
  });

  it('normalises authentication and permission failures with request IDs', async () => {
    for (const [status, kind] of [
      [401, 'unauthorised'],
      [403, 'forbidden'],
    ] as const) {
      vi.stubGlobal(
        'fetch',
        vi
          .fn<typeof fetch>()
          .mockResolvedValue(
            jsonResponse(
              { detail: 'Access denied' },
              status,
              `request-${status}`,
            ),
          ),
      );

      const error = await apiRequest('/api/v1/me').catch(
        (caught: unknown) => caught,
      );
      expect(error).toBeInstanceOf(ApiError);
      expect(error).toMatchObject({
        kind,
        message: 'Access denied',
        requestId: `request-${status}`,
        status,
      });
    }
  });

  it('maps FastAPI validation details to typed field problems', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse(
          {
            detail: [
              {
                loc: ['body', 'display_name'],
                msg: 'Field required',
                type: 'missing',
              },
            ],
          },
          422,
          'validation-request',
        ),
      ),
    );

    const error = await apiRequest('/api/v1/households', {
      body: '{}',
      method: 'POST',
    }).catch((caught: unknown) => caught);

    expect(error).toMatchObject({
      kind: 'validation',
      requestId: 'validation-request',
      validation: [
        {
          field: 'display_name',
          message: 'Field required',
          type: 'missing',
        },
      ],
    });
  });

  it('distinguishes server and network failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(jsonResponse({ detail: 'Unavailable' }, 503)),
    );
    await expect(apiRequest('/api/v1/me')).rejects.toMatchObject({
      kind: 'server',
      status: 503,
    });

    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Network failed')),
    );
    await expect(apiRequest('/api/v1/me')).rejects.toMatchObject({
      kind: 'network',
      status: 0,
    });
  });

  it('handles empty success and non-JSON unexpected responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(new Response(null, { status: 204 })),
    );
    await expect(apiRequest('/api/v1/me')).resolves.toBeUndefined();

    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response('No coffee', {
          headers: { 'X-Request-ID': 'teapot-request' },
          status: 418,
        }),
      ),
    );
    await expect(apiRequest('/api/v1/me')).rejects.toMatchObject({
      kind: 'unexpected',
      message: 'API request failed with status 418',
      requestId: 'teapot-request',
    });
  });
});
