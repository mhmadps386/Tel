'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { startServer } = require('./helpers');
const { TaskStore, ValidationError } = require('../src/store');

test('task priorities', async (t) => {
  const app = await startServer();
  t.after(app.close);

  await t.test('defaults priority to medium on create', async () => {
    const res = await app.request('POST', '/api/tasks', { title: 'Default' });
    assert.equal(res.status, 201);
    assert.equal(res.body.priority, 'medium');
  });

  await t.test('accepts each valid priority on create', async () => {
    for (const priority of ['low', 'medium', 'high']) {
      const res = await app.request('POST', '/api/tasks', { title: `P ${priority}`, priority });
      assert.equal(res.status, 201);
      assert.equal(res.body.priority, priority);
    }
  });

  await t.test('rejects invalid priority on create', async () => {
    for (const priority of ['urgent', 'HIGH', '', null, 3, ['high']]) {
      const res = await app.request('POST', '/api/tasks', { title: 'Bad', priority });
      assert.equal(res.status, 400, `priority ${JSON.stringify(priority)} should be rejected`);
      assert.match(res.body.error, /priority/);
    }
  });

  await t.test('updates priority via PATCH', async () => {
    const { body: task } = await app.request('POST', '/api/tasks', { title: 'Change me' });
    const res = await app.request('PATCH', `/api/tasks/${task.id}`, { priority: 'high' });
    assert.equal(res.status, 200);
    assert.equal(res.body.priority, 'high');
  });

  await t.test('rejects invalid priority on PATCH without partial update', async () => {
    const { body: task } = await app.request('POST', '/api/tasks', { title: 'Keep me', priority: 'low' });
    for (const priority of ['critical', null, 1]) {
      const res = await app.request('PATCH', `/api/tasks/${task.id}`, { title: 'Changed', priority });
      assert.equal(res.status, 400);
    }
    const list = await app.request('GET', '/api/tasks');
    const stored = list.body.find((x) => x.id === task.id);
    assert.equal(stored.priority, 'low');
    assert.equal(stored.title, 'Keep me');
  });
});

test('task list filters', async (t) => {
  const app = await startServer();
  t.after(app.close);

  const make = async (title, priority, done) => {
    const { body } = await app.request('POST', '/api/tasks', { title, priority });
    if (done) await app.request('PATCH', `/api/tasks/${body.id}`, { done: true });
    return body.id;
  };
  const ids = {
    lowOpen: await make('a', 'low', false),
    lowDone: await make('b', 'low', true),
    medOpen: await make('c', 'medium', false),
    highDone: await make('d', 'high', true),
    highOpen: await make('e', 'high', false),
  };
  const idsOf = (res) => res.body.map((x) => x.id).sort((a, b) => a - b);

  await t.test('no filters returns all tasks', async () => {
    const res = await app.request('GET', '/api/tasks');
    assert.equal(res.status, 200);
    assert.equal(res.body.length, 5);
  });

  await t.test('filters by status', async () => {
    const open = await app.request('GET', '/api/tasks?status=open');
    assert.equal(open.status, 200);
    assert.deepEqual(idsOf(open), [ids.lowOpen, ids.medOpen, ids.highOpen]);
    const done = await app.request('GET', '/api/tasks?status=done');
    assert.deepEqual(idsOf(done), [ids.lowDone, ids.highDone]);
  });

  await t.test('filters by priority', async () => {
    assert.deepEqual(idsOf(await app.request('GET', '/api/tasks?priority=low')), [ids.lowOpen, ids.lowDone]);
    assert.deepEqual(idsOf(await app.request('GET', '/api/tasks?priority=medium')), [ids.medOpen]);
    assert.deepEqual(idsOf(await app.request('GET', '/api/tasks?priority=high')), [ids.highDone, ids.highOpen]);
  });

  await t.test('combines status and priority filters', async () => {
    assert.deepEqual(idsOf(await app.request('GET', '/api/tasks?status=done&priority=high')), [ids.highDone]);
    assert.deepEqual(idsOf(await app.request('GET', '/api/tasks?priority=low&status=open')), [ids.lowOpen]);
    const none = await app.request('GET', '/api/tasks?status=done&priority=medium');
    assert.equal(none.status, 200);
    assert.deepEqual(none.body, []);
  });

  await t.test('rejects unknown filter values with 400', async () => {
    for (const query of ['status=closed', 'status=', 'status=OPEN', 'priority=urgent',
      'priority=', 'status=open&priority=nope', 'status=nope&priority=low']) {
      const res = await app.request('GET', `/api/tasks?${query}`);
      assert.equal(res.status, 400, `?${query} should be rejected`);
      assert.ok(res.body.error);
    }
  });
});

test('GET /api/stats', async (t) => {
  const app = await startServer();
  t.after(app.close);

  await t.test('returns all keys as zero when empty', async () => {
    const res = await app.request('GET', '/api/stats');
    assert.equal(res.status, 200);
    assert.deepEqual(res.body, { total: 0, open: 0, done: 0, byPriority: { low: 0, medium: 0, high: 0 } });
  });

  await t.test('counts tasks by status and priority and tracks changes', async () => {
    const a = (await app.request('POST', '/api/tasks', { title: 'a', priority: 'high' })).body;
    await app.request('POST', '/api/tasks', { title: 'b' });
    const c = (await app.request('POST', '/api/tasks', { title: 'c', priority: 'high' })).body;
    await app.request('PATCH', `/api/tasks/${a.id}`, { done: true });

    let res = await app.request('GET', '/api/stats');
    assert.deepEqual(res.body, { total: 3, open: 2, done: 1, byPriority: { low: 0, medium: 1, high: 2 } });

    await app.request('PATCH', `/api/tasks/${c.id}`, { priority: 'low' });
    await app.request('DELETE', `/api/tasks/${a.id}`);
    res = await app.request('GET', '/api/stats');
    assert.deepEqual(res.body, { total: 2, open: 2, done: 0, byPriority: { low: 1, medium: 1, high: 0 } });
    for (const v of [res.body.total, res.body.open, res.body.done, ...Object.values(res.body.byPriority)]) {
      assert.ok(Number.isInteger(v));
    }
  });
});

test('dashboard wires priorities and stats', async (t) => {
  const app = await startServer();
  t.after(app.close);
  const html = await (await fetch(app.base + '/')).text();
  assert.match(html, /\/api\/stats/);
  assert.match(html, /<select id="priority"/);
  for (const p of ['low', 'medium', 'high']) assert.match(html, new RegExp(`<option value="${p}"`));
  assert.match(html, /priority-\$\{t\.priority\}/);
});

test('TaskStore unit rules', () => {
  const store = new TaskStore();
  assert.equal(store.create({ title: 'x' }).priority, 'medium');
  assert.throws(() => store.create({ title: 'x', priority: 'bogus' }), ValidationError);
  assert.throws(() => store.list({ status: 'bogus' }), ValidationError);
  assert.throws(() => store.list({ priority: 'bogus' }), ValidationError);
  assert.equal(store.list().length, 1);
  assert.deepEqual(store.stats(), { total: 1, open: 1, done: 0, byPriority: { low: 0, medium: 1, high: 0 } });
});
