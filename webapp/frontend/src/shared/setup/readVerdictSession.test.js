import assert from 'node:assert/strict';
import test from 'node:test';
import { createReadVerdictSession } from './readVerdictSession.js';

const identity = { scan_date: '2026-10-22', universe_type: 'us_equities', engine_config_version: 'current' };
function setup(request, scanIdentity = identity) {
  const changes = [];
  const session = createReadVerdictSession({ ticker: 'AAA', scanIdentity, request,
    onChange: (state) => changes.push(state) });
  return { session, changes };
}
const stored = { verdict: 'disagree', grade_verdict: 'too_high', note: 'rails', engine_config_version: 'current' };

test('a grade update retains the read reason and sends all four identity legs', async () => {
  let sent;
  const { session } = setup(async (method, body) => {
    if (method === 'GET') return stored;
    sent = body; return body;
  });
  await session.load();
  await session.save({ grade_verdict: 'too_low' });
  assert.deepEqual(sent, { ticker: 'AAA', ...identity, verdict: 'disagree', grade_verdict: 'too_low', note: 'rails' });
  assert.equal(session.getState().grade_verdict, 'too_low');
  await session.save({ verdict: null });
  assert.equal(sent.grade_verdict, null);
  assert.equal(sent.note, null);
});

test('saving serializes requests and a failure restores the complete prior judgment', async () => {
  let fail;
  let posts = 0;
  const { session } = setup((method) => method === 'GET' ? Promise.resolve(stored)
    : new Promise((resolve, reject) => { posts += 1; fail = reject; }));
  await session.load();
  const saving = session.save({ grade_verdict: 'too_low' });
  assert.equal(session.getState().status, 'saving');
  assert.equal(await session.save({ verdict: 'agree' }), false);
  assert.equal(posts, 1);
  fail(new Error('offline'));
  assert.equal(await saving, false);
  assert.equal(session.getState().grade_verdict, 'too_high');
  assert.equal(session.getState().note, 'rails');
  assert.match(session.getState().error, /did not save/);
});

test('late loads and writes on a disposed chart never publish into the next chart', async () => {
  let finish;
  const { session, changes } = setup(() => new Promise((resolve) => { finish = resolve; }));
  const loading = session.load();
  const n = changes.length;
  session.dispose();
  finish(stored);
  await loading;
  assert.equal(changes.length, n);
  assert.equal(await session.save({ verdict: 'agree' }), false);
  let finishWrite;
  const writing = setup((method) => method === 'GET' ? Promise.resolve(stored)
    : new Promise((resolve) => { finishWrite = resolve; }));
  await writing.session.load();
  const pending = writing.session.save({ verdict: 'agree' });
  const before = writing.changes.length;
  writing.session.dispose();
  finishWrite({});
  await pending;
  assert.equal(writing.changes.length, before);
});

test('old-engine and unstamped feedback require a new judgment', async () => {
  for (const version of ['previous', null]) {
    const { session } = setup(async () => ({ ...stored, engine_config_version: version }));
    await session.load();
    assert.equal(session.getState().stale, true);
    assert.equal(session.getState().verdict, null);
    assert.equal(session.getState().grade_verdict, null);
  }
});

test('failed loads refuse writes and can be retried without losing stored feedback', async () => {
  let calls = 0;
  const { session } = setup(async () => { if (++calls === 1) throw new Error('offline'); return stored; });
  await session.load();
  assert.equal(session.getState().status, 'error');
  assert.equal(await session.save({ verdict: 'agree' }), false);
  await session.load();
  assert.equal(session.getState().grade_verdict, 'too_high');
});

test('a partial identity cannot issue feedback requests', async () => {
  const { session } = setup(() => assert.fail('request must not be sent'), { scan_date: '2026-10-22' });
  await session.load();
  assert.equal(session.getState().status, 'unavailable');
});
