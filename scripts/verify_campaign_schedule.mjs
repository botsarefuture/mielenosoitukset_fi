// Run with: node --experimental-strip-types scripts/verify_campaign_schedule.mjs
// Checks the campaign page's phase logic (frontend/src/app/campaign-schedule.ts) at every
// boundary of the approved schedule. Dates are Helsinki dates, as the host computes them.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const lib = await import(fileURLToPath(new URL('../frontend/src/app/campaign-schedule.ts', import.meta.url)));
const { campaignSchedule, campaignPhase, defaultSchedule, fiDate, fiRange, fiWeekday } = lib;
const config = JSON.parse(readFileSync(new URL('../mielenosoitukset_fi/utils/data/fundraising.json', import.meta.url), 'utf8'));

// One shared configuration: the bundled defaults equal the file the Go API serves.
const fromFile = campaignSchedule(config);
assert.deepEqual(fromFile, defaultSchedule, 'defaults match utils/data/fundraising.json');
assert.equal(fromFile.collectionNumber, 'RA/2026/1586');
assert.equal(fromFile.area, 'Koko Suomi Ahvenanmaata lukuun ottamatta');

const states = today => campaignPhase(fromFile, today).milestones.map(m => m.state[0]).join('');
const here = today => campaignPhase(fromFile, today).milestones.find(m => m.state === 'current')?.key ?? null;
const upNext = today => campaignPhase(fromFile, today).milestones.find(m => m.upNext)?.key ?? null;

// Before opening: nothing under way, the opening is next, reminder slot, info below "Mistä on kyse".
let p = campaignPhase(fromFile, '2026-11-15');
assert(p.preLaunch && !p.collectionOpen && !p.collectionClosed && !p.collectionInfoFirst);
assert.equal(states('2026-11-15'), 'nnnnn');
assert.equal(upNext('2026-11-15'), 'collectionOpens');
assert.equal(here('2026-11-15'), null);

// 2026-11-16 00:00 Helsinki: opens, donate slot, block order swaps, dot moves to "Tässä ollaan nyt".
p = campaignPhase(fromFile, '2026-11-16');
assert(!p.preLaunch && p.collectionOpen && !p.collectionClosed && p.collectionInfoFirst);
assert.equal(states('2026-11-16'), 'cnnnn');
assert.equal(upNext('2026-11-16'), null);

// Last collection day is still open; the day after it is closed and the closing milestone is current.
p = campaignPhase(fromFile, '2027-02-15');
assert(p.collectionOpen && !p.collectionClosed);
assert.equal(here('2027-02-15'), 'collectionOpens');
p = campaignPhase(fromFile, '2027-02-16');
assert(!p.collectionOpen && p.collectionClosed && p.collectionInfoFirst);
assert.equal(states('2027-02-16'), 'dcnnn');

assert.equal(here('2027-02-28'), 'collectionEnds');
assert.equal(here('2027-03-01'), 'campaignStarts');
assert.equal(states('2027-03-01'), 'ddcnn');
assert.equal(here('2027-03-05'), 'campaignStarts');
assert.equal(here('2027-03-06'), 'opening');
assert.equal(here('2027-05-02'), 'opening');
assert.equal(here('2027-05-03'), 'marketingWeek');
assert.equal(here('2027-05-09'), 'marketingWeek');
assert.equal(states('2027-05-10'), 'ddddd');
assert.equal(here('2027-05-10'), null);
assert.equal(upNext('2027-05-10'), null);

// Month and year ends, and a leap-free February.
assert.equal(lib.nextDay('2027-02-28'), '2027-03-01');
assert.equal(lib.nextDay('2026-12-31'), '2027-01-01');

// Formatting comes from the configuration.
assert.equal(fiDate('2026-11-16'), '16.11.2026');
assert.equal(lib.fiDayMonth('2026-11-16'), '16.11.');
assert.equal(fiRange('2027-05-03', '2027-05-09'), '3.–9.5.2027');
assert.equal(fiRange('2027-05-03', '2027-05-09', false), '3.–9.5.');
assert.equal(fiRange('2027-04-28', '2027-05-04'), '28.4.–4.5.2027');
assert.equal(fiWeekday('2027-03-06'), 'lauantai');
assert.equal(lib.fiWeekdayEssive('2027-03-06'), 'lauantaina');
assert.equal(lib.fiWeekdayShort('2027-03-06'), 'La');

// Bad values fall back field by field; a changed date moves the phase.
const moved = campaignSchedule({ start_date: '2026-11-20', end_date: 'nope', opening_date: '2027-02-30', opening_time: '8' });
assert.equal(moved.collectionStart, '2026-11-20');
assert.equal(moved.collectionEnd, defaultSchedule.collectionEnd);
assert.equal(moved.openingDate, defaultSchedule.openingDate);
assert.equal(moved.openingTime, defaultSchedule.openingTime);
assert(campaignPhase(moved, '2026-11-16').preLaunch);
assert.deepEqual(campaignSchedule(null), defaultSchedule);
console.log('PASS: campaign schedule phases and formats');
