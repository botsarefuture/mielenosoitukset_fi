// Phase boundaries, milestones and dismissal of the fundraising bar, against the built host.
// Run after `npm run app:build`.
import assert from 'node:assert/strict';
import { dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const { barPhase, barMilestone, isDismissed, normalizeBar, dismissScript, shortDate } =
  await import(pathToFileURL(`${root}/frontend/dist/server/render.js`));

const config = (over = {}) => normalizeBar({ enabled: true, start: '2026-11-16', end: '2027-02-15', donations_open: true, ...over });

// Phase boundaries by Helsinki date.
assert.equal(barPhase(config(), '2026-11-15'), 'pre');
assert.equal(barPhase(config(), '2026-11-16'), 'open');
assert.equal(barPhase(config(), '2027-02-15'), 'open', 'the end date is the last day shown');
assert.equal(barPhase(config(), '2027-02-16'), null, 'hidden after the end date');
// Off by default and when the configuration is incomplete or unconfirmed.
assert.equal(barPhase(normalizeBar(undefined), '2026-11-20'), null);
assert.equal(barPhase(config({ enabled: false }), '2026-11-20'), null);
assert.equal(barPhase(config({ start: null }), '2026-11-20'), null);
assert.equal(barPhase(config({ start: '2027-03-01' }), '2026-11-20'), null, 'start after end is rejected');
assert.equal(barPhase(config({ start: 'not-a-date' }), '2026-11-20'), null);
assert.equal(barPhase(config({ donations_open: false }), '2026-11-20'), null, 'never claims a collection that is not active');
assert.equal(barPhase(config({ donations_open: false }), '2026-11-10'), 'pre', 'the opening can be announced before confirmation');
// The Helsinki date changes at 00:00 Helsinki, not UTC (winter time, UTC+2).
assert.equal(normalizeBar({}, new Date('2026-11-15T21:59:59Z')).today, '2026-11-15');
assert.equal(normalizeBar({}, new Date('2026-11-15T22:00:00Z')).today, '2026-11-16');
assert.equal(normalizeBar({}, new Date('2027-02-15T22:00:00Z')).today, '2027-02-16');

// Milestones.
assert.equal(barMilestone(config(), '2026-11-15'), 'pre');
assert.equal(barMilestone(config(), '2026-11-16'), 'open');
assert.equal(barMilestone(config(), '2027-02-01'), 'open');
assert.equal(barMilestone(config(), '2027-02-02'), 'last');
assert.equal(barMilestone(config(), '2027-02-16'), null);

// Dismissal: seven days, ended early by a new milestone, tolerant of bad storage.
const now = Date.UTC(2026, 10, 20, 12);
const stored = (milestone, ageMs) => JSON.stringify({ at: now - ageMs, milestone });
assert.equal(isDismissed(stored('open', 6 * 86_400_000), 'open', now), true);
assert.equal(isDismissed(stored('open', 7 * 86_400_000), 'open', now), false, 'expires after seven days');
assert.equal(isDismissed(stored('pre', 1000), 'open', now), false, 'a new milestone shows the bar again');
assert.equal(isDismissed(stored('open', -1000), 'open', now), false, 'a timestamp in the future is ignored');
for (const bad of [null, '', 'x', '{}', '{"at":"1","milestone":"open"}', '[]', 'null']) assert.equal(isDismissed(bad, 'open', now), false, String(bad));
assert.equal(isDismissed(stored('open', 1000), null, now), false);

// The pre-paint script and isDismissed agree.
function runScript(storage, nowMs, milestone) {
  const attrs = {};
  const source = dismissScript(milestone).replace(/^<script>|<\/script>$/g, '');
  const fakeDate = { now: () => nowMs };
  new Function('localStorage', 'document', 'Date', 'JSON', source)(
    { getItem: () => storage }, { documentElement: { setAttribute: (k, v) => { attrs[k] = v; } } }, fakeDate, JSON);
  return 'data-fb-hidden' in attrs;
}
for (const [raw, milestone] of [[stored('open', 1000), 'open'], [stored('open', 8 * 86_400_000), 'open'], [stored('pre', 1000), 'open'], ['garbage', 'open'], [null, 'pre']]) {
  assert.equal(runScript(raw, now, milestone), isDismissed(raw, milestone, now), `script and isDismissed agree for ${raw}`);
}

assert.equal(shortDate('2026-11-16'), '16.11.');
assert.equal(shortDate('2027-02-05'), '5.2.');
console.log('PASS: fundraising bar phases, milestones and dismissal');
