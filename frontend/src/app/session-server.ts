import { request } from 'node:http';
import { isIP } from 'node:net';
import { anonymousSession, normalizeSession } from './session';
import type { SessionSummary } from './session';

type PublicSummary = { key: string; value: SessionSummary; expiresAt: number };
type SessionResponse = { value: unknown; cookies: string[] };
const PUBLIC_CONFIG_TTL_MS = 5 * 60 * 1000;
const MAX_BODY_BYTES = 64 * 1024;
let publicSummary: PublicSummary | null = null;
let publicPending: { key: string; promise: Promise<SessionSummary> } | null = null;

function copySession(value: SessionSummary): SessionSummary {
  return { ...value, locales: value.locales.map((locale) => ({ ...locale })) };
}

function socketSession(endpoint: string, socketPath: string, cookie: string | undefined,
  timeoutMs: number, publicOrigin: string, clientIp?: string, cloudflareIp?: string): Promise<SessionResponse | null> {
  return new Promise((resolve) => {
    const url = new URL(endpoint);
    if (url.protocol !== 'http:' || url.username || url.password) { resolve(null); return; }
    const req = request({ socketPath, path: `${url.pathname}${url.search}`, method: 'GET',
      headers: { Host: url.host, Accept: 'application/json',
        'X-Forwarded-Proto': new URL(publicOrigin).protocol.slice(0, -1),
        ...(clientIp && isIP(clientIp) ? { 'X-Forwarded-For': clientIp } : {}),
        // Flask independently checks that the forwarded peer belongs to Cloudflare.
        ...(cloudflareIp && isIP(cloudflareIp) ? { 'CF-Connecting-IP': cloudflareIp } : {}),
        ...(cookie ? { Cookie: cookie } : {}) } });
    const timer = setTimeout(() => req.destroy(new Error('Session timeout')), timeoutMs);
    const finish = (value: SessionResponse | null) => { clearTimeout(timer); resolve(value); };
    req.on('error', () => finish(null));
    req.on('response', (res) => {
      if (res.statusCode !== 200 || !/^application\/json(?:;|$)/i.test(res.headers['content-type'] ?? '')) {
        res.destroy(); finish(null); return;
      }
      const chunks: Buffer[] = [];
      let size = 0;
      res.on('data', (chunk: Buffer) => {
        size += chunk.length;
        if (size > MAX_BODY_BYTES) { req.destroy(); res.destroy(); finish(null); return; }
        chunks.push(chunk);
      });
      res.on('error', () => finish(null));
      res.on('aborted', () => finish(null));
      res.on('end', () => {
        try { finish({ value: JSON.parse(Buffer.concat(chunks).toString('utf8')), cookies: res.headers['set-cookie'] ?? [] }); }
        catch { finish(null); }
      });
    });
    req.end();
  });
}

async function requestSession(endpoint: string, cookie: string | undefined,
  timeoutMs: number, socketPath?: string, publicOrigin = endpoint, clientIp?: string,
  cloudflareIp?: string, onCookies?: (cookies: string[]) => void): Promise<SessionSummary | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    let result: SessionResponse | null;
    if (socketPath) {
      result = await socketSession(endpoint, socketPath, cookie, timeoutMs, publicOrigin, clientIp, cloudflareIp);
    } else {
      const response = await fetch(endpoint, {
        signal: controller.signal, redirect: 'error',
        headers: { Accept: 'application/json', ...(cookie ? { Cookie: cookie } : {}) },
      });
      if (response.status !== 200) return null;
      result = { value: await response.json(), cookies: onCookies ? response.headers.getSetCookie() : [] };
    }
    const value = result?.value;
    if (!value || typeof value !== 'object' || typeof (value as Record<string, unknown>).authenticated !== 'boolean') return null;
    const session = normalizeSession(value);
    if (session.authenticated && session.translationJoin && result?.cookies.length) onCookies?.(result.cookies);
    return session;
  } catch {
    // Failures fall back after the bounded timeout and are never cached.
    return null;
  } finally { clearTimeout(timer); }
}

/** Cookie-bearing requests stay private; only cookieless public configuration is shared. */
export async function fetchSession(endpoint: string, cookie: string | undefined,
  timeoutMs = 1200, socketPath?: string, publicOrigin = endpoint, clientIp?: string,
  cloudflareIp?: string, onCookies?: (cookies: string[]) => void): Promise<SessionSummary> {
  if (cookie) return (await requestSession(endpoint, cookie, timeoutMs, socketPath, publicOrigin, clientIp, cloudflareIp, onCookies)) ?? copySession(anonymousSession);
  const key = JSON.stringify([socketPath ?? null, endpoint, publicOrigin]);
  if (publicSummary?.key === key && publicSummary.expiresAt > Date.now()) return copySession(publicSummary.value);
  if (publicPending?.key !== key) {
    const promise = requestSession(endpoint, undefined, timeoutMs, socketPath, publicOrigin, clientIp, cloudflareIp).then((value) => {
      if (value && !value.authenticated) {
        const publicValue = { ...value, role: 'guest', name: null, picture: null,
          globalAdmin: false, hasAdminAccess: false, unread: 0 };
        publicSummary = { key, value: publicValue, expiresAt: Date.now() + PUBLIC_CONFIG_TTL_MS };
        return publicValue;
      }
      return copySession(anonymousSession);
    }).finally(() => { if (publicPending?.promise === promise) publicPending = null; });
    publicPending = { key, promise };
  }
  return copySession(await publicPending.promise);
}
