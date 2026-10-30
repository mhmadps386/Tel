'use strict';

const http = require('node:http');
const { createApp } = require('./app');

// Binds to localhost only: this demo must never be exposed publicly.
const PORT = Number(process.env.PORT) || 3000;
http.createServer(createApp()).listen(PORT, '127.0.0.1', () => {
  console.log(`demo app listening on http://127.0.0.1:${PORT}`);
});
