// Run with: node --experimental-strip-types scripts/verify_developer_writes.mjs
// Checks the pure parts of the /developer write controls (frontend/src/app/developer-route.ts):
// when the controls appear, what a write sends, and how failures read. No browser needed.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const route = await import(fileURLToPath(new URL('../frontend/src/app/developer-route.ts', import.meta.url)));
const { readDeveloper, developerWrite, writeFailure, developerCopy, developerIssuableScopes } = route;
const id = 'a'.repeat(24);
const csrf = '1999999999.0123456789abcdef01234567.' + 'f'.repeat(64);
const app = { id, name: 'A', description: '', client_id: 'cid', allowed_scopes: ['read'] };

// Controls exist only when Go says writes are on and sends a well-formed token.
assert.equal(readDeveloper({ access: true, apps: [app], tokens: [] }, false).csrf, undefined);
assert.equal(readDeveloper({ access: true, apps: [app], tokens: [], writes: true, csrf }, false).csrf, csrf);
assert.equal(readDeveloper({ access: true, apps: [app], tokens: [], writes: true }, false).csrf, undefined);
assert.equal(readDeveloper({ access: true, apps: [app], tokens: [], writes: true, csrf: '<script>' }, false).csrf, undefined);
assert.equal(readDeveloper({ access: true, apps: [app], tokens: [], writes: 'yes', csrf }, false).csrf, undefined);
assert.equal(readDeveloper({ access: true, app, tokens: [], writes: true, csrf }, true).csrf, csrf);
assert.deepEqual(readDeveloper({ access: false }, false), { status: 'locked' });

// Privileged scopes are never offered by the issuing forms.
assert(!developerIssuableScopes.includes('admin') && !developerIssuableScopes.includes('mcp.admin'));

// A write sends the CSRF header, JSON and the cookie; DELETE has no body.
const calls = [];
const fake = (status, body) => async (url, init) => { calls.push({ url, init }); return { ok: status < 400, status, json: async () => body }; };
let result = await developerWrite('POST', '/api/developer/apps', csrf, { name: 'x' }, fake(200, { status: 'success', app: { client_secret: 'S' } }));
assert(result.ok && result.body.app.client_secret === 'S');
assert.equal(calls[0].init.headers['X-CSRF-Token'], csrf);
assert.equal(calls[0].init.credentials, 'same-origin');
assert.equal(calls[0].init.body, '{"name":"x"}');
await developerWrite('DELETE', `/api/developer/tokens/${id}`, csrf, undefined, fake(200, { status: 'success' }));
assert.equal(calls[1].init.body, undefined);

// Failures: no secret in the message, server text only for input errors.
assert.equal(writeFailure(429, null), developerCopy.rateLimited);
assert.equal(writeFailure(403, { error: 'invalid csrf token' }), developerCopy.sessionExpired);
assert.equal(writeFailure(401, null), developerCopy.sessionExpired);
assert.equal(writeFailure(403, { error: 'forbidden' }), developerCopy.failed);
assert.equal(writeFailure(400, { error: 'Nimi vaaditaan' }), 'Nimi vaaditaan');
assert.equal(writeFailure(503, { error: 'service unavailable' }), developerCopy.failed);
result = await developerWrite('POST', '/x', csrf, {}, fake(403, { error: 'invalid csrf token' }));
assert(!result.ok && result.message === developerCopy.sessionExpired);
result = await developerWrite('POST', '/x', csrf, {}, async () => { throw new Error('offline'); });
assert(!result.ok && result.message === developerCopy.failed);
result = await developerWrite('POST', '/x', csrf, {}, async () => ({ ok: true, status: 200, json: async () => { throw new Error('bad json'); } }));
assert(!result.ok, 'an unreadable success body is a failure, not an empty success');
console.log('PASS: developer write controls');
