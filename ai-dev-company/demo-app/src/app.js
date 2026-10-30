'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { TaskStore, ValidationError } = require('./store');

const PUBLIC_DIR = path.join(__dirname, '..', 'public');
const MAX_BODY_BYTES = 10 * 1024;

function sendJson(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new ValidationError('request body too large'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (chunks.length === 0) return resolve({});
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));
      } catch {
        reject(new ValidationError('invalid JSON body'));
      }
    });
    req.on('error', reject);
  });
}

function createApp(store = new TaskStore()) {
  return async function handler(req, res) {
    const url = new URL(req.url, 'http://localhost');
    const match = url.pathname.match(/^\/api\/tasks\/(\d+)$/);

    try {
      if (req.method === 'GET' && url.pathname === '/api/health') {
        return sendJson(res, 200, { status: 'ok' });
      }
      if (req.method === 'GET' && url.pathname === '/api/tasks') {
        return sendJson(res, 200, store.list());
      }
      if (req.method === 'POST' && url.pathname === '/api/tasks') {
        const body = await readJson(req);
        return sendJson(res, 201, store.create(body));
      }
      if (match && req.method === 'PATCH') {
        const body = await readJson(req);
        const task = store.update(Number(match[1]), body);
        return task ? sendJson(res, 200, task) : sendJson(res, 404, { error: 'not found' });
      }
      if (match && req.method === 'DELETE') {
        return store.remove(Number(match[1]))
          ? sendJson(res, 204, {})
          : sendJson(res, 404, { error: 'not found' });
      }
      if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        return fs.createReadStream(path.join(PUBLIC_DIR, 'index.html')).pipe(res);
      }
      return sendJson(res, 404, { error: 'not found' });
    } catch (err) {
      if (err instanceof ValidationError) return sendJson(res, 400, { error: err.message });
      return sendJson(res, 500, { error: 'internal error' });
    }
  };
}

module.exports = { createApp };
