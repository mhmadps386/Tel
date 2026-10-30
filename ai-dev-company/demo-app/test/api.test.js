'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { startServer } = require('./helpers');

test('task API', async (t) => {
  const app = await startServer();
  t.after(app.close);

  await t.test('health check', async () => {
    const res = await app.request('GET', '/api/health');
    assert.equal(res.status, 200);
    assert.deepEqual(res.body, { status: 'ok' });
  });

  await t.test('creates and lists tasks', async () => {
    const created = await app.request('POST', '/api/tasks', { title: '  Write tests ' });
    assert.equal(created.status, 201);
    assert.equal(created.body.title, 'Write tests');
    assert.equal(created.body.done, false);
    const list = await app.request('GET', '/api/tasks');
    assert.equal(list.status, 200);
    assert.equal(list.body.length, 1);
  });

  await t.test('rejects invalid titles', async () => {
    assert.equal((await app.request('POST', '/api/tasks', { title: '' })).status, 400);
    assert.equal((await app.request('POST', '/api/tasks', {})).status, 400);
    assert.equal((await app.request('POST', '/api/tasks', { title: 'x'.repeat(201) })).status, 400);
  });

  await t.test('rejects malformed JSON', async () => {
    const res = await fetch(app.base + '/api/tasks', { method: 'POST', body: '{nope' });
    assert.equal(res.status, 400);
  });

  await t.test('updates and deletes a task', async () => {
    const { body: task } = await app.request('POST', '/api/tasks', { title: 'Ship it' });
    const patched = await app.request('PATCH', `/api/tasks/${task.id}`, { done: true });
    assert.equal(patched.status, 200);
    assert.equal(patched.body.done, true);
    assert.equal((await app.request('PATCH', `/api/tasks/${task.id}`, { done: 'yes' })).status, 400);
    assert.equal((await app.request('DELETE', `/api/tasks/${task.id}`)).status, 204);
    assert.equal((await app.request('DELETE', `/api/tasks/${task.id}`)).status, 404);
    assert.equal((await app.request('PATCH', '/api/tasks/9999', { done: true })).status, 404);
  });

  await t.test('serves the dashboard', async () => {
    const res = await fetch(app.base + '/');
    assert.equal(res.status, 200);
    assert.match(await res.text(), /Task Dashboard/);
  });
});
