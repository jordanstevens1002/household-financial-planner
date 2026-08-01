import { describe, expect, it } from 'vitest';

import nginxConfig from '../../nginx/default.conf?raw';

describe('production frontend caching', () => {
  it('publicly proxies only the database-free API liveness check', () => {
    expect(nginxConfig).toMatch(
      /location = \/health\/live\s*\{[\s\S]*?proxy_pass http:\/\/api:8000;/,
    );
    expect(nginxConfig).toMatch(/location \/health\/\s*\{[\s\S]*?return 404;/);
    expect(nginxConfig).not.toContain('location = /health/ready');
  });

  it('returns 404 for obsolete asset chunks instead of the application shell', () => {
    expect(nginxConfig).toMatch(
      /location \/assets\/\s*\{[\s\S]*?try_files \$uri =404;/,
    );
  });

  it('caches fingerprinted assets and never caches the application shell', () => {
    expect(nginxConfig).toContain(
      'Cache-Control "public, max-age=31536000, immutable"',
    );
    expect(nginxConfig).toMatch(
      /location = \/index\.html\s*\{[\s\S]*?Cache-Control "no-cache, no-store, must-revalidate"/,
    );
  });

  it('retains the restrictive referrer policy in cache-specific locations', () => {
    expect(nginxConfig.match(/Referrer-Policy "no-referrer"/g)).toHaveLength(4);
  });
});
