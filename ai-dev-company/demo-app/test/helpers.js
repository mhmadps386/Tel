'use strict';

const http = require('node:http');
const { createApp } = require('../src/app');

async function startServer() {
  const server = http.createServer(createApp());
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  async function request(method, path, body) {
    const res = await fetch(base + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    return { status: res.status, body: text ? JSON.parse(text) : null, raw: text };
  }
  return { server, base, request, close: () => new Promise((r) => server.close(r)) };
}

module.exports = { startServer };
